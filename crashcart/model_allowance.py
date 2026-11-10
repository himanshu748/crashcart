"""Optional, durable v1 Modal call/cost ledger. This module never sends requests.

The account owner supplies an existing reviewed ledger. Runtime code cannot
initialize/reset it, refund failures, or bypass an unresolved dispatch. Its
stable sibling .lock inode is shared with the historical allowance.json guard.
A replacement may already be visible if the following directory fsync fails.
That failure still raises; either recoverable state remains charged: the prior
RESERVED entry or the installed completion metadata. No failed write refunds it.
"""

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import uuid

from .model_ids import DEEPSEEK_MODEL_ID as MODEL

CALL_LIMIT = 24
CEILING_MICRO_USD = 1_000_000
RESERVATION_MICRO_USD = 40_000
MAX_REQUEST_BYTES = 65_536
MAX_LEDGER_BYTES = 4 * 1024 * 1024
LOCK_TIMEOUT_SECONDS = 2.0


class ModelAllowanceError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Reservation:
    call: int
    request_sha256: str
    reservation_id: str
    _path: str = field(repr=False)
    _started: float = field(repr=False)
    _credential: str = field(repr=False)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate field")
            result[key] = value
        return result

    def invalid(_):
        raise ValueError("nonfinite JSON")

    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def _timestamp(value):
    if not isinstance(value, str) or len(value) > 80:
        raise ValueError("timestamp")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("timezone")


def _cost(value):
    if type(value) not in {int, float} or not math.isfinite(value) or not 0 <= value < 1e12:
        raise ValueError("cost")
    return Decimal(str(value))


def _usage(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("usage")
    counts = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        if key in value:
            count = value[key]
            if type(count) is not int or not 0 <= count < 10**12:
                raise ValueError("tokens")
            counts[key] = count
    return counts or None


def _validate(state):
    try:
        if (
            type(state) is not dict
            or type(state.get("version")) is not int
            or state["version"] != 1
            or type(state.get("call_limit")) is not int
            or state["call_limit"] != CALL_LIMIT
            or type(state.get("ceiling_micro_usd")) is not int
            or state["ceiling_micro_usd"] != CEILING_MICRO_USD
            or type(state.get("calls")) is not list
            or len(state["calls"]) > CALL_LIMIT
        ):
            raise ValueError("ledger")
        for index, call in enumerate(state["calls"], 1):
            if (
                type(call) is not dict
                or type(call.get("call")) is not int
                or call["call"] != index
                or call.get("state") not in {"RESERVED", "RESPONDED", "ERROR"}
                or type(call.get("reserved_micro_usd")) is not int
                or call["reserved_micro_usd"] != RESERVATION_MICRO_USD
                or not isinstance(call.get("request_sha256"), str)
                or not re.fullmatch(r"[a-f0-9]{64}", call["request_sha256"])
                or type(call.get("request_bytes")) is not int
                or not 0 < call["request_bytes"] <= MAX_REQUEST_BYTES
            ):
                raise ValueError("entry")
            _timestamp(call.get("started_at"))
            _cost(call.get("observed_rate_cost_micro_usd", 0))
            if "reservation_id" in call and (
                not isinstance(call["reservation_id"], str) or not re.fullmatch(r"[a-f0-9]{32}", call["reservation_id"])
            ):
                raise ValueError("reservation")
            if call["state"] != "RESERVED" or "finished_at" in call:
                _timestamp(call.get("finished_at"))
            if call["state"] != "RESERVED" or "duration_seconds" in call:
                duration = call.get("duration_seconds")
                if type(duration) not in {int, float} or not math.isfinite(duration) or duration < 0:
                    raise ValueError("duration")
            if "usage" in call:
                _usage(call["usage"])
            for key in ("response_id", "model", "error"):
                if (
                    key in call
                    and call[key] is not None
                    and (
                        not isinstance(call[key], str)
                        or len(call[key]) > 200
                        or any(ord(char) < 32 for char in call[key])
                    )
                ):
                    raise ValueError("metadata")
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ModelAllowanceError("MODEL_ALLOWANCE_CORRUPT") from None


def _path(value):
    try:
        path = Path(value)
        if not path.is_absolute() or path.name in {"", ".", ".."}:
            raise ValueError("absolute ledger path required")
        return path
    except (TypeError, ValueError):
        raise ModelAllowanceError("MODEL_ALLOWANCE_PATH_INVALID") from None


def _private_file(info):
    return (
        stat.S_ISREG(info.st_mode)
        and stat.S_IMODE(info.st_mode) == 0o600
        and info.st_uid == os.getuid()
        and info.st_nlink == 1
    )


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def _locked(path, lock_timeout=None):
    wait = LOCK_TIMEOUT_SECONDS if lock_timeout is None else lock_timeout
    if type(wait) not in {int, float} or not math.isfinite(wait) or wait <= 0:
        raise ModelAllowanceError("MODEL_ALLOWANCE_LOCKED")
    wait = min(wait, LOCK_TIMEOUT_SECONDS)
    lock = path.with_suffix(".lock")
    if lock == path:
        raise ModelAllowanceError("MODEL_ALLOWANCE_PATH_INVALID")
    fd = None
    try:
        parent = path.parent.stat()
        if (
            not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.getuid()
            or stat.S_IMODE(parent.st_mode) & 0o022
            or path.parent.is_symlink()
        ):
            raise ModelAllowanceError("MODEL_ALLOWANCE_PERMISSIONS")
        fd = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        if not _private_file(os.fstat(fd)):
            raise ModelAllowanceError("MODEL_ALLOWANCE_PERMISSIONS")
        deadline = time.monotonic() + wait
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise ModelAllowanceError("MODEL_ALLOWANCE_LOCKED") from None
                time.sleep(0.01)
        try:
            ledger_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            raise ModelAllowanceError("MODEL_ALLOWANCE_MISSING") from None
        with os.fdopen(ledger_fd, "rb") as handle:
            if not _private_file(os.fstat(handle.fileno())):
                raise ModelAllowanceError("MODEL_ALLOWANCE_PERMISSIONS")
            raw = handle.read(MAX_LEDGER_BYTES + 1)
        if len(raw) > MAX_LEDGER_BYTES:
            raise ModelAllowanceError("MODEL_ALLOWANCE_CORRUPT")
        try:
            state = _json(raw)
        except (ValueError, TypeError, RecursionError):
            raise ModelAllowanceError("MODEL_ALLOWANCE_CORRUPT") from None
        _validate(state)
        yield state
    except OSError:
        raise ModelAllowanceError("MODEL_ALLOWANCE_UNAVAILABLE") from None
    finally:
        if fd is not None:
            os.close(fd)


def _write(path, state):
    _validate(state)
    temporary = None
    try:
        raw = (json.dumps(state, indent=2, allow_nan=False) + "\n").encode()
        if len(raw) > MAX_LEDGER_BYTES:
            raise ModelAllowanceError("MODEL_ALLOWANCE_CORRUPT")
        fd, temporary = tempfile.mkstemp(prefix=".allowance-", dir=path.parent)
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), 0o600)
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _sync_directory(path.parent)
    except (ValueError, TypeError, OverflowError):
        raise ModelAllowanceError("MODEL_ALLOWANCE_CORRUPT") from None
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass


