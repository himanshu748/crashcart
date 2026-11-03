#!/usr/bin/env python3
"""Validate CrashCart claims, never infer runtime success from the existence of code."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

IDS = tuple(f"CC-{number:03d}" for number in range(1, 61))
MODES = {"DOCUMENT_REVIEW", "LOCAL_TEST", "LIVE_SANDBOX", "RECORDED_REPLAY",
         "FRESH_SANDBOX", "SPONSOR_SERVICE"}
STATES = {"PENDING", "IN_PROGRESS", "IMPLEMENTED_UNVERIFIED", "BLOCKED", "FAILED",
          "STALE", "VERIFIED"}
ITEM = re.compile(r"^- \[([ xX])\] \*\*(CC-\d{3})\.(.*?)\*\*", re.MULTILINE)
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contained(root: Path, name: str) -> Path:
    """Resolve symlinks too: evidence may not escape the delivered repository."""
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError("file reference must be a nonempty repository-relative path")
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or ".." in Path(name).parts:
        raise ValueError(f"file reference escapes repository: {name}")
    return path


def read_json(root: Path, name: str):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(contained(root, name).read_text(), object_pairs_hook=unique_object)


def checklist_items(text: str) -> tuple[dict, list[str]]:
    matches = list(ITEM.finditer(text))
    counts = Counter(match.group(2) for match in matches)
    errors = [f"duplicate requirement ID {key}" for key, count in counts.items() if count != 1]
    errors += [f"missing requirement ID {key}" for key in IDS if key not in counts]
    errors += [f"unexpected requirement ID {key}" for key in counts if key not in IDS]
    items = {}
    for index, match in enumerate(matches):
        # Bind only this acceptance condition, excluding mutable checkbox/phase prose.
        tail = text[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        done = re.search(r"\*\*Done when:\*\*([^\n]+)", tail)
        verify = re.search(r"\*\*Verify:\*\*([^\n]+)", tail)
        if not done or not verify:
            errors.append(f"{match.group(2)} missing Done when or Verify acceptance text")
            continue
        acceptance = "\n".join(part.strip() for part in (match.group(3), done.group(1), verify.group(1)))
        items[match.group(2)] = {
            "checked": match.group(1).lower() == "x",
            "acceptance_sha256": hashlib.sha256(acceptance.encode()).hexdigest(),
        }
    return items, errors


def read_rules(root: Path) -> dict:
    rules = read_json(root, "scripts/requirements.json")
    if not isinstance(rules, dict) or set(rules) != set(IDS):
        raise ValueError("rules must contain exactly CC-001 through CC-060")
    for key, rule in rules.items():
        if not isinstance(rule, dict) or rule.get("phase") != (int(key[3:]) - 1) // 6 + 1:
            raise ValueError(f"invalid phase rule for {key}")
        modes, deps = rule.get("allowed_modes"), rule.get("dependencies")
        if not isinstance(modes, list) or not modes or not set(modes) <= MODES:
            raise ValueError(f"invalid proof modes for {key}")
        if not isinstance(deps, list) or len(set(deps)) != len(deps) or not set(deps) <= set(IDS) or key in deps:
            raise ValueError(f"invalid dependencies for {key}")
    visiting, seen = set(), set()
    def visit(key):
        if key in visiting:
            raise ValueError(f"dependency cycle at {key}")
        if key not in seen:
            visiting.add(key)
            for dep in rules[key]["dependencies"]:
                visit(dep)
            visiting.remove(key)
            seen.add(key)
    for key in IDS:
        visit(key)
    return rules


def review_errors(root: Path, review: object, *, independent=False) -> list[str]:
    if not isinstance(review, dict):
        return ["review must be an object"]
    errors = []
    if not review.get("reviewer") or review.get("result") != "PASS":
        errors.append("review is missing a reviewer or has not passed")
    if independent and review.get("independent") is not True:
        errors.append("independent review is required")
    try:
        if not contained(root, review.get("evidence")).is_file():
            errors.append("review evidence is missing")
    except (ValueError, TypeError) as exc:
        errors.append(str(exc))
    findings = review.get("findings")
    if not isinstance(findings, list):
        errors.append("review findings must be an explicit list")
    else:
        for finding in findings:
            if not isinstance(finding, dict) or finding.get("status") not in {"open", "resolved"}:
                errors.append("invalid review finding")
            elif finding.get("severity") == "blocking" and finding["status"] != "resolved":
                errors.append(f"unresolved blocking review finding: {finding.get('id', 'unnamed')}")
    return errors


def review_binding(root: Path, phase: int) -> dict:
    """Freeze both the review decision and the independently inspected artifact."""
    name = f"evidence/reviews/phase-{phase}.json"
    review = read_json(root, name)
    evidence = review["evidence"]
    return {"record": name, "sha256": digest(contained(root, name)),
            "evidence": evidence, "evidence_sha256": digest(contained(root, evidence))}


def record_errors(root: Path, key: str, record: object, item: dict, rule: dict) -> list[str]:
    errors = []
    if not isinstance(record, dict):
        return ["verification record must be an object"]
    if record.get("item_id") != key or record.get("status") != "VERIFIED":
        errors.append("record ID/status does not support checkmark")
    if record.get("mode") not in rule["allowed_modes"]:
        errors.append(f"wrong proof mode; requires {', '.join(rule['allowed_modes'])}")
    if record.get("acceptance_sha256") != item["acceptance_sha256"]:
        errors.append("acceptance text is stale or unbound")
    for field in ("run_id", "command_or_action", "expected_result", "observed_result", "executed_at"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            errors.append(f"missing {field}")
    try:
        timestamp = datetime.fromisoformat(record.get("executed_at", "").replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            errors.append("executed_at must include a timezone")
    except (ValueError, TypeError, AttributeError):
        errors.append("executed_at must be an ISO 8601 timestamp")
    environment = record.get("environment")
    if not isinstance(environment, dict) or not environment or any(not value for value in environment.values()):
        errors.append("environment must identify the actual verification environment")
    expected, observed = record.get("expected_exit_code"), record.get("observed_exit_code")
    if expected is not None or observed is not None:
        if type(expected) is not int or type(observed) is not int or expected != observed:
            errors.append("expected and observed exit codes must match")
    elif record.get("mode") != "DOCUMENT_REVIEW":
        errors.append("runtime proof requires expected and observed exit codes")
    dependencies = record.get("dependencies")
    if not isinstance(dependencies, list) or set(dependencies) != set(rule["dependencies"]):
        errors.append("record dependencies do not match the fixed requirement rules")

    evidence = record.get("evidence_files")
    if not isinstance(evidence, list) or not evidence:
        errors.append("missing evidence artifacts")
        evidence = []
    elif len(set(evidence)) != len(evidence):
        errors.append("duplicate evidence artifact reference")
    artifact_hashes = record.get("evidence_sha256")
    if not isinstance(artifact_hashes, dict) or set(artifact_hashes) != set(evidence):
        errors.append("all evidence artifacts require SHA-256 bindings")
        artifact_hashes = {}
    for name in evidence:
        try:
            path = contained(root, name)
            if not path.is_file():
                errors.append(f"missing artifact: {name}")
            elif digest(path) != artifact_hashes.get(name):
                errors.append(f"stale artifact hash: {name}")
        except (ValueError, TypeError) as exc:
            errors.append(str(exc))
    result = record.get("result")
    assertions = result.get("assertions") if isinstance(result, dict) else None
    if not isinstance(result, dict) or result.get("outcome") != "PASS" or not isinstance(assertions, list) or not assertions:
        errors.append("specific passing structured assertions are required")
    else:
        for assertion in assertions:
            if (not isinstance(assertion, dict) or not isinstance(assertion.get("name"), str)
                    or not assertion.get("name", "").strip() or assertion.get("passed") is not True
                    or assertion.get("evidence") not in evidence):
                errors.append("assertion must pass and reference a bound evidence artifact")

    hashes = record.get("relevant_source_hashes")
    if not isinstance(hashes, dict) or not hashes:
        errors.append("missing relevant source hashes")
        hashes = {}
    if hashes.get("scripts/requirements.json") != digest(root / "scripts/requirements.json"):
        errors.append("requirement rules are stale or unbound")
    snapshot = record.get("source_snapshot")
    commit = record.get("source_commit")
    if not snapshot and not commit:
        errors.append("source commit or equivalent source snapshot is required")
    if snapshot:
        try:
            snapshot = contained(root, snapshot)
            if not snapshot.is_dir() or not snapshot.is_relative_to(root / "evidence"):
                errors.append("source snapshot must be a directory under evidence/")
                snapshot = None
        except (ValueError, TypeError) as exc:
            errors.append(str(exc))
            snapshot = None
    if commit and (not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit)):
        errors.append("source_commit must be a full Git SHA or null for an unborn repository")
        commit = None
    if commit:
        resolved = subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=root,
                                  capture_output=True, check=False)
        if resolved.returncode:
            errors.append("source_commit does not identify an available Git commit")
    for name, expected_hash in hashes.items():
        try:
            path = contained(root, name)
            if not isinstance(expected_hash, str) or not SHA256.fullmatch(expected_hash):
                errors.append(f"invalid source hash: {name}")
            elif not path.is_file() or digest(path) != expected_hash:
                errors.append(f"stale source hash: {name}")
            if snapshot:
                frozen = contained(snapshot, name)
                if not frozen.is_file() or digest(frozen) != expected_hash:
                    errors.append(f"source snapshot mismatch: {name}")
            elif commit:
                frozen = subprocess.run(["git", "show", f"{commit}:{name}"], cwd=root,
                                        capture_output=True, check=False)
                if frozen.returncode or hashlib.sha256(frozen.stdout).hexdigest() != expected_hash:
                    errors.append(f"commit does not contain tested source; preserve a snapshot: {name}")
        except (ValueError, TypeError, OSError) as exc:
            errors.append(str(exc))
    if rule.get("independent_review_required") or record.get("review") is not None:
        errors.extend(review_errors(root, record.get("review"), independent=rule.get("independent_review_required", False)))
        if isinstance(record.get("review"), dict) and record["review"].get("evidence") not in evidence:
            errors.append("review artifact must be included in bound evidence_files")
    if key == "CC-060":
        try:
            if record.get("release_report") not in evidence:
                raise ValueError("CC-060 must bind the inspected release report as evidence")
            audit = read_json(root, record["release_report"])
            if (audit.get("mode") != "release" or audit.get("ok") is not True
                    or audit.get("required_count") != 59 or set(audit.get("verified_ids", [])) != set(IDS[:-1])):
                errors.append("CC-060 release report did not pass all first 59 requirements")
            for preceding in IDS[:-1]:
                path = contained(root, f"evidence/{preceding}/verification.json")
                if not path.is_file() or audit.get("verification_sha256", {}).get(preceding) != digest(path):
                    errors.append(f"CC-060 release report is stale: {preceding}")
            for phase in range(1, 11):
                binding = review_binding(root, phase)
                if audit.get("phase_reviews", {}).get(str(phase)) != binding:
                    errors.append(f"CC-060 phase review or its artifact is stale: phase {phase}")
                errors.extend(f"CC-060 phase {phase} review: {error}" for error in
                              review_errors(root, read_json(root, binding["record"]), independent=True))
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            errors.append(f"CC-060 release audit missing or invalid: {exc}")
    return errors


def validate(root: Path, mode="progress", phase=None) -> dict:
    root = root.resolve()
    errors = []
    try:
        items, errors = checklist_items(contained(root, "BUILD_CHECKLIST.md").read_text())
        rules = read_rules(root)
    except (OSError, ValueError, TypeError) as exc:
        return {"ok": False, "mode": mode, "verified_count": 0, "errors": [str(exc)]}
    checked = {key for key, item in items.items() if item["checked"]}
    # Release produces the input to CC-060, so never depends on its own record.
    considered = checked - {"CC-060"} if mode == "release" else checked
    valid, records, open_states = set(), {}, {}
    for key in IDS:
        name = f"evidence/{key}/verification.json"
        try:
            record = read_json(root, name) if contained(root, name).is_file() else None
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"{key}: invalid record: {exc}")
            continue
        records[key] = record
        if key in considered:
            try:
                failures = record_errors(root, key, record, items[key], rules[key])
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                failures = [f"malformed verification record: {exc}"]
            if failures:
                errors.extend(f"{key}: {failure}" for failure in failures)
            else:
                valid.add(key)
        elif key not in checked:
            state = record.get("status", "PENDING") if isinstance(record, dict) else "PENDING"
            if state not in STATES or state == "VERIFIED":
                errors.append(f"{key}: unchecked requirement has invalid or VERIFIED record state")
            open_states[key] = state
    # A dependency whose own evidence is invalid cannot support another checkmark.
    while True:
        removed = {key for key in valid if not set(rules[key]["dependencies"]) <= valid}
        if not removed:
            break
        for key in sorted(removed):
            missing = sorted(set(rules[key]["dependencies"]) - valid)
            errors.append(f"{key}: unsatisfied dependencies: {', '.join(missing)}")
        valid -= removed
    required, phase_reviews = set(), {}
    if mode == "phase":
        if type(phase) is not int or not 1 <= phase <= 10:
            errors.append("phase must be an integer from 1 to 10")
        else:
            required = {key for key in IDS if rules[key]["phase"] == phase}
            try:
                review = read_json(root, f"evidence/reviews/phase-{phase}.json")
                errors.extend(f"phase review: {error}" for error in review_errors(root, review, independent=True))
                if set(review.get("item_ids", [])) != required:
                    errors.append("phase review must identify every requirement in the phase")
                reviewed = review.get("verification_sha256", {})
                for key in required:
                    path = contained(root, f"evidence/{key}/verification.json")
                    if not path.is_file() or reviewed.get(key) != digest(path):
                        errors.append(f"phase review is stale or missing record hash: {key}")
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                errors.append(f"phase review missing or invalid: {exc}")
    elif mode == "release":
        required = set(IDS[:-1])
        for number in range(1, 11):
            # The final phase's review precedes CC-060; bind its first five items.
            phase_ids = {key for key in required if rules[key]["phase"] == number}
            try:
                review = read_json(root, f"evidence/reviews/phase-{number}.json")
                phase_reviews[str(number)] = review_binding(root, number)
                errors.extend(f"phase {number} review: {error}" for error in review_errors(root, review, independent=True))
                if not phase_ids <= set(review.get("item_ids", [])):
                    errors.append(f"phase {number} review does not cover its release requirements")
                for key in phase_ids:
                    path = contained(root, f"evidence/{key}/verification.json")
                    if not path.is_file() or review.get("verification_sha256", {}).get(key) != digest(path):
                        errors.append(f"phase {number} review is stale or missing record hash: {key}")
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
                errors.append(f"phase {number} review missing or invalid: {exc}")
    elif mode != "progress":
        errors.append("unknown validation mode")
    for key in sorted(required - valid):
        errors.append(f"{key}: required by {mode} gate but not verified")
    return {
        "schema_version": 1, "mode": mode, "phase": phase, "ok": not errors,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verified_count": len(valid), "total": 60, "required_count": len(required),
        "verified_ids": sorted(valid), "open_states": open_states, "errors": errors,
        "proof_modes": dict(Counter(records[key]["mode"] for key in valid)),
        "verification_sha256": {key: digest(root / f"evidence/{key}/verification.json") for key in valid},
        "phase_reviews": phase_reviews,
        "limitations": ["Mechanical validation does not authenticate narrative claims or prove product usefulness.",
                        "Release validates CC-001 through CC-059; CC-060 requires inspection of this report."],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("progress", "phase", "release"), nargs="?", default="progress")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--phase", type=int)
    parser.add_argument("--report", help="repository-relative JSON report output (required for release)")
    args = parser.parse_args(argv)
    if args.mode == "release" and not args.report:
        parser.error("release requires --report evidence/CC-060/release-report.json")
    report = validate(args.root, args.mode, args.phase)
    if args.report:
        try:
            path = contained(args.root.resolve(), args.report)
            if not path.is_relative_to(args.root.resolve() / "evidence"):
                raise ValueError("reports must be written under evidence/")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=2) + "\n")
        except (OSError, ValueError) as exc:
            print(f"Report error: {exc}", file=sys.stderr)
            return 2
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
