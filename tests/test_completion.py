"""Adversarial mechanical checks; generated receipts here are synthetic test fixtures."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_completion", REPO / "scripts/check_completion.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


class CompletionCheckerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "scripts").mkdir()
        shutil.copy(REPO / "scripts/requirements.json", self.root / "scripts/requirements.json")
        self.rules = checker.read_rules(self.root)
        text = (REPO / "BUILD_CHECKLIST.md").read_text().replace("- [x] **CC-", "- [ ] **CC-")
        (self.root / "BUILD_CHECKLIST.md").write_text(text)
        (self.root / "sample.py").write_text("# synthetic checker test source\n")
        self.snapshot = self.root / "evidence/snapshots/test"
        (self.snapshot / "scripts").mkdir(parents=True)
        shutil.copy(self.root / "sample.py", self.snapshot / "sample.py")
        shutil.copy(self.root / "scripts/requirements.json", self.snapshot / "scripts/requirements.json")

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n")

    def mark(self, key):
        path = self.root / "BUILD_CHECKLIST.md"
        path.write_text(path.read_text().replace(f"- [ ] **{key}.", f"- [x] **{key}."))

    def verify(self, key, *, dependencies=True):
        if dependencies:
            for dep in self.rules[key]["dependencies"]:
                if not (self.root / f"evidence/{dep}/verification.json").is_file():
                    self.verify(dep)
        artifact = f"evidence/{key}/result.json"
        self.write(artifact, {"synthetic_test_fixture": True, "checked": key})
        review_artifact = f"evidence/{key}/review.txt"
        (self.root / review_artifact).write_text("Synthetic independent review for checker unit test only.\n")
        items, errors = checker.checklist_items((self.root / "BUILD_CHECKLIST.md").read_text())
        self.assertEqual(errors, [])
        record = {
            "item_id": key, "status": "VERIFIED", "mode": self.rules[key]["allowed_modes"][0],
            "source_commit": None, "source_snapshot": "evidence/snapshots/test",
            "relevant_source_hashes": {name: checker.digest(self.root / name)
                                       for name in ("sample.py", "scripts/requirements.json")},
            "acceptance_sha256": items[key]["acceptance_sha256"],
            "environment": {"runtime": "synthetic isolated unit-test fixture"},
            "run_id": "synthetic-checker-test", "command_or_action": "unit-test fixture",
            "expected_result": "specific synthetic condition holds", "observed_result": "specific synthetic condition holds",
            "expected_exit_code": 0, "observed_exit_code": 0,
            "executed_at": "2026-10-22T12:00:00+05:30",
            "evidence_files": [artifact, review_artifact],
            "evidence_sha256": {name: checker.digest(self.root / name) for name in (artifact, review_artifact)},
            "dependencies": self.rules[key]["dependencies"],
            "result": {"outcome": "PASS", "assertions": [{"name": "synthetic condition", "passed": True, "evidence": artifact}]},
        }
        if self.rules[key]["independent_review_required"]:
            record["review"] = {"reviewer": "synthetic-test-reviewer", "independent": True,
                                "result": "PASS", "findings": [], "evidence": review_artifact}
        self.write(f"evidence/{key}/verification.json", record)
        self.mark(key)
        return record

    def modify(self, key, transform):
        record = checker.read_json(self.root, f"evidence/{key}/verification.json")
        transform(record)
        self.write(f"evidence/{key}/verification.json", record)

    def reject(self, expected):
        report = checker.validate(self.root)
        self.assertFalse(report["ok"], report)
        self.assertIn(expected, "\n".join(report["errors"]))
        return report

    def phase_review(self, phase, exclude_final=False):
        keys = [key for key in checker.IDS if self.rules[key]["phase"] == phase and not (exclude_final and key == "CC-060")]
        artifact = f"evidence/reviews/phase-{phase}.txt"
        (self.root / artifact).parent.mkdir(parents=True, exist_ok=True)
        (self.root / artifact).write_text("Synthetic phase review for checker unit test only.\n")
        review = {"reviewer": "synthetic-test-reviewer", "independent": True, "result": "PASS",
                  "findings": [], "evidence": artifact, "item_ids": keys,
                  "verification_sha256": {key: checker.digest(self.root / f"evidence/{key}/verification.json") for key in keys}}
        self.write(f"evidence/reviews/phase-{phase}.json", review)

    def test_honest_incomplete_progress_passes(self):
        report = checker.validate(self.root)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["verified_count"], 0)
        self.assertEqual(len(report["open_states"]), 60)

    def test_verified_receipt_with_unborn_head_snapshot_passes(self):
        self.verify("CC-001")
        report = checker.validate(self.root)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["verified_ids"], ["CC-001"])

    def test_unsupported_checkmark_rejected(self):
        self.mark("CC-001")
        self.reject("verification record must be an object")

    def test_missing_artifact_rejected(self):
        self.verify("CC-001")
        (self.root / "evidence/CC-001/result.json").unlink()
        self.reject("missing artifact")

    def test_stale_source_hash_rejected(self):
        self.verify("CC-001")
        (self.root / "sample.py").write_text("# modified after verification\n")
        self.reject("stale source hash")

    def test_stale_artifact_hash_rejected(self):
        self.verify("CC-001")
        (self.root / "evidence/CC-001/result.json").write_text('{"tampered": true}\n')
        self.reject("stale artifact hash")

    def test_wrong_mode_cannot_be_self_selected(self):
        self.verify("CC-008")
        self.modify("CC-008", lambda record: record.update(mode="LOCAL_TEST"))
        self.reject("wrong proof mode")

    def test_omitting_fixed_dependency_is_rejected(self):
        self.verify("CC-006")
        self.modify("CC-006", lambda record: record.update(dependencies=[]))
        self.reject("dependencies do not match")

    def test_unverified_dependency_rejected(self):
        self.verify("CC-006", dependencies=False)
        self.reject("unsatisfied dependencies: CC-003")

    def test_stale_dependency_invalidates_its_dependent(self):
        self.verify("CC-006")
        (self.root / "evidence/CC-003/result.json").unlink()
        report = self.reject("unsatisfied dependencies: CC-003")
        self.assertNotIn("CC-006", report["verified_ids"])

    def test_failed_review_rejected(self):
        self.verify("CC-001")
        self.modify("CC-001", lambda record: record.update(review={"reviewer": "reviewer", "result": "FAIL",
                    "evidence": "evidence/CC-001/review.txt", "findings": []}))
        self.reject("review is missing a reviewer or has not passed")

    def test_open_blocking_review_finding_rejected(self):
        self.verify("CC-001")
        self.modify("CC-001", lambda record: record.update(review={"reviewer": "reviewer", "result": "PASS",
                    "evidence": "evidence/CC-001/review.txt", "findings": [{"id": "R1", "severity": "blocking", "status": "open"}]}))
        self.reject("unresolved blocking review finding")

    def test_duplicate_checklist_id_rejected(self):
        path = self.root / "BUILD_CHECKLIST.md"
        path.write_text(path.read_text() + "\n- [ ] **CC-001. Duplicate.**\n  **Done when:** A\n  **Verify:** B\n")
        self.reject("duplicate requirement ID CC-001")

    def test_missing_checklist_id_rejected(self):
        path = self.root / "BUILD_CHECKLIST.md"
        path.write_text(path.read_text().replace("- [ ] **CC-001.", "- [ ] **REMOVED-001."))
        self.reject("missing requirement ID CC-001")

    def test_duplicate_json_rule_id_rejected(self):
        path = self.root / "scripts/requirements.json"
        path.write_text('{"CC-001": {}, "CC-001": {}}')
        self.reject("duplicate JSON key")

    def test_outside_repository_artifact_rejected(self):
        self.verify("CC-001")
        self.modify("CC-001", lambda record: record.update(evidence_files=["../outside.txt"], evidence_sha256={"../outside.txt": "0" * 64}))
        self.reject("escapes repository")

    def test_symlink_escape_rejected(self):
        self.verify("CC-001")
        path = self.root / "evidence/CC-001/result.json"
        path.unlink()
        path.symlink_to(REPO / "BUILD_CHECKLIST.md")
        self.reject("escapes repository")

    def test_missing_snapshot_rejected(self):
        self.verify("CC-001")
        self.modify("CC-001", lambda record: record.update(source_snapshot=None))
        self.reject("source commit or equivalent source snapshot is required")

    def test_snapshot_mismatch_rejected(self):
        self.verify("CC-001")
        (self.snapshot / "sample.py").write_text("# not tested source\n")
        self.reject("source snapshot mismatch")

    def test_environment_and_structured_assertions_required(self):
        self.verify("CC-001")
        self.modify("CC-001", lambda record: record.update(environment={}, result={"outcome": "PASS", "assertions": []}))
        self.reject("environment must identify")
        self.reject("specific passing structured assertions")

    def test_runtime_exit_codes_must_match(self):
        self.verify("CC-006")
        self.modify("CC-006", lambda record: record.update(observed_exit_code=1))
        self.reject("expected and observed exit codes must match")

    def test_expected_nonzero_regression_outcome_is_valid(self):
        self.verify("CC-006")
        self.modify("CC-006", lambda record: record.update(expected_exit_code=1, observed_exit_code=1))
        self.assertTrue(checker.validate(self.root)["ok"])

    def test_acceptance_change_is_stale_but_checkbox_change_is_not(self):
        self.verify("CC-001")
        self.assertTrue(checker.validate(self.root)["ok"])
        path = self.root / "BUILD_CHECKLIST.md"
        path.write_text(path.read_text().replace("USD 29 ticket fixture", "USD 30 ticket fixture"))
        self.reject("acceptance text is stale or unbound")

    def test_malformed_record_is_error_not_checker_crash(self):
        self.verify("CC-001")
        self.modify("CC-001", lambda record: record.update(evidence_files=[{}]))
        self.reject("malformed verification record")

    def test_unchecked_verified_record_rejected(self):
        self.verify("CC-001")
        path = self.root / "BUILD_CHECKLIST.md"
        path.write_text(path.read_text().replace("- [x] **CC-001.", "- [ ] **CC-001."))
        self.reject("unchecked requirement has invalid or VERIFIED record state")

    def test_phase_gate_rejects_incomplete_and_requires_review(self):
        report = checker.validate(self.root, "phase", 1)
        self.assertFalse(report["ok"])
        self.assertTrue(any("required by phase gate" in error for error in report["errors"]))
        for number in range(1, 7):
            self.verify(f"CC-{number:03d}")
        self.assertFalse(checker.validate(self.root, "phase", 1)["ok"])
        self.phase_review(1)
        self.assertTrue(checker.validate(self.root, "phase", 1)["ok"])
        self.modify("CC-001", lambda record: record.update(run_id="changed-after-review"))
        self.assertTrue(any("phase review is stale" in error for error in checker.validate(self.root, "phase", 1)["errors"]))

    def test_release_requires_59_without_own_final_evidence(self):
        report = checker.validate(self.root, "release")
        self.assertFalse(report["ok"])
        self.assertEqual(report["required_count"], 59)
        for key in checker.IDS[:-1]:
            self.verify(key)
        for phase in range(1, 11):
            self.phase_review(phase, exclude_final=True)
        report = checker.validate(self.root, "release")
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["verified_count"], 59)
        self.assertFalse((self.root / "evidence/CC-060/verification.json").exists())
        self.write("evidence/CC-060/release-report.json", report)
        malformed_review_path = self.root / "evidence/reviews/phase-1.json"
        original_phase_review = malformed_review_path.read_bytes()
        malformed_review = json.loads(original_phase_review)
        malformed_review.pop("evidence")
        malformed_review_path.write_text(json.dumps(malformed_review))
        rejected_release = checker.validate(self.root, "release")
        self.assertFalse(rejected_release["ok"])
        self.assertTrue(any("phase 1 review missing or invalid" in error for error in rejected_release["errors"]))
        malformed_review_path.write_bytes(original_phase_review)
        self.verify("CC-060")
        self.modify("CC-060", lambda record: record.update(
            release_report="evidence/CC-060/release-report.json",
            evidence_files=record["evidence_files"] + ["evidence/CC-060/release-report.json"],
            evidence_sha256={**record["evidence_sha256"], "evidence/CC-060/release-report.json": checker.digest(self.root / "evidence/CC-060/release-report.json")}))
        final = checker.validate(self.root)
        self.assertTrue(final["ok"], final)
        self.assertEqual(final["verified_count"], 60)
        # A final verdict is revocable: reviews are evidence, not an unchecked
        # narrative attachment that can fail or disappear after release.
        review_path = self.root / "evidence/reviews/phase-1.json"
        artifact_path = self.root / "evidence/reviews/phase-1.txt"
        original_review = review_path.read_bytes()
        original_artifact = artifact_path.read_bytes()
        failed_review = json.loads(original_review)
        failed_review.update(result="FAIL", findings=[{"id": "late-blocker", "severity": "blocking", "status": "open"}])
        mutations = {
            "late failing decision": lambda: review_path.write_text(json.dumps(failed_review)),
            "deleted review": review_path.unlink,
            "changed inspected artifact": lambda: artifact_path.write_text("Late unresolved blocking finding\n"),
            "deleted inspected artifact": artifact_path.unlink,
        }
        for label, mutate in mutations.items():
            with self.subTest(label=label):
                mutate()
                reopened = checker.validate(self.root)
                self.assertFalse(reopened["ok"], reopened)
                self.assertNotIn("CC-060", reopened["verified_ids"])
                self.assertEqual(reopened["verified_count"], 59)
            review_path.write_bytes(original_review)
            artifact_path.write_bytes(original_artifact)


if __name__ == "__main__":
    unittest.main()