def _request(request, expected_origin, expected_model):
    label = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    if (
        not isinstance(expected_origin, str)
        or not re.fullmatch(rf"https://(?:{label}\.modal\.run|{label}\.{label}\.modal\.direct)", expected_origin)
        or expected_model != MODEL
        or request.get_method() != "POST"
        or request.full_url != expected_origin + "/v1/chat/completions"
    ):
        raise ModelAllowanceError("MODEL_ALLOWANCE_DESTINATION_REJECTED")
    raw = request.data
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_REQUEST_BYTES:
        raise ModelAllowanceError("MODEL_ALLOWANCE_REQUEST_REJECTED")
    try:
        body = _json(raw)
        if (
            type(body) is not dict
            or set(body) - {"model", "messages", "n", "max_tokens", "stream", "reasoning_effort", "response_format"}
            or body.get("model") != expected_model
            or type(body.get("messages")) is not list
            or len(body["messages"]) != 2
            or any(
                type(message) is not dict
                or set(message) != {"role", "content"}
                or message["role"] != role
                or not isinstance(message["content"], str)
                for message, role in zip(body["messages"], ("system", "user"))
            )
            or type(body.get("n")) is not int
            or body["n"] != 1
            or type(body.get("max_tokens")) is not int
            or not 1 <= body["max_tokens"] <= 1024
            or body.get("stream") is not False
            or body.get("reasoning_effort") != "none"
        ):
            raise ValueError("wire limits")
    except (ValueError, TypeError, RecursionError):
        raise ModelAllowanceError("MODEL_ALLOWANCE_REQUEST_REJECTED") from None
    credential = request.get_header("Authorization", "")
    credential = credential.removeprefix("Bearer ") if isinstance(credential, str) else ""
    return raw, credential


