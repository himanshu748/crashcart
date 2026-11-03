"""Fail-closed, run-bound held-out model input boundary.

The policy contains only permitted inputs and freeze commitments. The reviewer
seed/answer/source envelope must never be available to this process. This is a
trusted-process boundary, not a sandbox against arbitrary Python execution.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from .invariant import DEFAULT_INVARIANT
from .store import canonical

NEUTRAL_PROMISE = "USD 29.00 buys exactly one workshop ticket within 60 seconds of completed payment."
CONTEXT_FIELDS = {"input_version", "invariant", "run_id", "fixture_id", "proof_mode",
                  "untrusted_promise", "untrusted_observations", "prior_plans", "available_evidence_ids"}
FORBIDDEN_FIELDS = {"seed", "private_seed", "expected_answer", "expected_verdict", "final_verdict",
                    "verdict", "fault", "fault_schedule", "defect_source", "merchant_variant"}
# Known leakage forms, not a claim that arbitrary natural-language leakage can
# be decided automatically. Actual inputs also require independent human review.
LEAK_TEXT = re.compile(r"\b(?:PASS|FAIL|INCONCLUSIVE)\b|promise\s+(?:kept|broken)|"
                       r"more evidence needed|response_loss|process_interrupt|event_delay|"
                       r"event_duplicate|paid_without_ticket|ticket_delivered_once_on_time|"
                       r"seeded defect|expected[_ ](?:answer|verdict)|recovery (?:enabled|disabled)|"
                       r"(?:private|selected)[_ ]seed|defect[_ ]source|crashcart/[^\s]+\.py", re.I)


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def audit_context(context, *, run_id, customer_event_ids, forbidden_values=(),
                  validated_prior_plans=(), validated_fault_observations=()):
    """Return defects without editing inputs. Customer IDs need reviewer provenance.

    Prior plans and proposals require separately validated receipt matches.
    Known-cue scanning supplements independent review; it is not semantic proof.
    """
    from .investigator import PROMPT_VERSION

    issues = []
    if not isinstance(context, dict) or set(context) != CONTEXT_FIELDS:
        return [{"path": "$", "reason": "Unexpected model context fields"}]
    if context["run_id"] != run_id or context["fixture_id"] != "workshop-v1":
        issues.append({"path": "$.run_id", "reason": "Unexpected run or registered fixture"})
    try:
        invariant_matches = canonical(context["invariant"]) == canonical(dict(DEFAULT_INVARIANT))
    except (TypeError, ValueError):
        invariant_matches = False
    if context["input_version"] != PROMPT_VERSION or not invariant_matches:
        issues.append({"path": "$.invariant", "reason": "Changed investigator input or invariant"})
    if context["proof_mode"] not in {"LOCAL_TEST", "LIVE_SANDBOX", "FRESH_SANDBOX"}:
        issues.append({"path": "$.proof_mode", "reason": "Unsupported investigation proof mode"})

    def inspect(value, path):
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    issues.append({"path": path, "reason": "Non-string external JSON key"})
                    continue
                if key in FORBIDDEN_FIELDS:
                    issues.append({"path": path + "." + key, "reason": "Reviewer-only or verdict field"})
                # External JSON keys can carry the same answer or private
                # material as values. Audit both without rewriting either.
                inspect(key, path + ".<key>")
                inspect(item, path + "." + key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                inspect(item, path + f"[{index}]")
        elif isinstance(value, str):
            if LEAK_TEXT.search(value):
                issues.append({"path": path, "reason": "Known answer or fixture cue"})
            if any(marker and marker in value for marker in forbidden_values):
                issues.append({"path": path, "reason": "Reviewer-only canary or source path"})

    if canonical(context["prior_plans"]) != canonical(list(validated_prior_plans)):
        issues.append({"path": "$.prior_plans", "reason": "No matching validated model receipts"})
    inspect(context["untrusted_promise"], "$.untrusted_promise")
    observations = context["untrusted_observations"]
    if not isinstance(observations, dict):
        issues.append({"path": "$.untrusted_observations", "reason": "Expected observation object"})
        return issues
    # An exemption requires an actual validated model/tool receipt, not a label.
    for tool, observation in observations.items():
        if tool not in {"read_provider", "read_merchant", "read_browser", "propose_fault"}:
            issues.append({"path": "$.untrusted_observations." + tool, "reason": "Unexpected tool output"})
        if tool == "propose_fault":
            if canonical(observation) not in {canonical(item) for item in validated_fault_observations}:
                issues.append({"path": "$.untrusted_observations.propose_fault", "reason": "No matching validated proposal receipt"})
        else:
            inspect(observation, "$.untrusted_observations." + tool)
    browser = observations.get("read_browser", {}).get("data", {})
    if browser.get("known") is True and not browser.get("observations"):
        issues.append({"path": "$.untrusted_observations.read_browser", "reason": "Missing customer observation"})
    for index, observation in enumerate(browser.get("observations", [])):
        path = f"$.untrusted_observations.read_browser.data.observations[{index}]"
        if observation.get("id") not in customer_event_ids:
            issues.append({"path": path + ".id", "reason": "No reviewer-approved customer-only provenance"})
        if observation.get("visible_text_available") is not True:
            issues.append({"path": path, "reason": "Customer text unavailable for leakage review"})
    return issues



class HeldOutError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code, self.metadata = code, {}


_ACTIVE = ContextVar("crashcart_held_out_request", default=None)
ROOT = Path(__file__).resolve().parents[1]
POLICY_VERSION = "held-out-policy-v1"
POLICY_FIELDS = {"version", "run_id", "purchase_id", "order_id", "fixture_id", "proof_mode",
                 "neutral_promise", "invariant", "budget", "model_configuration", "input_version",
                 "system_sha256", "schema_sha256", "schema_name", "max_output_tokens", "source_hashes",
                 "customer_receipts", "response_model"}


def evaluation_required():
    """Trusted launch configuration, never a request/run/model supplied switch."""
    mode = os.environ.get("CRASHCART_EVALUATION_MODE", "ordinary")
    if mode not in {"ordinary", "held_out"}:
        raise HeldOutError("HELD_OUT_INVALID_PROCESS_MODE")
    # A half-configured launch must not quietly become an ordinary process.
    if mode == "ordinary" and any(os.environ.get(key) for key in
            ("CRASHCART_HELD_OUT_POLICY", "CRASHCART_HELD_OUT_POLICY_SHA256")):
        raise HeldOutError("HELD_OUT_INVALID_PROCESS_MODE")
    return mode == "held_out"


def source_hashes():
    """All executable runtime sources and pinned dependencies, not a selected defect."""
    paths = sorted([*ROOT.joinpath("crashcart").glob("*.py"), *ROOT.joinpath("migrations").glob("*.sql"),
                    ROOT / "requirements.txt", ROOT / ".python-version"])
    return {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}


def _checked_json(raw):
    from .model_transport import json_object
    try:
        return json_object(raw)
    except (TypeError, ValueError):
        raise HeldOutError("HELD_OUT_POLICY_INVALID") from None


def _read_policy(path, digest):
    try:
        # Refuse symlinks and writable/shared policy files. The out-of-band
        # digest is the immutable binding, including if the owner replaces it.
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o400:
                raise HeldOutError("HELD_OUT_POLICY_PERMISSIONS")
            raw = handle.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != digest:
            raise HeldOutError("HELD_OUT_POLICY_HASH_MISMATCH")
        policy = _checked_json(raw)
        if set(policy) != POLICY_FIELDS or policy["version"] != POLICY_VERSION:
            raise HeldOutError("HELD_OUT_POLICY_INVALID")
        strings = ("run_id", "purchase_id", "fixture_id", "proof_mode", "neutral_promise", "input_version",
                   "system_sha256", "schema_sha256", "schema_name", "response_model")
        model = policy["model_configuration"]
        if (any(not isinstance(policy[key], str) or not policy[key] for key in strings) or
                policy["order_id"] is not None and not isinstance(policy["order_id"], str) or
                any(not isinstance(policy[key], dict) for key in ("invariant", "budget", "source_hashes")) or
                not isinstance(model, dict) or set(model) != {"provider", "protocol", "endpoint_origin", "endpoint", "configured_model"} or
                any(not isinstance(value, str) or not value for value in model.values())):
            raise HeldOutError("HELD_OUT_POLICY_INVALID")
        return policy
    except (OSError, TypeError, ValueError):
        raise HeldOutError("HELD_OUT_POLICY_UNAVAILABLE") from None


class HeldOutGate:
    """One execution's validated receipts; nothing here is model-visible policy."""
    @classmethod
    def for_run(cls, store, run_id):
        if not evaluation_required():
            return None
        path = os.environ.get("CRASHCART_HELD_OUT_POLICY")
        digest = os.environ.get("CRASHCART_HELD_OUT_POLICY_SHA256", "")
        if not path or not Path(path).is_absolute() or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise HeldOutError("HELD_OUT_POLICY_REQUIRED")
        return cls(store, run_id, path, digest)

    def __init__(self, store, run_id, path, digest):
        self.store, self.run_id, self.path, self.digest = store, run_id, path, digest
        # Keep the policy as serialized immutable bytes, detached from callers.
        self._policy = canonical(_read_policy(path, digest))
        self._plans, self._observations, self._response, self._evidence_ids = [], {}, None, []
        self._expected_context, self._attempt_id = None, None
        self.check_binding()
        bindings = [e for e in self.store.get_events(self.run_id) if e["source"] == "investigator" and e["event_type"] == "held_out_policy_bound"]
        if not bindings:
            self.store.record_event(self.run_id, "investigator", "held_out_policy_bound",
                {"policy_sha256": self.digest}, purchase_id=self.policy["purchase_id"])

    @property
    def policy(self):
        return json.loads(self._policy)

    def check_binding(self):
        from .investigator import SYSTEM, MODEL_PLAN_SCHEMA, PROMPT_VERSION, MAX_OUTPUT_TOKENS
        p = self.policy
        for event in self.store.get_events(self.run_id):
            if event["source"] != "investigator":
                continue
            if event["event_type"] == "held_out_policy_bound" and event["payload"] != {"policy_sha256": self.digest}:
                raise HeldOutError("HELD_OUT_RUN_POLICY_CHANGED")
            if (event["event_type"] == "investigation_ended" and
                    str(event["payload"].get("reason", "")).startswith("HELD_OUT_")):
                raise HeldOutError("HELD_OUT_TRIAL_ALREADY_REJECTED")
        if canonical(_read_policy(self.path, self.digest)) != self._policy:
            raise HeldOutError("HELD_OUT_POLICY_CHANGED")
        if not evaluation_required():
            raise HeldOutError("HELD_OUT_PROCESS_MODE_CHANGED")
        run = self.store.get_run(self.run_id)
        purchase = self.store.purchase_for_run(self.run_id)
        expected = {"run_id": run["id"], "purchase_id": purchase["id"], "order_id": purchase["order_id"],
                    "fixture_id": run["fixture_id"], "proof_mode": run["mode"], "neutral_promise": run["promise"],
                    "invariant": run["invariant"], "budget": run["budget"]}
        if any(canonical(p[key]) != canonical(value) for key, value in expected.items()):
            raise HeldOutError("HELD_OUT_RUN_BINDING_MISMATCH")
        if p["neutral_promise"] != NEUTRAL_PROMISE or canonical(p["invariant"]) != canonical(dict(DEFAULT_INVARIANT)):
            raise HeldOutError("HELD_OUT_INVARIANT_OR_PROMISE_CHANGED")
        if (p["input_version"] != PROMPT_VERSION or p["system_sha256"] != sha(SYSTEM) or
                p["schema_sha256"] != sha(MODEL_PLAN_SCHEMA) or p["schema_name"] != "crashcart_investigator_wire_v4" or
                type(p["max_output_tokens"]) is not int or p["max_output_tokens"] != MAX_OUTPUT_TOKENS or
                p["source_hashes"] != source_hashes()):
            raise HeldOutError("HELD_OUT_FREEZE_DRIFT")
        self.customer_events()

    def customer_events(self):
        p = self.policy
        receipts = p["customer_receipts"]
        if not isinstance(receipts, list) or not 1 <= len(receipts) <= 5:
            raise HeldOutError("HELD_OUT_CUSTOMER_RECEIPT_REQUIRED")
        all_events = {event["id"]: event for event in self.store.get_events(self.run_id)}
        approved, seen = [], set()
        for receipt in receipts:
            if not isinstance(receipt, dict) or set(receipt) != {"event", "event_sha256", "receipt_path", "receipt_sha256"}:
                raise HeldOutError("HELD_OUT_CUSTOMER_RECEIPT_INVALID")
            event = receipt["event"]
            if not isinstance(event, dict) or not isinstance(event.get("payload"), dict):
                raise HeldOutError("HELD_OUT_CUSTOMER_RECEIPT_INVALID")
            event_id, payload = event.get("id"), event["payload"]
            if (not isinstance(event_id, str) or event_id in seen or event_id not in all_events or
                    sha(event) != receipt["event_sha256"] or canonical(all_events[event_id]) != canonical(event)):
                raise HeldOutError("HELD_OUT_CUSTOMER_RECEIPT_CHANGED")
            seen.add(event_id)
            if (event.get("run_id") != self.run_id or event.get("purchase_id") != p["purchase_id"] or
                    event.get("order_id") != p["order_id"] or event.get("source") != "browser" or
                    payload.get("url_path") not in {"/checkout", "/ticket"} or
                    not isinstance(payload.get("visible_text"), str) or not payload["visible_text"].strip() or
                    len(payload["visible_text"]) > 2000):
                raise HeldOutError("HELD_OUT_CUSTOMER_IDENTITY_OR_TEXT_INVALID")
            try:
                receipt_path = Path(receipt["receipt_path"])
                if not receipt_path.is_absolute() or receipt_path.is_symlink():
                    raise OSError("invalid path")
                raw = receipt_path.read_bytes()
                if hashlib.sha256(raw).hexdigest() != receipt["receipt_sha256"]:
                    raise OSError("changed receipt")
            except (OSError, TypeError, ValueError):
                raise HeldOutError("HELD_OUT_CUSTOMER_SOURCE_CHANGED") from None
            if payload.get("receipt_sha256") not in (None, receipt["receipt_sha256"]):
                raise HeldOutError("HELD_OUT_CUSTOMER_SOURCE_CHANGED")
            # Scan the complete saved event, not just its projected text.
            context = self._empty_context()
            context["untrusted_observations"] = {"read_browser": {"evidence_id": event_id,
                "data": {"known": True, "observations": [{**event, "visible_text_available": True}]}}}
            if audit_context(context, run_id=self.run_id, customer_event_ids={event_id}):
                raise HeldOutError("HELD_OUT_CUSTOMER_INPUT_REJECTED")
            approved.append(deepcopy(event))
        return approved

    def _empty_context(self):
        p = self.policy
        return {"input_version": p["input_version"], "invariant": p["invariant"], "run_id": self.run_id,
                "fixture_id": p["fixture_id"], "proof_mode": p["proof_mode"], "untrusted_promise": p["neutral_promise"],
                "untrusted_observations": {}, "prior_plans": [], "available_evidence_ids": []}

    def audit_context(self, context):
        self.check_binding()
        events = {event["id"]: event for event in self.store.get_events(self.run_id)}
        plans = []
        for event_id, serialized in self._plans:
            event = events.get(event_id)
            if not event or canonical(event) != serialized:
                raise HeldOutError("HELD_OUT_MODEL_RECEIPT_CHANGED")
            plans.append(event["payload"]["plan"])
        expected = self._empty_context()
        expected["prior_plans"] = plans
        expected["untrusted_observations"] = {tool: json.loads(value[1]) for tool, value in self._observations.items()}
        # The runtime retains all observation IDs, including superseded reads.
        expected["available_evidence_ids"] = list(self._evidence_ids)
        for event_id, _, serialized in self._observations.values():
            if event_id not in events or canonical(events[event_id]) != serialized:
                raise HeldOutError("HELD_OUT_TOOL_RECEIPT_CHANGED")
        if canonical(context) != canonical(expected):
            raise HeldOutError("HELD_OUT_UNLINKED_CONTEXT")
        proposals = [expected["untrusted_observations"]["propose_fault"]] if "propose_fault" in self._observations else []
        if audit_context(context, run_id=self.run_id, customer_event_ids={e["id"] for e in self.customer_events()},
                         validated_prior_plans=plans, validated_fault_observations=proposals):
            raise HeldOutError("HELD_OUT_INPUT_REJECTED")

    @contextmanager
    def request_scope(self, context, attempt_id):
        self.audit_context(context)
        attempts = {a["id"]: a for a in self.store.get_attempts(self.run_id)}
        attempt = attempts.get(attempt_id)
        if not attempt or attempt["kind"] != "investigator.model" or attempt["state"] != "RUNNING":
            raise HeldOutError("HELD_OUT_MODEL_RESERVATION_REQUIRED")
        reserved = dict(attempt["input"])
        provenance = reserved.pop("model_configuration", None)
        expected_provenance = {k: v for k, v in self.policy["model_configuration"].items() if k != "endpoint"}
        if canonical(reserved) != canonical(context) or canonical(provenance) != canonical(expected_provenance):
            raise HeldOutError("HELD_OUT_MODEL_RESERVATION_CHANGED")
        self._expected_context, self._attempt_id = canonical(context), attempt_id
        self._response = None
        token = _ACTIVE.set(self)
        try:
            yield
        finally:
            _ACTIVE.reset(token)
            self._expected_context = None

    def accept_response(self, response):
        if self._expected_context is None:
            raise HeldOutError("HELD_OUT_REQUEST_SCOPE_REQUIRED")
        # Input bindings and prior receipts can change while HTTP is in flight.
        # Validate them before any returned plan, including finish, is accepted.
        self.audit_context(json.loads(self._expected_context))
        if response.get("model") != self.policy["response_model"]:
            raise HeldOutError("HELD_OUT_RESPONSE_MODEL_CHANGED")
        self._response = canonical(response)

    def audit_current_receipts(self):
        """Revalidate the terminal state before a deterministic outcome is accepted."""
        context = self._empty_context()
        context["prior_plans"] = [json.loads(serialized)["payload"]["plan"] for _, serialized in self._plans]
        context["untrusted_observations"] = {tool: json.loads(value[1]) for tool, value in self._observations.items()}
        context["available_evidence_ids"] = list(self._evidence_ids)
        self.audit_context(context)

    def remember_plan(self, event_id, response):
        from .investigator import project_model_plan
        from .model_transport import json_object
        event = next((e for e in self.store.get_events(self.run_id) if e["id"] == event_id), None)
        actual = json.loads(self._response) if self._response else None
        if (not actual or not event or event["event_type"] != "model_plan" or
                event["payload"].get("attempt_id") != self._attempt_id or
                any(actual.get(key) != response.get(key) for key in actual)):
            raise HeldOutError("HELD_OUT_MODEL_RECEIPT_REQUIRED")
        projected = project_model_plan(json_object(actual["plan_text"]), self.store.get_run(self.run_id),
                                       set(self._evidence_ids))
        if canonical(projected) != canonical(event["payload"]["plan"]):
            raise HeldOutError("HELD_OUT_MODEL_RECEIPT_CHANGED")
        self._plans.append((event_id, canonical(event)))

    def audit_tool(self, name, result, plan):
        self.check_binding()
        if name == "read_browser":
            from .investigator import browser_observation
            expected = {"known": True, "observations": [browser_observation(e) for e in self.customer_events()]}
            if canonical(result) != canonical(expected):
                raise HeldOutError("HELD_OUT_CUSTOMER_PROJECTION_CHANGED")
        if name in {"read_merchant", "read_provider"} and result.get("known") is True:
            p = self.policy
            if any(result.get(key) != p[key] for key in ("run_id", "purchase_id", "order_id")):
                raise HeldOutError("HELD_OUT_TOOL_IDENTITY_CHANGED")
        if name == "propose_fault":
            from .faults import validate_fault
            expected = {"proposal": validate_fault({k: v for k, v in plan["arguments"]["fault"].items() if v is not None},
                                                   self.policy["fixture_id"]), "executed": False, "requires_operator": True}
            if (not self._plans or json.loads(self._plans[-1][1])["payload"]["plan"] != plan or
                    canonical(result) != canonical(expected)):
                raise HeldOutError("HELD_OUT_PROPOSAL_RECEIPT_REQUIRED")
            return
        context = self._empty_context()
        context["untrusted_observations"] = {name: {"evidence_id": "pending", "data": result}}
        if audit_context(context, run_id=self.run_id, customer_event_ids={e["id"] for e in self.customer_events()}):
            raise HeldOutError("HELD_OUT_TOOL_INPUT_REJECTED")

    def remember_observation(self, name, observation, event_id):
        event = next(e for e in self.store.get_events(self.run_id) if e["id"] == event_id)
        if event["event_type"] != "tool_observation" or event["payload"]["tool"] != name:
            raise HeldOutError("HELD_OUT_TOOL_RECEIPT_REQUIRED")
        self._observations[name] = (event_id, canonical(observation), canonical(event))
        self._evidence_ids.append(event_id)

    def audit_request(self, request, config, max_output_tokens):
        from .model_transport import json_object
        self.check_binding()
        p = self.policy
        if not self._expected_context:
            raise HeldOutError("HELD_OUT_REQUEST_SCOPE_REQUIRED")
        self.audit_context(json.loads(self._expected_context))
        configuration = {**config.provenance(), "endpoint": config.endpoint, "configured_model": config.model}
        if canonical(configuration) != canonical(p["model_configuration"]):
            raise HeldOutError("HELD_OUT_MODEL_CONFIGURATION_CHANGED")
        if (request.full_url != config.endpoint or request.get_method() != "POST" or
                type(request.data) is not bytes or max_output_tokens != p["max_output_tokens"]):
            raise HeldOutError("HELD_OUT_REQUEST_CHANGED")
        try:
            body = json_object(request.data)
            messages_key = "input" if config.protocol == "responses" else "messages"
            messages = body[messages_key]
            if len(messages) != 2 or set(messages[0]) != {"role", "content"} or set(messages[1]) != {"role", "content"}:
                raise ValueError("messages")
            if (messages[0]["role"] != "system" or messages[1]["role"] != "user" or
                    sha(messages[0]["content"]) != p["system_sha256"] or
                    canonical(json_object(messages[1]["content"])) != self._expected_context):
                raise ValueError("messages")
            if config.protocol == "responses":
                expected = {"model": config.model, "store": False, "max_output_tokens": p["max_output_tokens"],
                            "input": messages, "text": {"format": {"type": "json_schema", "name": p["schema_name"],
                            "strict": True, "schema": body["text"]["format"]["schema"]}}}
                schema = body["text"]["format"]["schema"]
            else:
                schema = body["response_format"]["json_schema"]["schema"]
                expected = {"model": config.model, "messages": messages, "stream": False, "n": 1,
                    "reasoning_effort": "none", "max_tokens": p["max_output_tokens"],
                    "response_format": {"type": "json_schema", "json_schema": {"name": p["schema_name"], "strict": True, "schema": schema}}}
            if sha(schema) != p["schema_sha256"] or canonical(body) != canonical(expected):
                raise ValueError("wire")
        except (ValueError, TypeError, KeyError, IndexError):
            raise HeldOutError("HELD_OUT_FINAL_REQUEST_REJECTED") from None


def guard_request(request, config, max_output_tokens):
    gate = _ACTIVE.get()
    if gate is not None:
        gate.audit_request(request, config, max_output_tokens)
    elif evaluation_required():
        raise HeldOutError("HELD_OUT_REQUEST_SCOPE_REQUIRED")


def record_response(response):
    gate = _ACTIVE.get()
    if gate is not None:
        gate.accept_response(response)


def guard_http_request(request):
    """The shared HTTP function also refuses calls outside the bound scope."""
    gate = _ACTIVE.get()
    if gate is not None:
        from .model_transport import ModelConfig
        config = gate.policy["model_configuration"]
        gate.audit_request(request, ModelConfig(config["provider"], config["protocol"], config["endpoint_origin"],
            config["endpoint"], config["configured_model"], ""), gate.policy["max_output_tokens"])
    elif evaluation_required():
        raise HeldOutError("HELD_OUT_REQUEST_SCOPE_REQUIRED")
