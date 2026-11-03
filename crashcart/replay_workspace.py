"""Persist freshly executed offline replay in normal workspace read APIs.

No provider or model imports, no caller-supplied verdict, no live fallback. The
original tape is preserved separately from namespaced replay projections.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import uuid

from .replay import ReplayError, digest, load_package, replay, validate_package, WORKSPACE_IMPORT_VERSION
from .store import Store, canonical, utcnow

IMPORT_VERSION = WORKSPACE_IMPORT_VERSION
ROOT = Path(__file__).resolve().parents[1]


def _sources():
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
            ("crashcart/replay.py", "crashcart/replay_workspace.py", "crashcart/store.py",
             "crashcart/invariant.py", "migrations/001_initial.sql")}


def _map(value, identities):
    if isinstance(value, str):
        return identities.get(value, value)
    if isinstance(value, list):
        return [_map(item, identities) for item in value]
    if isinstance(value, dict):
        return {key: _map(item, identities) for key,item in value.items()}
    return value


def _insert(db, table, row):
    # Table/column names originate only in this module or the executed Store.
    columns=list(row)
    db.execute("INSERT INTO " + table + "(" + ",".join(columns) + ") VALUES(" +
               ",".join("?" for _ in columns) + ")", [row[key] for key in columns])


def _state_hash(db, run_id):
    rows={"runs":[dict(r) for r in db.execute("SELECT * FROM runs WHERE id=?",(run_id,))],
          "purchases":[dict(r) for r in db.execute("SELECT * FROM purchases WHERE run_id=?",(run_id,))],
          "operations":[dict(r) for r in db.execute("SELECT o.* FROM operations o JOIN purchases p ON p.id=o.purchase_id WHERE p.run_id=? ORDER BY o.id",(run_id,))],
          "tickets":[dict(r) for r in db.execute("SELECT t.* FROM tickets t JOIN purchases p ON p.id=t.purchase_id WHERE p.run_id=? ORDER BY t.id",(run_id,))],
          "events":[dict(r) for r in db.execute("SELECT * FROM events WHERE run_id=? ORDER BY id",(run_id,))]}
    return digest(rows)


def import_replay(store, package, merchant="defective"):
    """Re-execute then atomically save an isolated replay; duplicate imports reuse it.

    The original package/hash and actual replay result are sealed in a finished
    attempt. Schema provenance is not authentication of historical service data.
    """
    tape=validate_package(deepcopy(package))
    if merchant not in {"defective","healthy"}:
        raise ReplayError("Unknown merchant variant")
    implementation=_sources()
    key=digest({"version":IMPORT_VERSION,"input_sha256":digest(tape),"merchant":merchant,"implementation":implementation})
    # Serialize duplicate detection and insertion. Replay is bounded (<=100
    # steps) and strictly offline; failures roll back the entire import.
    with store.connect(write=True) as db:
        prior=db.execute("SELECT * FROM attempts WHERE kind=? AND json_extract(input_json,'$.import_key')=?",
                         (IMPORT_VERSION,key)).fetchall()
        if prior:
            if len(prior)!=1 or prior[0]["state"]!="COMPLETED" or not prior[0]["finished_at"]:
                raise ReplayError("Replay import is unresolved or duplicated; no overwrite")
            result=json.loads(prior[0]["result_json"])
            if _state_hash(db,prior[0]["run_id"])!=result["workspace_state_sha256"]:
                raise ReplayError("Saved replay workspace changed; immutable import will not be overwritten")
            return {**result["receipt"],"reused":True}
        execution=replay(tape,merchant,include_state=True)
        if implementation!=_sources():
            raise ReplayError("Replay implementation changed during execution")
        state=execution.pop("execution_state")
        run=deepcopy(state["runs"][0]);purchase=deepcopy(state["purchases"][0])
        run_id,purchase_id=run["id"],purchase["id"]
        imported_at=utcnow()
        order_id="replay_order_"+run_id.removeprefix("run_")
        capture_id="replay_capture_"+run_id.removeprefix("run_") if purchase["capture_id"] else None
        identities={tape["source"]["run_id"]:run_id,tape["source"]["purchase_id"]:purchase_id,
                    tape["source"]["order_id"]:order_id}
        if purchase["capture_id"]:identities[purchase["capture_id"]]=capture_id
        if len(identities) != 3 + bool(purchase["capture_id"]):
            raise ReplayError("Source identities overlap; replay namespace is ambiguous")
        source_links={"source":deepcopy(tape["source"]),"input_sha256":digest(tape),
            "implementation":implementation,"import_version":IMPORT_VERSION,"imported_at":imported_at,
            "mode":execution["mode"],"fresh_execution":False,"network_calls":0,
            "source_authenticity":execution["source_authenticity"],"identity_mapping":identities,
            "recorded_evaluation":deepcopy(execution["evaluation"]),
            "clock_domains":{"source":"recorded observation timestamps","replay":"recorded clock re-execution",
                             "import":"current workspace persistence time","cross_clock_order_proves_causality":False}}
        run.update(state={"PASS":"completed","FAIL":"failed","INCONCLUSIVE":"inconclusive"}[execution["verdict"]],
                   created_at=imported_at,updated_at=imported_at)
        purchase.update(order_id=order_id,capture_id=capture_id,created_at=imported_at,updated_at=imported_at)
        if purchase["confirmation_json"]:
            purchase["confirmation_json"]=canonical({**_map(json.loads(purchase["confirmation_json"]),identities),
                "replay_provenance":source_links})
        _insert(db,"runs",run);_insert(db,"purchases",purchase)
        for operation in state["operations"]:
            projected=deepcopy(operation)
            for column in ("body_json","response_json"):
                if projected[column] is not None:projected[column]=canonical(_map(json.loads(projected[column]),identities))
            _insert(db,"operations",projected)
        for ticket in state["tickets"]:_insert(db,"tickets",ticket)
        step_states={step["source_record"]:step for step in execution["trace"]}
        events=[]
        for index,record in enumerate(tape["records"]):
            step=step_states.get(record["id"])
            if record["event_type"]=="entitlement_read" and step:
                payload=_map(step["merchant_state"],identities)
            elif record["source"]=="browser":
                payload=deepcopy(record["payload"])
            else:
                payload=_map(record["payload"],identities)
            payload.update(replay_provenance={"import_version":IMPORT_VERSION,"input_sha256":digest(tape),
                "mode":execution["mode"],"source_mode":execution["source_mode"],"fresh_execution":False,
                "imported_at":imported_at,"source_run_id":tape["source"]["run_id"],"source_record_id":record["id"],
                "source_record_sha256":digest(record),"executed_step":step is not None,
                "recorded_observed_at":record["observed_at"],"clock_domain":"RECORDED_SOURCE"},recorded_payload=deepcopy(record["payload"]))
            event={"id":f"event_{run_id.removeprefix('run_')}_record_{index:04}","run_id":run_id,
                "purchase_id":purchase_id,"order_id":order_id if record["order_id"] else None,
                "operation_id":None,"source":record["source"],"event_type":record["event_type"],
                "event_time":record["observed_at"],"observed_at":record["observed_at"],
                "caused_by":None,"payload_json":canonical(payload)}
            events.append(event)
        outcome={key:deepcopy(execution[key]) for key in ("verdict","reason","signature","invariant_version","source_ids","deadline")}
        outcome=_map(outcome,identities)
        outcome["replay_provenance"]=source_links
        for suffix,source,kind,payload in [("checked","checker","invariant_result",outcome),
                ("imported","replay","replay_imported",{**source_links,"source_package":deepcopy(tape),"source_operations":deepcopy(tape["operations"]),
                    "replay_operation_mapping":deepcopy(execution["operation_mapping"]),"result":outcome})]:
            events.append({"id":f"event_{run_id.removeprefix('run_')}_{suffix}","run_id":run_id,
                "purchase_id":purchase_id,"order_id":order_id,"operation_id":None,"source":source,
                "event_type":kind,"event_time":tape["evaluate_at"],"observed_at":imported_at,"caused_by":None,
                "payload_json":canonical(payload)})
        for event in events:_insert(db,"events",event)
        if db.execute("SELECT COUNT(*) FROM tickets WHERE purchase_id=?",(purchase_id,)).fetchone()[0]!=execution["ticket_count"]:
            raise ReplayError("Imported ticket state differs from actual replay execution")
        receipt={"run_id":run_id,"purchase_id":purchase_id,"mode":execution["mode"],"source_mode":execution["source_mode"],
            "input_sha256":execution["input_sha256"],"merchant_variant":merchant,"imported_at":imported_at,
            "verdict":execution["verdict"],"signature":execution["signature"],"ticket_count":execution["ticket_count"],
            "source_run_id":tape["source"]["run_id"],"identity_mapping":identities,"network_calls":0,"fresh_execution":False,
            "source_authenticity":execution["source_authenticity"],"reused":False}
        _insert(db,"attempts",{"id":"attempt_"+uuid.uuid4().hex,"run_id":run_id,"ordinal":1,"kind":IMPORT_VERSION,
            "state":"COMPLETED","input_json":canonical({"import_key":key,"package":tape,"implementation":implementation}),
            "result_json":canonical({"receipt":receipt,"execution":execution,"workspace_state_sha256":_state_hash(db,run_id)}),
            "created_at":imported_at,"finished_at":imported_at})
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input");parser.add_argument("--db",required=True)
    parser.add_argument("--merchant",choices=("defective","healthy"),default="defective")
    args=parser.parse_args()
    try:
        result=import_replay(Store(args.db),load_package(args.input),args.merchant)
        print(json.dumps(result,indent=2));return 0
    except (ReplayError,ValueError,TypeError,KeyError,OSError) as exc:
        print(json.dumps({"error":"INVALID_REPLAY_IMPORT","reason":str(exc)}));return 3

if __name__=="__main__":raise SystemExit(main())
