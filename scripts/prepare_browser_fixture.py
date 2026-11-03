"""Seed isolated LOCAL_TEST merchant records; never claims a real payment."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crashcart.store import Store, utcnow

folder = Path("var/browser-check")
folder.mkdir(parents=True, exist_ok=True)
store = Store(folder / "browser.sqlite3")
run = store.create_run("LOCAL_TEST: stored workshop ticket for browser adapter verification", mode="LOCAL_TEST")
store.update_purchase(run["purchase_id"], order_id="LOCAL_BROWSER_ORDER")
store.confirm_payment(run["purchase_id"], order_id="LOCAL_BROWSER_ORDER", capture_id="LOCAL_BROWSER_CAPTURE", amount=2900, currency="USD", completed_at=utcnow(), provider_response={"source": "synthetic browser test; no provider execution"})
ticket = store.fulfill(run["purchase_id"])
store.update_run(run["id"], state="completed")
(folder / "fixture.json").write_text(json.dumps({"run_id": run["id"], "ticket_id": ticket["id"], "purchase_id": run["purchase_id"], "mode": "LOCAL_TEST"}, indent=2))
print("Isolated LOCAL_TEST merchant ticket seeded; no provider calls.")
