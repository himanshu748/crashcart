import argparse
import json
import os
import secrets
from pathlib import Path

from .config import load_env, prerequisites


def main():
    parser = argparse.ArgumentParser(description="CrashCart owned sandbox merchant")
    parser.add_argument("command", choices=["setup", "migrate", "serve", "worker", "prerequisites"])
    parser.add_argument("--db", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.command == "setup":
        target = Path(".env")
        if target.exists():
            raise SystemExit(".env exists; preserved. Edit its missing fields locally.")
        template = Path(".env.example").read_text()
        with open(target, "x", opener=lambda path, flags: os.open(path, flags, 0o600)) as file:
            file.write(template.replace("CRASHCART_OPERATOR_TOKEN=\n", "CRASHCART_OPERATOR_TOKEN=" + secrets.token_urlsafe(32) + "\n"))
        print("Created private .env with local operator token. Service credentials remain unset.")
        return
    load_env()
    db = args.db or os.environ.get("CRASHCART_DB", "var/crashcart.sqlite3")
    if args.command == "prerequisites":
        print(json.dumps(prerequisites(), indent=2))
    elif args.command == "migrate":
        from .store import Store
        Store(db).migrate()
        print("Migrations applied; workshop-v1 seeded (2900 USD, recovery 60s).")
    elif args.command == "serve":
        from .server import serve
        serve(db, os.environ.get("CRASHCART_HOST", "127.0.0.1"), args.port or int(os.environ.get("CRASHCART_PORT", "8765")))
    elif args.command == "worker":
        from .worker import work
        work(db, once=args.once)


if __name__ == "__main__":
    main()
