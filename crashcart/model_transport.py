"""One bounded structured-model request to an explicitly selected provider.

This module owns wire formats only. Callers validate plans and own reservations,
proof modes and all payment decisions. No redirects, retries or model fallback.
"""
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

MODAL_ORIGIN = "https://your-owned-model.example.invalid"
MODAL_MODEL = "deepseek-ai/DeepSeek-V4.1-Flash"
MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES, MAX_OUTPUT_TOKENS = 65536, 1048576, 1024
SECRET_KEYS = ("OPENAI_API_KEY", "MODAL_API_KEY", "MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET",
               "PAYPAL_CLIENT_SECRET", "KERNEL_API_KEY", "AG_STUDIO_LICENSE_KEY", "CRASHCART_OPERATOR_TOKEN")


class ModelTransportError(Exception):
    def __init__(self, code, *, metadata=None, response=None):
        super().__init__(code)
        self.code, self.metadata = code, metadata or {}
        # Transient IPC response, never persisted or included in exception text.
        self.response = response


def strict_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON field")
            result[key] = value
        return result
    def invalid_constant(_):
        raise ValueError("non-finite JSON value")
    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid_constant)


def json_object(text):
    value = strict_json(text)
    if not isinstance(value, dict):
        raise ValueError("expected JSON object")
    return value


