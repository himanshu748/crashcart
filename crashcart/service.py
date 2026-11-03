"""Owned merchant operations with durable journals and independent reconciliation.

The provider adapter never falls back to a stub. Tests inject explicitly local
transports. Response-loss evidence belongs to the harness, not merchant state.
"""
from datetime import datetime, timezone
import os
from urllib.parse import urlencode, urlparse

from .paypal import PayPalSandbox, PayPalError, approval_url, inspect_capture, validate_capture
from .faults import validate_fault
from .invariant import evaluate
from .store import utcnow


def instant(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class MerchantService:
    def __init__(self, store, provider_factory=PayPalSandbox):
        self.store = store
        self.provider_factory = provider_factory

    def context(self, run_id):
        run = self.store.get_run(run_id)
        if not run:
            raise ValueError("Unknown run")
        if run["cancel_requested"] or run["state"] == "cancelled":
            raise ValueError("Run is cancelled; evidence is read-only")
        fault = validate_fault(run["fault"], fixture_id=run["fixture_id"])
        return run, self.store.purchase_for_run(run_id), fault

    def provider(self, run):
        if run["mode"] not in {"LIVE_SANDBOX", "FRESH_SANDBOX"}:
            raise ValueError("This mode cannot contact PayPal. Recorded replay has no live fallback.")
        return self.provider_factory()

    def event(self, run, purchase, source, kind, payload, operation=None, event_time=None):
        return self.store.record_event(run["id"], source, kind, payload,
            purchase_id=purchase["id"], order_id=purchase.get("order_id"),
            operation_id=operation["id"] if operation else None, event_time=event_time)

    def retry_window(self, operation):
        if (datetime.now(timezone.utc) - instant(operation["created_at"])).total_seconds() >= 6 * 3600:
            raise ValueError("Six-hour request-ID retention budget expired; reconcile existing order. No new payment operation was created.")

    def create_order(self, run_id):
        run, purchase, fault = self.context(run_id)
        provider = self.provider(run)
        if purchase.get("order_id"):
            order = provider.get_order(purchase["order_id"])
            if order.get("status") == "COMPLETED":
                return {"order_id": purchase["order_id"], "approval_url": None, "reconciliation": self.reconcile(run_id)}
            return {"order_id": purchase["order_id"], "approval_url": approval_url(order)}
        base = os.environ.get("CRASHCART_PUBLIC_URL", "http://127.0.0.1:8765").rstrip("/")
        parsed = urlparse(base)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("Valid configured CRASHCART_PUBLIC_URL required")
        query = urlencode({"run": run_id})
        body = {"intent": "CAPTURE", "purchase_units": [{"reference_id": purchase["id"], "custom_id": purchase["id"],
            "description": "Resilient systems workshop ticket", "amount": {"currency_code": "USD", "value": "29.00"}}],
            "payment_source": {"paypal": {"experience_context": {"shipping_preference": "NO_SHIPPING", "user_action": "PAY_NOW",
                "return_url": base + "/return?" + query, "cancel_url": base + "/cancel?" + query}}}}
        operation = self.store.operation(purchase["id"], "order.create", body)
        self.retry_window(operation)
        self.store.update_run(run_id, state="running")
        try:
            order = provider.create_order(operation["body"], operation["request_id"])
            if order.get("status") == "COMPLETED" and order.get("id"):
                self.store.update_purchase(purchase["id"], order_id=order["id"], payment_state="UNRESOLVED")
                self.store.update_operation(operation["id"], state="COMPLETED", response=order)
                return {"order_id": order["id"], "approval_url": None, "reconciliation": self.reconcile(run_id)}
            url = approval_url(order)
            if not order.get("id") or not url:
                raise ValueError("Provider order lacks an approval URL or identity")
            purchase = self.store.update_purchase(purchase["id"], order_id=order["id"], payment_state="AWAITING_APPROVAL")
            self.store.update_operation(operation["id"], state="COMPLETED", response=order)
            self.event(run, purchase, "provider", "order_created", order, operation)
            self.store.update_run(run_id, state="awaiting_approval")
            return {"order_id": order["id"], "approval_url": url}
        except PayPalError as exc:
            self.store.update_operation(operation["id"], state="UNRESOLVED" if exc.ambiguous else "FAILED", response={"code": exc.code})
            self.store.update_run(run_id, state="inconclusive")
            self.event(run, purchase, "merchant", "order_unresolved", {"code": exc.code}, operation)
            raise

    def capture(self, run_id, order_id):
        run, purchase, fault = self.context(run_id)
        if not purchase["order_id"] or order_id != purchase["order_id"]:
            raise ValueError("Return order does not match the persisted purchase")
        if fault["kind"] == "process_interrupt" and os.environ.get("CRASHCART_ALLOW_PROCESS_INTERRUPT") != "1":
            raise ValueError("Process interruption disabled; set CRASHCART_ALLOW_PROCESS_INTERRUPT=1 only for an owned fault exercise")
        provider = self.provider(run)
        before = provider.get_order(order_id)
        self.event(run, purchase, "provider", "pre_capture_read", before)
        if before.get("status") == "COMPLETED":
            return self.reconcile(run_id)
        if before.get("status") != "APPROVED":
            raise ValueError("Actual sandbox buyer approval is required; callback parameters alone are insufficient")
        operation = self.store.operation(purchase["id"], "order.capture", {})
        self.retry_window(operation)
        self.store.update_run(run_id, state="running")
        self.store.update_purchase(purchase["id"], payment_state="UNRESOLVED")
        self.store.update_operation(operation["id"], state="IN_FLIGHT")
        if fault["merchant"] == "healthy":
            self.store.enqueue(run_id, "reconcile", {"attempt": 0}, semantic_key="recovery-0", available_at=datetime.now(timezone.utc).timestamp()+2)
        self.event(run, purchase, "harness", "fault_activated", fault, operation)
        try:
            response = provider.capture_order(order_id, operation["body"], operation["request_id"])
            # Harness tape survives loss; merchant's order/capture state is still unresolved.
            self.event(run, purchase, "harness", "capture_transport_response", response, operation)
            if fault["kind"] == "process_interrupt":
                self.event(run, purchase, "harness", "process_exit_boundary", {"exit_code": 86, "boundary": "after_capture_before_fulfillment"}, operation)
                os._exit(86)
            if fault["kind"] == "response_loss":
                self.store.update_operation(operation["id"], state="UNRESOLVED")
                self.event(run, purchase, "merchant", "customer_message", {"message": "Payment could not be confirmed. No ticket is available yet."}, operation)
                self.store.update_run(run_id, state="inconclusive")
                return {"state": "unresolved", "message": "Payment could not be confirmed. No ticket is available yet."}
            self.store.update_operation(operation["id"], state="COMPLETED", response=response)
            return self.reconcile(run_id)
        except PayPalError as exc:
            self.store.update_operation(operation["id"], state="UNRESOLVED" if exc.ambiguous else "FAILED", response={"code": exc.code})
            self.store.update_run(run_id, state="inconclusive")
            self.event(run, purchase, "merchant", "capture_unresolved", {"code": exc.code, "ambiguous": exc.ambiguous}, operation)
            raise

    def reconcile(self, run_id):
        run, purchase, fault = self.context(run_id)
        if not purchase["order_id"]:
            raise ValueError("No saved order to reconcile")
        provider = self.provider(run)
        order = provider.get_order(purchase["order_id"])
        observed = self.event(run, purchase, "provider", "independent_order_read", order)
        try:
            payment = inspect_capture(order, purchase["order_id"], purchase["id"])
        except ValueError as exc:
            self.store.update_run(run_id, state="inconclusive")
            self.event(run, purchase, "checker", "inconclusive", {"reason": str(exc)})
            return {"verdict": "INCONCLUSIVE", "reason": str(exc), "merchant": self.store.merchant_state(purchase["id"])}
        try:
            validate_capture(order, purchase["order_id"], purchase["id"])
            eligible = True
        except ValueError:
            eligible = False
        if eligible:
            self.store.confirm_payment(purchase["id"], order_id=payment["order_id"], capture_id=payment["capture_id"],
                amount=payment["amount"], currency=payment["currency"], completed_at=payment["completed_at"], provider_response=order)
        elapsed = (datetime.now(timezone.utc) - instant(payment["completed_at"])).total_seconds()
        if eligible and fault["merchant"] == "healthy" and (fault["kind"] != "event_delay" or elapsed >= fault["delay_seconds"]):
            ticket = self.store.fulfill(purchase["id"])
            self.event(run, purchase, "merchant", "ticket_fulfilled", ticket)
            if fault["kind"] == "event_duplicate":
                duplicate = self.store.fulfill(purchase["id"])
                self.event(run, purchase, "harness", "duplicate_processing", {"ticket_id": duplicate["id"]})
        merchant = self.store.merchant_state(purchase["id"])
        merchant_observed = self.event(run, purchase, "merchant", "entitlement_read", merchant)
        merchant["observation_id"] = merchant_observed["id"]
        normalized = {**payment, "run_id": run_id, "purchase_id": purchase["id"], "status": "COMPLETED", "confirmed": True,
            "capture_completed_at": payment["completed_at"], "observed_at": observed["observed_at"], "observation_id": observed["id"]}
        verdict = evaluate(normalized, merchant, now=utcnow())
        self.event(run, purchase, "checker", "invariant_result", verdict)
        self.store.update_run(run_id, state={"PASS": "completed", "FAIL": "failed", "INCONCLUSIVE": "inconclusive"}[verdict["verdict"]])
        if verdict["verdict"] != "INCONCLUSIVE":
            self.event(run, purchase, "harness", "fault_deactivated", {"kind": fault["kind"]})
        return {**verdict, "payment": normalized, "merchant": merchant}

    def observe_browser(self, run_id, body):
        run, purchase, fault = self.context(run_id)
        allowed = {"url_path", "visible_text", "action", "recording_id", "browser_kind"}
        if set(body) - allowed or body.get("browser_kind") != "LOCAL_BROWSER":
            raise ValueError("Local observation schema required; KERNEL evidence needs its actual session adapter")
        if not all(isinstance(body.get(n), str) and len(body[n]) <= 4000 for n in ["url_path", "visible_text", "action"]):
            raise ValueError("Bounded actual browser text, path and action are required")
        return self.event(run, purchase, "browser", "customer_observation", body)

    def webhook(self, headers, event, *, raw_body=None):
        provider = self.provider_factory()
        if not provider.verify_webhook(headers, event, raw_body=raw_body):
            raise ValueError("Webhook signature rejected")
        event_id = event.get("id")
        if not event_id:
            raise ValueError("Verified event missing identity")
        resource = event.get("resource", {})
        order_id = resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id")
        with self.store.connect() as db:
            purchase = db.execute("SELECT * FROM purchases WHERE order_id=?", (order_id,)).fetchone() if order_id else None
        run_id = purchase["run_id"] if purchase else None
        safe = {"id": event_id, "event_type": event.get("event_type"), "order_id": order_id, "resource_id": resource.get("id")}
        accepted = self.store.accept_webhook(event_id, safe, verified=True, run_id=run_id)
        if run_id:
            self.store.enqueue(run_id, "reconcile", {"attempt": 0}, semantic_key="webhook-"+event_id)
        return {"verified": True, "event_id": event_id, "stored": accepted}