def reserve(path, request, *, expected_origin, expected_model, lock_timeout=None):
    """Reserve before dispatch, using trusted configured origin/model, not caller input.

    A single unresolved reservation anywhere in the existing history blocks new
    dispatch. No initialization, reset, refund, retry or provider call occurs.
    """
    raw, credential = _request(request, expected_origin, expected_model)
    path = _path(path)
    digest, identity = hashlib.sha256(raw).hexdigest(), uuid.uuid4().hex
    with _locked(path, lock_timeout) as state:
        if any(call["state"] == "RESERVED" for call in state["calls"]):
            raise ModelAllowanceError("MODEL_ALLOWANCE_UNRESOLVED")
        spent = Decimal(0)
        for call in state["calls"]:
            usage = _usage(call.get("usage")) or {}
            # Preserve historical entries, but never undercount known usage if
            # a legacy cost field is absent or lower than its reported tokens.
            derived = Decimal(usage.get("prompt_tokens", 0)) * Decimal(".30") + Decimal(
                usage.get("completion_tokens", 0)
            ) * Decimal("1.20")
            spent += max(Decimal(RESERVATION_MICRO_USD), _cost(call.get("observed_rate_cost_micro_usd", 0)), derived)
        if len(state["calls"]) >= CALL_LIMIT or spent + RESERVATION_MICRO_USD > CEILING_MICRO_USD:
            raise ModelAllowanceError("MODEL_ALLOWANCE_EXHAUSTED")
        index = len(state["calls"]) + 1
        state["calls"].append(
            {
                "call": index,
                "state": "RESERVED",
                "started_at": _now(),
                "request_sha256": digest,
                "request_bytes": len(raw),
                "reserved_micro_usd": RESERVATION_MICRO_USD,
                "reservation_id": identity,
            }
        )
        _write(path, state)
    return Reservation(index, digest, identity, str(path), time.monotonic(), credential)


def _identifier(value, credential):
    if (
        isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}", value)
        and not (credential and credential in value)
    ):
        return value
    return None


def finish(path, reservation, *, response=None, error=None, lock_timeout=None):
    """Record only completion metadata. Every dispatched error consumes its reservation.

    A failure before replacement leaves RESERVED intact and blocks subsequent
    calls. A directory-fsync failure after replacement raises even though the
    installed completion may already be visible. Its reservation/observed cost
    stays charged; crash recovery may retain that completion or prior RESERVED
    state. Never use this to clear a historical unknown reservation: it requires
    the object returned by this invocation.
    """
    path = _path(path)
    if (
        not isinstance(reservation, Reservation)
        or str(path) != reservation._path
        or type(reservation.call) is not int
        or not 1 <= reservation.call <= CALL_LIMIT
    ):
        raise ModelAllowanceError("MODEL_ALLOWANCE_RESERVATION_MISMATCH")
    if response is None and error is not None:
        response = getattr(error, "response", None)
    duration = time.monotonic() - reservation._started
    if not math.isfinite(duration) or duration < 0:
        raise ModelAllowanceError("MODEL_ALLOWANCE_RESERVATION_MISMATCH")
    summary = {
        "state": "ERROR" if error is not None else "RESPONDED",
        "finished_at": _now(),
        "duration_seconds": duration,
    }
    if error is not None:
        code = getattr(error, "code", "")
        summary["error"] = (
            code
            if isinstance(code, str)
            and re.fullmatch(r"MODEL_(?:HTTP_[0-9]{3}|TIMEOUT|TRANSPORT_ERROR|RESPONSE_TOO_LARGE)", code)
            else "CALL_ERROR"
        )
    if isinstance(response, dict):
        summary.update(
            response_id=_identifier(response.get("id"), reservation._credential),
            model=_identifier(response.get("model"), reservation._credential),
        )
        try:
            usage = _usage(response.get("usage"))
            summary["usage"] = usage
            if usage and "prompt_tokens" in usage and "completion_tokens" in usage:
                cost = Decimal(usage["prompt_tokens"]) * Decimal(".30") + Decimal(usage["completion_tokens"]) * Decimal(
                    "1.20"
                )
                summary["observed_rate_cost_micro_usd"] = int(cost) if cost == cost.to_integral_value() else float(cost)
                _cost(summary["observed_rate_cost_micro_usd"])
        except (ValueError, OverflowError):
            raise ModelAllowanceError("MODEL_ALLOWANCE_USAGE_INVALID") from None
    with _locked(path, lock_timeout) as state:
        try:
            entry = state["calls"][reservation.call - 1]
        except (IndexError, TypeError):
            raise ModelAllowanceError("MODEL_ALLOWANCE_RESERVATION_MISMATCH") from None
        if (
            entry["call"] != reservation.call
            or entry["request_sha256"] != reservation.request_sha256
            or entry.get("reservation_id") != reservation.reservation_id
        ):
            raise ModelAllowanceError("MODEL_ALLOWANCE_RESERVATION_MISMATCH")
        if entry["state"] != "RESERVED":
            raise ModelAllowanceError("MODEL_ALLOWANCE_ALREADY_FINISHED")
        entry.update(summary)
        _write(path, state)
    return summary
