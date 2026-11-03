#!/usr/bin/env python3
"""Local operator import of a reviewed prior execution; no provider/network calls.

The private manifest explicitly attests reviewed artifact identities/hashes.
This is not a provider signature. Default is validation only; --apply appends
events and private references to an existing database, never payment state.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crashcart.kernel_evidence import KernelEvidenceError, import_kernel_receipt, require
from crashcart.store import Store


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        require(args.db.is_file() and not args.db.is_symlink(), "EXISTING_DATABASE_REQUIRED")
        with closing(sqlite3.connect(args.db.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            require(db.execute("PRAGMA user_version").fetchone()[0] == 1, "EXISTING_SCHEMA_REQUIRED")
        result = import_kernel_receipt(Store(args.db), args.manifest, args.artifact_root, apply=args.apply)
        print(json.dumps(result, sort_keys=True)); return 0
    except KernelEvidenceError as exc:
        print(json.dumps({"status": "REJECTED", "error": str(exc)})); return 1
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError):
        print(json.dumps({"status": "REJECTED", "error": "IMPORT_FAILED"})); return 1


if __name__ == "__main__": raise SystemExit(main())
