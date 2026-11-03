"""Actual offline execution/persistence; LOCAL_TEST sources remain synthetic."""
from copy import deepcopy
import hashlib
import io
import zipfile
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from crashcart.replay import ReplayError,digest,load_package,package_run,reduce_package
from crashcart.replay_workspace import IMPORT_VERSION,import_replay
from crashcart.store import Store
from crashcart import replay_workspace as workspace
from tests.test_replay import synthetic_package

HISTORICAL=Path(__file__).resolve().parents[1]/"evidence/runs/paypal-live/response-loss-input.json"

class ReplayWorkspaceTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.path=Path(folder.name)/"workspace.sqlite3";self.store=Store(self.path)
        blocker=patch("socket.socket",side_effect=AssertionError("Offline replay must never open a socket"))
        blocker.start();self.addCleanup(blocker.stop)

    def test_actual_offline_state_survives_restart_and_source_tape_is_unchanged(self):
        tape=synthetic_package();original=deepcopy(tape)
        bad=import_replay(self.store,tape);good=import_replay(self.store,tape,"healthy")
        self.assertEqual(tape,original);self.assertEqual((bad["ticket_count"],good["ticket_count"]),(0,1))
        self.assertEqual((bad["verdict"],good["verdict"]),("FAIL","PASS"))
        self.assertEqual((bad["mode"],good["mode"]),("LOCAL_TEST","LOCAL_TEST"))
        store=Store(self.path)
        for receipt in (bad,good):
            run=store.get_run(receipt["run_id"]);purchase=store.purchase_for_run(run["id"])
            merchant=store.merchant_state(purchase["id"])
            self.assertEqual(merchant["ticket_count"],receipt["ticket_count"])
            self.assertEqual(purchase["payment_confirmed"],1)
            self.assertTrue(purchase["order_id"].startswith("replay_order_"))
            self.assertTrue(purchase["capture_id"].startswith("replay_capture_"))
            attempt=store.get_attempts(run["id"])[0]
            self.assertEqual(attempt["input"]["package"],original)
            self.assertEqual(attempt["result"]["execution"]["input_sha256"],digest(original))
            self.assertEqual(attempt["state"],"COMPLETED")
            with self.assertRaises(ValueError):store.finish_attempt(attempt["id"],"COMPLETED",{})
            events=store.get_events(run["id"])
            for source in original["records"]:
                event=next(e for e in events if e["payload"].get("replay_provenance",{}).get("source_record_id")==source["id"])
                self.assertEqual(event["payload"]["recorded_payload"],source["payload"])
                self.assertEqual(event["observed_at"],source["observed_at"])
                self.assertEqual(event["event_time"],source["observed_at"])
                self.assertIsNone(event["caused_by"])
                self.assertEqual(event["payload"]["replay_provenance"]["source_record_sha256"],digest(source))
            last=next(e for e in events if e["event_type"]=="entitlement_read")
            self.assertEqual(last["payload"]["ticket_count"],receipt["ticket_count"])
            self.assertEqual(last["payload"]["recorded_payload"]["ticket_count"],0)
        self.assertNotEqual(bad["run_id"],good["run_id"])

    def test_original_financial_identity_and_budgets_never_change_or_collide(self):
        original=self.store.create_run("Existing financial run",mode="LIVE_SANDBOX")
        purchase=self.store.purchase_for_run(original["id"])
        self.store.update_purchase(purchase["id"],order_id="SYNTHETICORDER")
        self.store.confirm_payment(purchase["id"],order_id="SYNTHETICORDER",capture_id="SYNTHETICCAPTURE",amount=2900,currency="USD",completed_at="2026-10-22T10:00:00Z",provider_response={"synthetic":True})
        before=(self.store.get_run(original["id"]),self.store.get_purchase(purchase["id"]))
        imported=import_replay(self.store,synthetic_package(),"healthy")
        self.assertEqual(before,(self.store.get_run(original["id"]),self.store.get_purchase(purchase["id"])))
        self.assertNotEqual(self.store.purchase_for_run(imported["run_id"])["order_id"],before[1]["order_id"])
        self.assertEqual(len(self.store.list_runs()),2)

    def test_same_input_and_variant_reuses_durable_import_without_reexecution(self):
        one=import_replay(self.store,synthetic_package())
        with patch.object(workspace,"replay",side_effect=AssertionError("Do not execute a duplicate import")):
            two=import_replay(Store(self.path),synthetic_package())
        self.assertTrue(two["reused"]);self.assertEqual(one["run_id"],two["run_id"])
        self.assertEqual(len(self.store.list_runs()),1)
        self.store.update_run(one["run_id"],cancel_requested=1,state="cancelled")
        with self.assertRaisesRegex(ReplayError,"changed"):import_replay(self.store,synthetic_package())
        self.assertEqual(self.store.get_run(one["run_id"])["state"],"cancelled")

    def test_partial_import_rolls_back_all_rows_and_invalid_input_never_writes(self):
        original=workspace._insert
        def fail(db,table,row):
            if table=="events":raise RuntimeError("controlled write interruption")
            return original(db,table,row)
        with patch.object(workspace,"_insert",side_effect=fail),self.assertRaisesRegex(RuntimeError,"interruption"):
            import_replay(self.store,synthetic_package(),"healthy")
        with self.store.connect() as db:
            for table in ("runs","purchases","operations","tickets","events","attempts"):
                self.assertEqual(db.execute("SELECT COUNT(*) FROM "+table).fetchone()[0],0)
        invalid=synthetic_package();invalid["invariant"]["recovery_seconds"]=600
        with self.assertRaises(ReplayError):import_replay(self.store,invalid)
        self.assertEqual(self.store.list_runs(),[])

    def test_export_uses_exact_sealed_full_or_reduced_input_and_rejects_tampering(self):
        full=synthetic_package();reduced=reduce_package(full)["package"]
        self.assertLess(len(reduced["steps"]),len(full["steps"]))
        for tape in (full,reduced):
            with self.subTest(steps=len(tape["steps"])):
                receipt=import_replay(self.store,tape)
                run=self.store.get_run(receipt["run_id"]);purchase=self.store.purchase_for_run(run["id"])
                events=self.store.get_events(run["id"])
                output=package_run(run,purchase,self.store.get_operations(purchase["id"]),events,{"ignored-current-source":"0"*64})
                self.assertEqual(output,tape);self.assertEqual(digest(output),receipt["input_sha256"])
                changed=deepcopy(events)
                imported=next(e for e in changed if e["event_type"]=="replay_imported")
                imported["payload"]["input_sha256"]="0"*64
                with self.assertRaisesRegex(ReplayError,"hash, mode or namespace"):
                    package_run(run,purchase,[],changed,{})
                changed=deepcopy(events);next(e for e in changed if e["event_type"]=="replay_imported")["payload"]["identity_mapping"][tape["source"]["run_id"]]="different-run"
                with self.assertRaisesRegex(ReplayError,"hash, mode or namespace"):
                    package_run(run,purchase,[],changed,{})

    def test_genuine_historical_tape_is_recorded_replay_not_new_sandbox_execution(self):
        before=hashlib.sha256(HISTORICAL.read_bytes()).hexdigest()
        tape=load_package(HISTORICAL);result=import_replay(self.store,tape)
        self.assertEqual(tape["source"]["mode"],"LIVE_SANDBOX")
        self.assertEqual(result["mode"],"RECORDED_REPLAY");self.assertFalse(result["fresh_execution"])
        self.assertEqual(result["network_calls"],0);self.assertEqual(result["signature"],"paid_without_ticket")
        self.assertEqual(hashlib.sha256(HISTORICAL.read_bytes()).hexdigest(),before)
        saved=self.store.get_attempts(result["run_id"])[0]
        self.assertEqual(saved["input"]["package"]["source"],tape["source"])
        self.assertEqual(saved["result"]["receipt"]["source_run_id"],tape["source"]["run_id"])

