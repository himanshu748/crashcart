"""The public failure summary is a projection of already-public evidence, not inference."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from crashcart.recorded_ai import SUMMARY, SUMMARY_SHA256, failure_ai
from crashcart.replay import ReplayError


class RecordedFailureAiTests(unittest.TestCase):
    def test_pinned_trace_matches_public_payment_and_model_records(self):
        proof_path = Path(__file__).resolve().parents[1] / 'evidence/runs/submission-ready/live-flow-nov8/proof.json'
        proof = json.loads(proof_path.read_bytes())
        summary = failure_ai()
        self.assertEqual(SUMMARY_SHA256, hashlib.sha256(SUMMARY.read_bytes()).hexdigest())
        self.assertEqual(summary['proof_sha256'], hashlib.sha256(proof_path.read_bytes()).hexdigest())
        self.assertFalse(summary['fresh_execution'])
        self.assertFalse(summary['same_case_as_public_faulty_replay'])
        for step, call in zip(summary['trace'], proof['actual_model_calls']):
            self.assertEqual(step['action'], call['tool'])
            self.assertEqual(step['hypothesis'], call['hypothesis'])
            self.assertEqual(step['findings'], call['findings'])
        for key, value in summary['deterministic_result'].items():
            self.assertEqual(value, proof['investigation_job']['result']['final_verdict'][key])
        for forbidden in ('payer', 'api_key', 'client_secret', 'private_source_bindings', '/Users/'):
            self.assertNotIn(forbidden, json.dumps(summary))

    def test_changed_bytes_and_unsupported_citations_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'summary.json'
            path.write_bytes(SUMMARY.read_bytes() + b' ')
            with self.assertRaises(ReplayError):
                failure_ai(path)
            original = json.loads(SUMMARY.read_bytes())
            for change in ('citation', 'action', 'verdict', 'fresh'):
                source = deepcopy(original)
                if change == 'citation':
                    source['trace'][2]['findings'][0]['evidence_ids'] = ['unknown-record']
                elif change == 'action':
                    source['trace'][0]['action'] = 'capture_payment'
                elif change == 'verdict':
                    source['deterministic_result']['verdict'] = 'PASS'
                else:
                    source['fresh_execution'] = True
                raw = json.dumps(source).encode()
                path.write_bytes(raw)
                with self.subTest(change=change), patch('crashcart.recorded_ai.SUMMARY_SHA256', hashlib.sha256(raw).hexdigest()):
                    with self.assertRaises(ReplayError):
                        failure_ai(path)
