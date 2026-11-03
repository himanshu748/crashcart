#!/usr/bin/env python3
"""Exercise the delivered package in a clean directory and database, no secrets."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import sqlite3
import re

ROOT = Path(__file__).resolve().parent.parent


def run():
    print(json.dumps({"python": sys.version, "executable": sys.executable, "sqlite": sqlite3.sqlite_version, "mode": "LOCAL_TEST"}))
    with tempfile.TemporaryDirectory(prefix="crashcart-clean-") as tmp:
        clean = Path(tmp)
        for folder in ("crashcart", "web", "migrations"):
            shutil.copytree(ROOT / folder, clean / folder, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(ROOT / ".env.example", clean / ".env.example")
        env = {key: val for key, val in os.environ.items() if not key.startswith(("PAYPAL_", "OPENAI_", "KERNEL_", "CRASHCART_"))}
        def command(*args):
            proc = subprocess.run([sys.executable, "-m", "crashcart", *args], cwd=clean, env=env, capture_output=True, text=True, timeout=20)
            print(json.dumps({"command": "python3 -m crashcart " + " ".join(args), "exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}))
            assert proc.returncode == 0
        command("setup")
        command("migrate")
        command("migrate")
        command("worker", "--once")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = subprocess.Popen([sys.executable, "-m", "crashcart", "serve", "--port", str(port)], cwd=clean, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            for _ in range(80):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1) as response:
                        health = json.load(response)
                    break
                except OSError:
                    time.sleep(.05)
            else:
                raise AssertionError("clean service never became healthy")
            assert health["database"] == "ok"
            print(json.dumps({"health": health}))
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/fixture") as response:
                fixture = json.load(response)
            assert fixture["amount_minor"] == 2900 and fixture["currency"] == "USD" and fixture["recovery_seconds"] == 60
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as response:
                html = response.read().decode()
            assert "CrashCart" in html and "29.00" in re.sub(r"<[^>]+>", "", html)
            print(json.dumps({"fixture": fixture, "web_document": "served", "clean_database": True, "assertions": "PASS"}))
        finally:
            server.terminate()
            stdout, stderr = server.communicate(timeout=5)
            print(json.dumps({"server_stdout": stdout, "server_stderr": stderr}))


if __name__ == "__main__":
    run()
