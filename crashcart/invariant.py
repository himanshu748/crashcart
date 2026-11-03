"""Deterministic ticket-v1 verdicts over explicit, correlated observations.

Inputs must come from adapters. This evaluator performs no network calls and
does not establish whether its inputs are real sandbox evidence or local tests.
It never infers successful payment from a timeout, HTTP status, or model text.
"""

from datetime import datetime, timedelta, timezone
from types import MappingProxyType


DEFAULT_INVARIANT = MappingProxyType({
    "version": "ticket-v1",
    "amount": 2900,
    "currency": "USD",
    "ticket_count": 1,
    "recovery_seconds": 60,
})


def _time(value):
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        return None
    return value.astimezone(timezone.utc)


def _identity(value):
    return isinstance(value, str) and bool(value) and value == value.strip()


def evaluate(provider, merchant, now, invariant=DEFAULT_INVARIANT):
    """Evaluate normalized provider and merchant observations without side effects.

    Provider fields: confirmed, status, amount (integer minor units), currency,
    run_id, purchase_id, order_id, capture_id, capture_completed_at, observed_at.
    Merchant fields match Store.merchant_state: known, identities, observed_at,
    ticket_count, and tickets containing id, purchase_id, created_at.
    An observation made before the deadline cannot prove a later missing ticket.
    """
    if not isinstance(invariant, (dict, type(DEFAULT_INVARIANT))) or dict(invariant) != dict(DEFAULT_INVARIANT):
        raise ValueError("ticket-v1 is frozen; changing it requires a separately approved invariant")
    for name in ("amount", "ticket_count", "recovery_seconds"):
        if type(invariant[name]) is not int:
            raise ValueError("invariant numeric fields must be integer values")
    source_ids = {}
    deadline_text = None

    def result(verdict, signature, reason):
        return {"verdict": verdict, "reason": reason, "signature": signature,
                "invariant_version": invariant["version"], "source_ids": source_ids,
                "deadline": deadline_text}

    def unknown(signature, reason):
        return result("INCONCLUSIVE", signature, reason)

    current = _time(now)
    if current is None:
        return unknown("invalid_evaluation_time", "Evaluation requires an explicit timezone-aware time.")
    if not isinstance(provider, dict):
        return unknown("missing_provider_evidence", "Independent provider evidence is missing.")
    if not isinstance(merchant, dict) or merchant.get("known") is not True:
        return unknown("missing_merchant_evidence", "The merchant purchase record is missing or unknown.")
    for field in ("run_id", "purchase_id", "order_id"):
        if not _identity(provider.get(field)) or not _identity(merchant.get(field)):
            return unknown("missing_correlation_identity", f"Both observations require a valid {field}.")
        if provider[field] != merchant[field]:
            return unknown("correlation_mismatch", f"Provider and merchant {field} do not match.")
        source_ids[field] = provider[field]
    if not _identity(provider.get("capture_id")):
        return unknown("missing_capture_identity", "A confirmed capture identity is required.")
    source_ids["capture_id"] = provider["capture_id"]
    for label, observation in (("provider_observation_id", provider), ("merchant_observation_id", merchant)):
        if _identity(observation.get("observation_id")):
            source_ids[label] = observation["observation_id"]
    if provider.get("confirmed") is not True:
        return unknown("unconfirmed_payment", "Payment has not been confirmed by independent retrieval.")
    if provider.get("status") != "COMPLETED":
        return unknown("payment_not_completed", "The provider does not show a completed capture.")
    if type(provider.get("amount")) is not int or not _identity(provider.get("currency")):
        return unknown("malformed_payment", "Payment amount must be integer minor units with an explicit currency.")
    completed = _time(provider.get("capture_completed_at"))
    provider_observed = _time(provider.get("observed_at"))
    merchant_observed = _time(merchant.get("observed_at"))
    if any(value is None for value in (completed, provider_observed, merchant_observed)):
        return unknown("missing_observation_time", "Capture completion and both observation times must include timezones.")
    if any(value > current for value in (completed, provider_observed, merchant_observed)):
        return unknown("future_observation", "Evidence contains a timestamp later than the evaluation time.")
    if provider_observed < completed or merchant_observed < completed:
        return unknown("observation_precedes_payment", "The observations do not establish merchant state after payment completion.")
    deadline = completed + timedelta(seconds=invariant["recovery_seconds"])
    deadline_text = deadline.isoformat().replace("+00:00", "Z")
    count, tickets = merchant.get("ticket_count"), merchant.get("tickets")
    if type(count) is not int or count < 0 or not isinstance(tickets, list) or len(tickets) != count:
        return unknown("malformed_merchant_evidence", "Ticket count and the actual entitlement records disagree or are missing.")
    ticket_times, ticket_ids = [], []
    for ticket in tickets:
        if not isinstance(ticket, dict) or not _identity(ticket.get("id")) or ticket.get("purchase_id") != provider["purchase_id"]:
            return unknown("malformed_ticket_identity", "A ticket is missing its identity or belongs to another purchase.")
        if ticket["id"] in ticket_ids:
            return unknown("duplicated_ticket_observation", "Repeated observations of one ticket cannot establish multiple entitlements.")
        created = _time(ticket.get("created_at"))
        if created is None or created < completed or created > merchant_observed:
            return unknown("invalid_ticket_time", "A ticket lacks a valid creation time between capture and merchant observation.")
        ticket_ids.append(ticket["id"])
        ticket_times.append(created)
    source_ids["ticket_ids"] = ticket_ids
    if provider["amount"] != invariant["amount"]:
        return result("FAIL", "payment_amount_mismatch", "Confirmed capture amount does not match the fixed 2900-minor-unit purchase.")
    if provider["currency"] != invariant["currency"]:
        return result("FAIL", "payment_currency_mismatch", "Confirmed capture currency does not match the fixed USD purchase.")
    if count > invariant["ticket_count"]:
        return result("FAIL", "duplicate_tickets", "One logical paid purchase has multiple distinct tickets.")
    if count == 0:
        if current <= deadline:
            return unknown("within_recovery_window", "The fixed recovery window is still open; zero tickets is not yet a failure.")
        if merchant_observed <= deadline:
            return unknown("stale_merchant_observation", "The last merchant observation does not establish missing delivery beyond the deadline.")
        return result("FAIL", "paid_without_ticket", "Confirmed payment has zero tickets beyond the fixed recovery deadline.")
    if ticket_times[0] > deadline:
        return result("FAIL", "ticket_delivered_late", "The only ticket was created after the fixed recovery deadline.")
    return result("PASS", "ticket_delivered_once_on_time", "Confirmed exact payment has one ticket delivered within the fixed recovery window.")
