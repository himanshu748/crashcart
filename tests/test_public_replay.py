"""Execute the public historical tapes offline; these are not fresh payments."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from crashcart.invariant import DEFAULT_INVARIANT
from crashcart.replay import load_package, replay
from crashcart.replay_workspace import import_replay
from crashcart.store import Store


ROOT = Path(__file__).resolve().parents[1]
TAPES = ROOT / "evidence/runs/paypal-live"
EARLY_SHA256 = "07609306e1310420c49e9908ee26b2da361e42028ea6f40b5d19005d47498288"
LATE_SHA256 = "c82dc46148d2dc985de77d051177c67d1d9c7d7d9a760242d2a3758e3d91f88e"


class PublicReplayTests(unittest.TestCase):
    def setUp(self):
        # If replay accidentally gains a network path, fail before connecting.
        self.network = patch("socket.socket.connect", side_effect=AssertionError("Replay must stay offline")).start()
        self.addCleanup(patch.stopall)

    def tearDown(self):
        self.network.assert_not_called()

    def load_unchanged(self, name, expected_hash):
        path = TAPES / name
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected_hash)
        return load_package(path)

    def test_early_recording_fails_defective_and_passes_healthy_with_same_promise(self):
        tape = self.load_unchanged("early-response-loss-input.json", EARLY_SHA256)
        original = deepcopy(tape)
        self.assertEqual(tape["invariant"], dict(DEFAULT_INVARIANT))
        self.assertEqual(tape["invariant"]["recovery_seconds"], 60)
        self.assertEqual((len(tape["steps"]), len(tape["records"])), (12, 15))
        defective, healthy = (replay(tape, variant) for variant in ("defective", "healthy"))
        self.assertEqual((defective["verdict"], defective["signature"], defective["ticket_count"]),
                         ("FAIL", "paid_without_ticket", 0))
        self.assertEqual((healthy["verdict"], healthy["signature"], healthy["ticket_count"]),
                         ("PASS", "ticket_delivered_once_on_time", 1))
        for field in ("input_sha256", "invariant", "deadline", "evaluation"):
            self.assertEqual(defective[field], healthy[field], field)
        self.assertEqual(tape, original)
        self.assertEqual(healthy["mode"], "RECORDED_REPLAY")
        self.assertEqual(healthy["network_calls"], 0)

    def test_original_late_recording_still_rejects_late_healthy_delivery(self):
        tape = self.load_unchanged("response-loss-input.json", LATE_SHA256)
        self.assertEqual(tape["invariant"]["recovery_seconds"], 60)
        defective, healthy = (replay(tape, variant) for variant in ("defective", "healthy"))
        self.assertEqual((defective["verdict"], defective["signature"]), ("FAIL", "paid_without_ticket"))
        self.assertEqual((healthy["verdict"], healthy["signature"]), ("FAIL", "ticket_delivered_late"))

    def test_both_variants_import_as_separate_finished_replay_cases(self):
        tape = self.load_unchanged("early-response-loss-input.json", EARLY_SHA256)
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "judge.sqlite3")
            defective, healthy = (import_replay(store, tape, variant) for variant in ("defective", "healthy"))
            self.assertNotEqual(defective["run_id"], healthy["run_id"])
            self.assertEqual(defective["input_sha256"], healthy["input_sha256"])
            self.assertEqual((defective["signature"], healthy["signature"]),
                             ("paid_without_ticket", "ticket_delivered_once_on_time"))
            for receipt in (defective, healthy):
                self.assertEqual(receipt["mode"], "RECORDED_REPLAY")
                self.assertFalse(receipt["fresh_execution"])
                self.assertEqual(receipt["network_calls"], 0)
            with store.connect() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM runs").fetchone()[0], 2)
                self.assertEqual(db.execute("SELECT count(*) FROM tickets").fetchone()[0], 1)
                self.assertEqual(db.execute("SELECT count(*) FROM jobs").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