class ReplayWorkspaceHTTPTests(unittest.TestCase):
    def setUp(self):
        from crashcart.server import ThreadingHTTPServer,Handler
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.store=Store(Path(tmp.name)/"local.sqlite3")
        self.receipt=import_replay(self.store,load_package(HISTORICAL))
        self.env=patch.dict(os.environ,{"CRASHCART_OPERATOR_TOKEN":"test-only-token","CRASHCART_ALLOW_MODEL":"0","CRASHCART_ALLOW_SANDBOX":"0"})
        self.env.start();self.addCleanup(self.env.stop)
        self.server=ThreadingHTTPServer(("127.0.0.1",0),Handler);self.server.store=self.store
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close)
    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(2)
    def request(self,path,method="GET",body=None,auth=True,raw=False):
        conn=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=3)
        headers={"Content-Type":"application/json"}
        if auth:headers["Authorization"]="Bearer test-only-token"
        try:
            conn.request(method,path,None if body is None else json.dumps(body),headers)
            result=conn.getresponse();content=result.read();return result.status,content if raw else json.loads(content)
        finally:conn.close()
    def test_saved_replay_is_available_through_normal_authenticated_read_and_export_routes(self):
        run_id=self.receipt["run_id"]
        self.assertEqual(self.request("/api/runs/"+run_id,auth=False)[0],401)
        status,listing=self.request("/api/runs");self.assertEqual(status,200)
        self.assertEqual(listing["runs"][0]["id"],run_id)
        status,data=self.request("/api/runs/"+run_id);self.assertEqual(status,200)
        self.assertEqual(data["run"]["mode"],"RECORDED_REPLAY")
        self.assertEqual(data["purchase"]["payment_confirmed"],1);self.assertEqual(data["merchant"]["ticket_count"],0)
        self.assertTrue(any(e["source"]=="browser" for e in data["events"]))
        self.assertTrue(any(e["event_type"]=="independent_order_read" for e in data["events"]))
        result=next(e["payload"] for e in data["events"] if e["event_type"]=="invariant_result")
        self.assertEqual(result["signature"],"paid_without_ticket")
        self.assertFalse(result["replay_provenance"]["fresh_execution"])
        status,merchant=self.request("/api/merchant/"+data["purchase"]["id"])
        self.assertEqual(status,200);self.assertEqual(merchant["ticket_count"],data["merchant"]["ticket_count"])
        self.assertEqual(self.request("/api/runs/"+run_id+"/export")[1]["run"]["mode"],"RECORDED_REPLAY")
    def test_normal_regression_download_retains_exact_input_and_recorded_mode(self):
        status,data=self.request("/api/runs/"+self.receipt["run_id"]+"/regression.zip",raw=True)
        self.assertEqual(status,200)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            tape=json.loads(archive.read("input.json"));manifest=json.loads(archive.read("manifest.json"))
            self.assertEqual(digest(tape),self.receipt["input_sha256"])
            self.assertEqual(tape,load_package(HISTORICAL))
            self.assertEqual(manifest["mode"],"RECORDED_REPLAY")
            for name,expected in manifest["files"].items():
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(),expected)

    def test_normal_payment_actions_cannot_construct_provider_or_mutate_saved_replay(self):
        run_id=self.receipt["run_id"];purchase=self.store.purchase_for_run(run_id)
        before=(self.store.get_run(run_id),purchase,self.store.get_operations(purchase["id"]),self.store.get_events(run_id))
        with patch("crashcart.paypal.PayPalSandbox.__init__",side_effect=AssertionError("Provider must not be constructed")) as provider:
            for action,body in (("order",{}),("capture",{"order_id":purchase["order_id"]}),("reconcile",{})):
                status,result=self.request("/api/runs/"+run_id+"/"+action,"POST",body)
                self.assertEqual(status,400);self.assertIn("no live fallback",result["error"])
            provider.assert_not_called()
        self.assertEqual(before,(self.store.get_run(run_id),self.store.purchase_for_run(run_id),self.store.get_operations(purchase["id"]),self.store.get_events(run_id)))

if __name__=="__main__":unittest.main(verbosity=2)