def redact(value, environ):
    if isinstance(value, dict):
        return {k: redact(v, environ) for k, v in value.items() if isinstance(k, str) and
                not re.search(r"secret|authorization|api.?key|password|payer|shipping", k, re.I)}
    if isinstance(value, list):
        return [redact(v, environ) for v in value]
    if isinstance(value, str):
        for name in SECRET_KEYS:
            secret = environ.get(name)
            if isinstance(secret, str) and secret:
                value = value.replace(secret, "[REDACTED]")
        return re.sub(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", value) if "@" in value else value
    return value


@dataclass(frozen=True)
class ModelConfig:
    provider: str
    protocol: str
    origin: str
    endpoint: str
    model: str
    key: str = field(repr=False)

    def provenance(self):
        return {"provider": self.provider, "protocol": self.protocol, "endpoint_origin": self.origin}


def configuration(environ, *, injected=False):
    provider = environ.get("CRASHCART_MODEL_PROVIDER", "openai")
    if provider not in {"openai", "modal"}:
        raise ModelTransportError("INVALID_MODEL_PROVIDER")
    names = ("OPENAI_API_KEY", "OPENAI_MODEL") if provider == "openai" else ("MODAL_API_KEY", "MODAL_MODEL", "MODAL_BASE_URL")
    missing = [name for name in names if not environ.get(name)]
    if missing and not injected:
        raise ModelTransportError("MISSING_CONFIGURATION:" + ",".join(missing))
    if not injected and environ.get("CRASHCART_ALLOW_MODEL") != "1":
        raise ModelTransportError("MODEL_USAGE_NOT_AUTHORIZED:CRASHCART_ALLOW_MODEL")
    model = environ.get(names[1], "injected-local-test-model" if provider == "openai" else MODAL_MODEL)
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", model):
        raise ModelTransportError("INVALID_MODEL_CONFIGURATION")
    key = "" if injected else environ.get(names[0], "")
    if not isinstance(key, str) or (not injected and (not 1 <= len(key) <= 8192 or any(not 33 <= ord(c) <= 126 for c in key))):
        raise ModelTransportError("INVALID_MODEL_CREDENTIAL")
    if provider == "modal":
        # An exact owned origin prevents credentials being sent to arbitrary URLs.
        if environ.get("MODAL_BASE_URL", MODAL_ORIGIN if injected else None) != MODAL_ORIGIN or model != MODAL_MODEL:
            raise ModelTransportError("INVALID_MODAL_ENDPOINT_OR_MODEL")
        return ModelConfig(provider, "chat_completions", MODAL_ORIGIN, MODAL_ORIGIN + "/v1/chat/completions", model, key)
    return ModelConfig(provider, "responses", "https://api.openai.com", "https://api.openai.com/v1/responses", model, key)


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _direct_http(request, timeout):
    with build_opener(_NoRedirects()).open(request, timeout=timeout) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ModelTransportError("MODEL_RESPONSE_TOO_LARGE")
        return strict_json(raw)


def _worker_reply(raw):
    if len(raw) > MAX_RESPONSE_BYTES + 1024:
        raise ModelTransportError("MODEL_RESPONSE_TOO_LARGE")
    try:
        value = json_object(raw)
    except (TypeError, ValueError):
        raise ModelTransportError("MODEL_TRANSPORT_ERROR") from None
    if value.get("ok") is True and set(value) == {"ok", "response"}:
        return value["response"]
    code = value.get("error")
    if (value.get("ok") is False and set(value) == {"ok", "error"}
            and isinstance(code, str) and re.fullmatch(r"MODEL_(?:HTTP_[0-9]{3}|TIMEOUT|TRANSPORT_ERROR|RESPONSE_TOO_LARGE)", code)):
        raise ModelTransportError(code)
    raise ModelTransportError("MODEL_TRANSPORT_ERROR")


def http(request, timeout):
    """One isolated HTTP worker with a parent-enforced total wall-clock deadline.

    urllib's socket timeout only limits inactivity, so it is not the deadline.
    This parent kills and reaps the worker on timeout, including during DNS,
    TLS, headers or a slowly dripping body. Credentials travel only over stdin.
    """
    from .held_out import HeldOutError, guard_http_request
    try:
        guard_http_request(request)
    except HeldOutError as exc:
        raise ModelTransportError(exc.code) from None
    deadline = time.monotonic() + timeout
    packet = json.dumps({"url": request.full_url, "method": request.get_method(),
                         "headers": dict(request.header_items()),
                         "body": request.data.decode("utf-8"), "timeout": timeout},
                        ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    process = subprocess.Popen([sys.executable, "-I", "-S", str(Path(__file__).resolve()), "--http-worker"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        start_new_session=True, env={"PATH": os.defpath}, cwd=Path(__file__).resolve().parent)
    try:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args, timeout)
        raw, _ = process.communicate(packet, timeout=remaining)
    except BaseException as exc:
        # This worker starts no children. Kill the private process group as an
        # additional guard, and always reap it before returning to the caller.
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        raw, _ = process.communicate()
        if not isinstance(exc, subprocess.TimeoutExpired):
            raise
        response = None
        if raw:
            try:
                response = _worker_reply(raw)
            except ModelTransportError:
                pass
        raise ModelTransportError("MODEL_TIMEOUT", response=response) from None
    if process.returncode != 0:
        raise ModelTransportError("MODEL_TRANSPORT_ERROR")
    response = _worker_reply(raw)
    if time.monotonic() > deadline:
        raise ModelTransportError("MODEL_TIMEOUT", response=response)
    return response


def _http_worker():
    # Only the parent supplies this private pipe. Never emit request, headers,
    # traceback or raw errors to stdout/stderr; stdout is one bounded envelope.
    try:
        packet = sys.stdin.buffer.read(MAX_REQUEST_BYTES * 3 + 16384)
        value = json_object(packet)
        request = Request(value["url"], data=value["body"].encode("utf-8"),
                          method=value["method"], headers=value["headers"])
        response = _direct_http(request, value["timeout"])
        reply = {"ok": True, "response": response}
    except HTTPError as exc:
        exc.close()
        reply = {"ok": False, "error": "MODEL_HTTP_" + str(exc.code)}
    except (TimeoutError,):
        reply = {"ok": False, "error": "MODEL_TIMEOUT"}
    except ModelTransportError as exc:
        reply = {"ok": False, "error": exc.code}
    except Exception:
        reply = {"ok": False, "error": "MODEL_TRANSPORT_ERROR"}
    sys.stdout.buffer.write(json.dumps(reply, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8"))
    sys.stdout.buffer.flush()


def _metadata(response, config, environ):
    metadata = {**config.provenance(), "model": None, "response_id": None, "usage": None}
    if not isinstance(response, dict):
        return metadata
    for source, target in (("model", "model"), ("id", "response_id")):
        value = response.get(source)
        if isinstance(value, str) and 1 <= len(value) <= 200 and not any(ord(c) < 32 for c in value):
            metadata[target] = redact(value, environ)
    usage = response.get("usage")
    if isinstance(usage, dict):
        fields = {"input_tokens":"input_tokens", "output_tokens":"output_tokens", "total_tokens":"total_tokens"} if config.protocol == "responses" else {"prompt_tokens":"input_tokens", "completion_tokens":"output_tokens", "total_tokens":"total_tokens"}
        metadata["usage"] = {target: usage[name] for name, target in fields.items() if type(usage.get(name)) is int and usage[name] >= 0} or None
    return metadata


def _content(response, config, metadata):
    def fail(code):
        raise ModelTransportError(code, metadata=metadata)
    if not isinstance(response, dict):
        fail("MALFORMED_MODEL_RESPONSE")
    if not metadata["model"] or not metadata["response_id"]:
        fail("MISSING_MODEL_IDENTITY")
    if config.protocol == "chat_completions":
        choices = response.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            fail("MALFORMED_MODEL_RESPONSE")
        choice = choices[0]
        message = choice.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            fail("MALFORMED_MODEL_RESPONSE")
        if message.get("refusal"):
            fail("MODEL_REFUSED")
        if message.get("tool_calls") or message.get("function_call"):
            fail("UNSUPPORTED_MODEL_OUTPUT")
        if choice.get("finish_reason") != "stop":
            fail("MODEL_RESPONSE_INCOMPLETE")
        # Reasoning is never mined for an action or substituted for final content.
        return message.get("content")
    if response.get("status") != "completed":
        fail("MODEL_RESPONSE_INCOMPLETE")
    output = response.get("output")
    if not isinstance(output, list):
        fail("MALFORMED_MODEL_RESPONSE")
    texts = []
    for message in output:
        if not isinstance(message, dict) or message.get("type") not in {"message", "reasoning"}:
            fail("UNSUPPORTED_MODEL_OUTPUT")
        if message["type"] == "reasoning":
            continue
        if message.get("role") != "assistant" or not isinstance(message.get("content"), list):
            fail("MALFORMED_MODEL_RESPONSE")
        if message.get("tool_calls") or message.get("function_call"):
            fail("UNSUPPORTED_MODEL_OUTPUT")
        for part in message["content"]:
            if isinstance(part, dict) and part.get("type") == "refusal":
                fail("MODEL_REFUSED")
            if not isinstance(part, dict) or part.get("type") != "output_text" or not isinstance(part.get("text"), str):
                fail("UNSUPPORTED_MODEL_OUTPUT")
            texts.append(part["text"])
    if len(texts) != 1:
        fail("MALFORMED_STRUCTURED_OUTPUT")
    return texts[0]


def complete(config, *, system, context, schema, schema_name, environ, timeout,
             max_output_tokens=MAX_OUTPUT_TOKENS, max_text_chars=16000, transport=http):
    started = time.monotonic()
    metadata = {**config.provenance(), "model": None, "response_id": None, "usage": None}
    def fail(code):
        raise ModelTransportError(code, metadata=metadata)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 30 or type(max_output_tokens) is not int or not 1 <= max_output_tokens <= MAX_OUTPUT_TOKENS:
        fail("INVALID_MODEL_BUDGET")
    messages = [{"role":"system", "content":system}, {"role":"user", "content":json.dumps(redact(context, environ), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)}]
    if config.protocol == "responses":
        body = {"model":config.model, "store":False, "max_output_tokens":max_output_tokens, "input":messages,
                "text":{"format":{"type":"json_schema", "name":schema_name, "strict":True, "schema":schema}}}
    else:
        body = {"model":config.model, "messages":messages, "stream":False, "n":1,
                "reasoning_effort":"none", "max_tokens":max_output_tokens,
                "response_format":{"type":"json_schema", "json_schema":{"name":schema_name, "strict":True, "schema":schema}}}
    raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    metadata.update(request_bytes=len(raw), request_sha256=hashlib.sha256(raw).hexdigest())
    if len(raw) > MAX_REQUEST_BYTES:
        fail("MODEL_REQUEST_TOO_LARGE")
    headers = {"Content-Type":"application/json"}
    if config.key:
        headers["Authorization"] = "Bearer " + config.key
    request = Request(config.endpoint, data=raw, method="POST", headers=headers)
    remaining = timeout - (time.monotonic() - started)
    if remaining <= 0:
        fail("MODEL_TIMEOUT")
    try:
        # Audit the exact final bytes after Request construction. Mode comes
        # from trusted process configuration, never the caller's environ map.
        from .held_out import HeldOutError, guard_request
        try:
            guard_request(request, config, max_output_tokens)
        except HeldOutError as exc:
            fail(exc.code)
        response = transport(request, remaining)
    except ModelTransportError as exc:
        if exc.response is not None:
            metadata.update(_metadata(exc.response, config, environ))
        raise ModelTransportError(exc.code, metadata={**metadata, **exc.metadata}) from None
    except HTTPError as exc:
        exc.close()
        fail("MODEL_HTTP_" + str(exc.code))
    except TimeoutError:
        fail("MODEL_TIMEOUT")
    except (OSError, URLError, ValueError):
        fail("MODEL_TRANSPORT_ERROR")
    metadata.update(_metadata(response, config, environ))
    if time.monotonic() - started > timeout:
        fail("MODEL_TIMEOUT")
    if isinstance(response, dict) and response.get("usage") is not None:
        usage = response["usage"]
        names = ("input_tokens", "output_tokens", "total_tokens") if config.protocol == "responses" else ("prompt_tokens", "completion_tokens", "total_tokens")
        if not isinstance(usage, dict) or any(type(usage[name]) is not int or usage[name] < 0 for name in names if name in usage):
            fail("MALFORMED_MODEL_USAGE")
    content = _content(response, config, metadata)
    if not isinstance(content, str) or not content.strip() or len(content) > max_text_chars:
        fail("MALFORMED_STRUCTURED_OUTPUT")
    content = redact(content, environ)
    try:
        json_object(content)
    except (TypeError, ValueError):
        fail("MALFORMED_STRUCTURED_OUTPUT")
    result = {**metadata, "plan_text":content}
    from .held_out import HeldOutError, record_response
    try:
        record_response(result)
    except HeldOutError as exc:
        fail(exc.code)
    return result


if __name__ == "__main__" and sys.argv[1:] == ["--http-worker"]:
    _http_worker()
