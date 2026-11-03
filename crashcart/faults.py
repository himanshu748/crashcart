"""Typed plans for faults confined to the registered owned merchant fixture.

Validation and planning are pure: a returned schedule is not proof that a fault
ran. Actual activation, deactivation and observations must be recorded by the
merchant harness. Provider records and external webhook verification are never
fault targets.
"""

FIXTURE_ID = "workshop-v1"
MAX_DELAY_SECONDS = 120
KINDS = frozenset({"none", "response_loss", "event_delay", "event_duplicate", "process_interrupt"})


def validate_fault(config=None, fixture_id=FIXTURE_ID):
    if fixture_id != FIXTURE_ID:
        raise ValueError("fault target must be the registered owned sandbox fixture workshop-v1")
    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise ValueError("fault configuration must be an object")
    if set(config) - {"kind", "merchant", "delay_seconds"}:
        raise ValueError("unsupported fault fields; arbitrary targets and provider mutations are forbidden")
    kind, merchant = config.get("kind", "none"), config.get("merchant", "healthy")
    if not isinstance(kind, str) or kind not in KINDS:
        raise ValueError("unsupported fault kind")
    if not isinstance(merchant, str) or merchant not in {"healthy", "defective"}:
        raise ValueError("merchant must be healthy or defective")
    normalized = {"kind": kind, "merchant": merchant}
    if kind == "event_delay":
        delay = config.get("delay_seconds")
        if type(delay) is not int or not 1 <= delay <= MAX_DELAY_SECONDS:
            raise ValueError(f"event delay must be integer seconds between 1 and {MAX_DELAY_SECONDS}")
        normalized["delay_seconds"] = delay
    elif "delay_seconds" in config:
        raise ValueError("delay_seconds is only valid for event_delay")
    return normalized


def fault_schedule(config=None, fixture_id=FIXTURE_ID):
    """Describe the boundary the harness is allowed to affect, without executing."""
    fault = validate_fault(config, fixture_id)
    if fault["kind"] == "none":
        return []
    boundaries = {
        "response_loss": ("merchant_capture_response", "discard_response_after_provider_capture"),
        "event_delay": ("verified_fixture_event", "delay_merchant_processing"),
        "event_duplicate": ("verified_fixture_event", "repeat_merchant_processing_once"),
        "process_interrupt": ("after_payment_before_ticket", "interrupt_owned_merchant_process"),
    }
    boundary, action = boundaries[fault["kind"]]
    step = {"fixture_id": fixture_id, "merchant": fault["merchant"], "kind": fault["kind"],
            "boundary": boundary, "action": action}
    if fault["kind"] == "event_delay":
        step["delay_seconds"] = fault["delay_seconds"]
    return [step]
