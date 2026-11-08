"""Synthetic v1 ledgers only; no private allowance files or provider requests."""
from copy import deepcopy
from dataclasses import replace
import fcntl
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import socket
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.request import Request

from crashcart import model_allowance as allowance

ORIGIN = "https://local-allowance-test.us-east.modal.direct"
CREDENTIAL = "synthetic-only-allowance-credential"


def body():
    return {"model": allowance.MODEL, "messages": [{"role": "system", "content": "Return JSON."}, {"role": "user", "content": "PRIVATE-BODY-NOT-LOGGED"}],
            "n": 1, "max_tokens": 1024, "stream": False, "reasoning_effort": "none"}


def request(raw=None, *, url=None, method="POST"):
    return Request(url or ORIGIN + "/v1/chat/completions", method=method,
                   data=json.dumps(body()).encode() if raw is None else raw,
                   headers={"Authorization": "Bearer " + CREDENTIAL})


def terminal(index, *, cost=None, state="RESPONDED"):
    value = {"call": index, "state": state, "started_at": "2026-10-26T10:00:00Z",
             "finished_at": "2026-10-26T10:00:01Z", "duration_seconds": 1,
             "request_sha256": "a" * 64, "request_bytes": 200,
             "reserved_micro_usd": 40000, "usage": None}
    if cost is not None: value["observed_rate_cost_micro_usd"] = cost
    return value


def _process_reserve(path, start, release, results):
    with patch.object(socket.socket, "connect", side_effect=AssertionError("No provider request permitted")):
        if not start.wait(10):
            results.put(("error", "start timeout")); return
        try:
            permit = allowance.reserve(path, request(), expected_origin=ORIGIN, expected_model=allowance.MODEL)
        except allowance.ModelAllowanceError as exc:
            results.put(("blocked", exc.code)); return
        results.put(("reserved", permit.call))
        if not release.wait(10):
            results.put(("error", "release timeout")); return
        allowance.finish(path, permit, error=TimeoutError("PRIVATE-ERROR-NOT-LOGGED"))
        results.put(("finished", permit.call))


class ModelAllowanceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "allowance.json"
        self.initial = {"version": 1, "call_limit": 24, "ceiling_micro_usd": 1000000, "calls": [],
                        "authorization_context": "Synthetic reviewed grant; not a live allowance",
                        "published_usd_per_million": {"input": .30, "output": 1.20}}
        self.write(self.initial)
        blocker = patch.object(socket.socket, "connect", side_effect=AssertionError("No provider request permitted"))
        blocker.start(); self.addCleanup(blocker.stop)

    def write(self, value):
        self.path.write_text(json.dumps(value)); self.path.chmod(0o600)

    def state(self): return json.loads(self.path.read_text())

    def reserve(self, packet=None, **kwargs):
        return allowance.reserve(self.path, packet or request(), expected_origin=ORIGIN,
                                 expected_model=allowance.MODEL, **kwargs)

    def test_v1_history_is_preserved_and_new_records_contain_metadata_only(self):
        prior = terminal(1)
        prior["choices"] = [{"message": {"content": "Legacy historical content is preserved unchanged"}}]
        initial = {**self.initial, "calls": [prior], "unknown_metadata": {"retained": [1, 2, 3]}}
        self.write(initial); permit = self.reserve(); reserved = self.state()
        self.assertEqual(reserved["calls"][0], prior)
        self.assertEqual(reserved["unknown_metadata"], initial["unknown_metadata"])
        self.assertEqual((permit.call, reserved["calls"][1]["state"]), (2, "RESERVED"))
        self.assertEqual(reserved["calls"][1]["request_sha256"], hashlib.sha256(request().data).hexdigest())
        response = {"id": "chatcmpl_test", "model": allowance.MODEL,
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                    "choices": [{"message": {"content": "PRIVATE-RESPONSE-NOT-LOGGED"}}],
                    "headers": {"authorization": CREDENTIAL}}
        summary = allowance.finish(self.path, permit, response=response)
        self.assertEqual(summary["observed_rate_cost_micro_usd"], 9)
        updated = self.state(); self.assertEqual(updated["calls"][0], prior)
        self.assertEqual(updated["calls"][1]["state"], "RESPONDED")
        self.assertEqual(updated["calls"][1]["usage"], response["usage"])
        self.assertNotIn("choices", updated["calls"][1]); self.assertNotIn("headers", updated["calls"][1])
        for secret in (CREDENTIAL, "PRIVATE-BODY-NOT-LOGGED", "PRIVATE-RESPONSE-NOT-LOGGED"):
            self.assertNotIn(secret, self.path.read_text()); self.assertNotIn(secret, repr(permit))

    def test_unknown_inflight_reservation_blocks_and_is_not_automatically_cleared(self):
        permit = self.reserve(); raw = self.path.read_bytes()
        with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_UNRESOLVED"): self.reserve()
        self.assertEqual(self.path.read_bytes(), raw)
        allowance.finish(self.path, permit, error=TimeoutError("PRIVATE-ERROR-NOT-LOGGED"))
        self.assertNotIn("PRIVATE-ERROR-NOT-LOGGED", self.path.read_text())
        self.assertEqual(self.state()["calls"][0]["state"], "ERROR")
        self.assertEqual(self.reserve().call, 2)

    def test_historical_unknown_reservation_cannot_be_cleared_by_call_number(self):
        prior = terminal(1); prior["state"] = "RESERVED"
        for key in ("finished_at", "duration_seconds", "usage"): del prior[key]
        self.write({**self.initial, "calls": [prior]}); before = self.path.read_bytes()
        with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_UNRESOLVED"): self.reserve()
        with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_RESERVATION_MISMATCH"):
            allowance.finish(self.path, 1, error=RuntimeError("Do not auto-clear history"))
        self.assertEqual(self.path.read_bytes(), before)

    def test_each_error_counts_and_twenty_fifth_call_is_rejected_without_reset(self):
        for index in range(1, 25):
            permit = self.reserve(); self.assertEqual(permit.call, index)
            allowance.finish(self.path, permit, error=RuntimeError("private detail"))
        before = self.path.read_bytes()
        with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_EXHAUSTED"): self.reserve()
        self.assertEqual(before, self.path.read_bytes()); self.assertEqual(len(self.state()["calls"]), 24)
        self.assertTrue(all(item["reserved_micro_usd"] == 40000 for item in self.state()["calls"]))

    def test_ceiling_uses_maximum_of_reserved_and_observed_without_fractional_rounddown(self):
        for costs, permitted in (([960000], True), ([960000.1], False), ([1, 920000], True), ([1, 920000.1], False)):
            with self.subTest(costs=costs):
                self.write({**self.initial, "calls": [terminal(i, cost=c) for i, c in enumerate(costs, 1)]})
                if permitted: self.assertEqual(self.reserve().call, len(costs) + 1)
                else:
                    before = self.path.read_bytes()
                    with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_EXHAUSTED"): self.reserve()
                    self.assertEqual(self.path.read_bytes(), before)

    def test_legacy_missing_or_understated_cost_cannot_hide_known_usage(self):
        for cost in (None, 0):
            with self.subTest(cost=cost):
                prior = terminal(1, cost=cost)
                prior["usage"] = {"prompt_tokens": 3300000, "completion_tokens": 0, "total_tokens": 3300000}
                self.write({**self.initial, "calls": [prior]}); before = self.path.read_bytes()
                with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_EXHAUSTED"):
                    self.reserve()
                self.assertEqual(self.path.read_bytes(), before)

    def test_exact_request_byte_boundary_and_reflected_credential_metadata(self):
        value = body(); value["max_tokens"] = 1; value["messages"][1]["content"] = ""
        encode = lambda: json.dumps(value, separators=(",", ":")).encode()
        value["messages"][1]["content"] = "x" * (allowance.MAX_REQUEST_BYTES - len(encode()))
        raw = encode(); self.assertEqual(len(raw), allowance.MAX_REQUEST_BYTES)
        permit = self.reserve(request(raw=raw))
        summary = allowance.finish(self.path, permit, response={"id": CREDENTIAL, "model": CREDENTIAL})
        self.assertIsNone(summary["response_id"]); self.assertIsNone(summary["model"])
        self.assertNotIn(CREDENTIAL, self.path.read_text())
        self.assertEqual(self.state()["calls"][0]["request_bytes"], 65536)

    def test_observed_usage_on_error_is_retained_and_never_refunds_reservation(self):
        permit = self.reserve()
        class TimedOut(Exception):
            code = "MODEL_TIMEOUT"
            response = {"id": "late_response", "model": allowance.MODEL,
                        "usage": {"prompt_tokens": 2000000, "completion_tokens": 0, "total_tokens": 2000000}}
        allowance.finish(self.path, permit, error=TimedOut(CREDENTIAL)); state = self.state()
        self.assertEqual(state["calls"][0]["state"], "ERROR")
        self.assertEqual(state["calls"][0]["observed_rate_cost_micro_usd"], 600000)
        self.assertEqual(state["calls"][0]["error"], "MODEL_TIMEOUT")
        self.assertEqual(state["calls"][0]["reserved_micro_usd"], 40000)

    def test_every_history_record_is_validated_not_only_the_most_recent(self):
        mutations = [lambda s: s.update(version=True), lambda s: s.update(call_limit=25),
                     lambda s: s.update(ceiling_micro_usd=1000001),
                     lambda s: s["calls"][0].update(call=2), lambda s: s["calls"][0].update(reserved_micro_usd=39999),
                     lambda s: s["calls"][0].update(state="RESET"), lambda s: s["calls"][0].update(started_at="not a time"),
                     lambda s: s["calls"][0].update(request_sha256="a"), lambda s: s["calls"][0].update(request_bytes=65537),
                     lambda s: s["calls"][0].update(duration_seconds=-1),
                     lambda s: s["calls"][0].update(observed_rate_cost_micro_usd=float("nan")),
                     lambda s: s["calls"][0].update(observed_rate_cost_micro_usd=float("inf")),
                     lambda s: s["calls"][0].update(observed_rate_cost_micro_usd=-1),
                     lambda s: s["calls"][0].update(observed_rate_cost_micro_usd=True),
                     lambda s: s["calls"][0].update(usage={"prompt_tokens": True})]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                state = {**deepcopy(self.initial), "calls": [terminal(1), terminal(2)]}
                mutate(state); self.write(state); before = self.path.read_bytes()
                with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_CORRUPT"): self.reserve()
                self.assertEqual(self.path.read_bytes(), before)

    def test_missing_malformed_duplicate_or_nonfinite_ledger_is_never_initialized(self):
        self.path.unlink()
        with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_MISSING"): self.reserve()
        self.assertFalse(self.path.exists())
        for content in ("not json", '{"version":1,"version":1}', '{"unrelated":NaN}', '[]'):
            self.path.write_text(content); self.path.chmod(0o600)
            with self.subTest(content=content), self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_CORRUPT"):
                self.reserve()
            self.assertEqual(self.path.read_text(), content)

    def test_private_modes_symlinks_and_hardlinks_fail_closed(self):
        self.path.chmod(0o644)
        with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_PERMISSIONS"): self.reserve()
        self.path.chmod(0o600); linked = self.path.with_name("linked.json"); os.link(self.path, linked)
        with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_PERMISSIONS"): self.reserve()
        linked.unlink()
        original = self.path.with_name("original.json"); self.path.rename(original); self.path.symlink_to(original)
        with self.assertRaises(allowance.ModelAllowanceError): self.reserve()
        self.path.unlink(); original.rename(self.path)
        lock = self.path.with_suffix(".lock")
        if lock.exists(): lock.unlink()
        lock.symlink_to(self.path)
        with self.assertRaises(allowance.ModelAllowanceError): self.reserve()
        self.assertEqual(self.state(), self.initial)

    def test_replacement_is_private_atomic_and_uses_stable_sibling_lock(self):
        initial_inode = self.path.stat().st_ino
        permit = self.reserve(); lock = self.path.with_suffix(".lock"); lock_inode = lock.stat().st_ino
        self.assertNotEqual(initial_inode, self.path.stat().st_ino)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        allowance.finish(self.path, permit, response={"id": "reply", "model": allowance.MODEL})
        self.assertEqual(lock.stat().st_ino, lock_inode)
        self.assertEqual(stat.S_IMODE(lock.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertFalse(list(self.path.parent.glob(".allowance-*")))

    def test_failed_finish_preserves_unknown_reservation_and_prevents_another_dispatch(self):
        permit = self.reserve(); before = self.path.read_bytes()
        with patch.object(allowance.os, "replace", side_effect=OSError("private filesystem detail")):
            with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_UNAVAILABLE"):
                allowance.finish(self.path, permit, response={"id": "reply"})
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(list(self.path.parent.glob(".allowance-*")))
        with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_UNRESOLVED"): self.reserve()

    def test_directory_sync_failure_on_reserve_leaves_unknown_and_prevents_dispatch(self):
        dispatch = Mock()
        with patch.object(allowance, "_sync_directory", side_effect=OSError("synthetic directory sync failure")):
            with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_UNAVAILABLE"):
                self.reserve()
                dispatch()
        dispatch.assert_not_called()
        state = self.state()
        self.assertEqual(len(state["calls"]), 1)
        self.assertEqual(state["calls"][0]["state"], "RESERVED")
        self.assertEqual(state["calls"][0]["reserved_micro_usd"], 40000)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_UNRESOLVED"):
            self.reserve()
        self.assertEqual(before, self.path.read_bytes())

    def test_directory_sync_failure_on_finish_preserves_visible_known_response_and_charge(self):
        prior = terminal(1, cost=960000)
        self.write({**self.initial, "calls": [prior]})
        permit = self.reserve()
        response = {"id": "known_response", "model": allowance.MODEL,
                    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}
        with patch.object(allowance, "_sync_directory", side_effect=OSError("synthetic directory sync failure")):
            with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_UNAVAILABLE"):
                allowance.finish(self.path, permit, response=response)
        state = self.state()
        self.assertEqual(state["calls"][0], prior)
        self.assertEqual(len(state["calls"]), 2)
        self.assertEqual(state["calls"][1]["state"], "RESPONDED")
        self.assertEqual(state["calls"][1]["response_id"], "known_response")
        self.assertEqual(state["calls"][1]["usage"], response["usage"])
        self.assertEqual(state["calls"][1]["reserved_micro_usd"], 40000)
        self.assertEqual(state["calls"][1]["observed_rate_cost_micro_usd"], 9)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_EXHAUSTED"):
            self.reserve()
        self.assertEqual(before, self.path.read_bytes())

    def test_wrong_or_double_finish_cannot_change_history(self):
        permit = self.reserve(); before = self.path.read_bytes()
        for wrong in (replace(permit, call=2), replace(permit, request_sha256="b" * 64),
                      replace(permit, reservation_id="b" * 32), replace(permit, call=True), 1):
            with self.subTest(wrong=wrong), self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_RESERVATION_MISMATCH"):
                allowance.finish(self.path, wrong, response={"id": "reply"})
            self.assertEqual(before, self.path.read_bytes())
        allowance.finish(self.path, permit, error=TimeoutError()); before = self.path.read_bytes()
        with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_ALREADY_FINISHED"):
            allowance.finish(self.path, permit, response={"id": "another"})
        self.assertEqual(before, self.path.read_bytes())

    def test_invalid_usage_leaves_reservation_unknown(self):
        for usage in ({"prompt_tokens": True}, {"completion_tokens": -1}, {"total_tokens": float("inf")}, "bad"):
            with self.subTest(usage=usage):
                self.write(self.initial); permit = self.reserve(); before = self.path.read_bytes()
                with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_USAGE_INVALID"):
                    allowance.finish(self.path, permit, response={"usage": usage})
                self.assertEqual(before, self.path.read_bytes())

    def test_destination_model_wire_limits_and_body_size_reject_before_reservation(self):
        packets = [request(url="https://another.us-east.modal.direct/v1/chat/completions"),
                   request(url=ORIGIN + "/v1/chat/completions/"), request(method="GET"),
                   request(url=ORIGIN + "/v1/chat/completions?token=private"),
                   request(raw=b"x" * 65537), request(raw=b"not json"),
                   request(raw=b'{"n":1,"n":2}'), request(raw=b'{"value":NaN}')]
        for fields in ({"model": "another-model"}, {"n": 2}, {"n": True}, {"max_tokens": 1025},
                       {"max_tokens": 0}, {"max_tokens": True}, {"stream": 0}, {"stream": True},
                       {"reasoning_effort": "low"}, {"max_completion_tokens": 100000},
                       {"max_output_tokens": 100000}, {"tools": [{"type": "function"}]},
                       {"messages": [{"role": "system", "content": "JSON"}, {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "https://must-not-fetch.invalid/huge.png"}}]}]},
                       {"messages": [{"role": "system", "content": "JSON"}, {"role": "user", "content": "text", "attachments": ["private"]}]},
                       {"messages": []}):
            packets.append(request(raw=json.dumps({**body(), **fields}).encode()))
        before = self.path.read_bytes()
        for packet in packets:
            with self.subTest(url=packet.full_url, method=packet.get_method()), self.assertRaises(allowance.ModelAllowanceError):
                self.reserve(packet)
            self.assertEqual(self.path.read_bytes(), before)
        for origin in ("https://tenant.modal.direct", "http://tenant.region.modal.direct", ORIGIN + "/", ORIGIN + ":443"):
            with self.subTest(pin=origin), self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_DESTINATION_REJECTED"):
                allowance.reserve(self.path, request(), expected_origin=origin, expected_model=allowance.MODEL)
        with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_DESTINATION_REJECTED"):
            allowance.reserve(self.path, request(), expected_origin=ORIGIN, expected_model="changed-model")

    def test_lock_contention_is_bounded_without_mutating_ledger(self):
        lock = self.path.with_suffix(".lock"); fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX); before = self.path.read_bytes()
            with self.assertRaisesRegex(allowance.ModelAllowanceError, "MODEL_ALLOWANCE_LOCKED"):
                self.reserve(lock_timeout=.03)
            self.assertEqual(before, self.path.read_bytes())
        finally: os.close(fd)

    def test_competing_processes_cannot_dispatch_past_unknown_reservation(self):
        context = multiprocessing.get_context("spawn")
        start, release, results = context.Event(), context.Event(), context.Queue()
        children = [context.Process(target=_process_reserve, args=(str(self.path), start, release, results)) for _ in range(3)]
        try:
            for child in children: child.start()
            start.set(); outcomes = [results.get(timeout=15) for _ in children]
            self.assertEqual(sum(status == "reserved" for status, _ in outcomes), 1)
            self.assertEqual(sum(item == ("blocked", "MODEL_ALLOWANCE_UNRESOLVED") for item in outcomes), 2)
            self.assertEqual(len(self.state()["calls"]), 1)
            self.assertEqual(self.state()["calls"][0]["state"], "RESERVED")
            release.set(); self.assertEqual(results.get(timeout=10), ("finished", 1))
            for child in children:
                child.join(5); self.assertEqual(child.exitcode, 0)
            self.assertEqual(self.state()["calls"][0]["state"], "ERROR")
        finally:
            release.set()
            for child in children:
                if child.is_alive(): child.terminate()
                child.join(3)
            results.close(); results.join_thread()


if __name__ == "__main__": unittest.main()
