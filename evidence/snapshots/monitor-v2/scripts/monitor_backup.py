#!/usr/bin/env python3
"""Create a consistent private SQLite backup without replacing an existing file."""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import time


def backup(source, destination):
    source, destination = Path(source), Path(destination)
    if not source.is_file():
        raise ValueError('Source database does not exist')
    destination.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    deadline = time.monotonic() + 10
    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise TimeoutError('Backup exceeded ten seconds')
    with closing(sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True, timeout=5)) as origin:
        with closing(sqlite3.connect(destination, timeout=5)) as copied:
            origin.backup(copied, pages=128, progress=progress, sleep=0.05)
            if copied.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('Backup integrity check failed')
            required = {'monitor_stores', 'monitor_events', 'monitor_orders',
                        'monitor_payments', 'monitor_associations', 'monitor_alerts'}
            tables = {row[0] for row in copied.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not required.issubset(tables):
                raise ValueError('Backup is not a supported monitoring database')
            if copied.execute('PRAGMA foreign_key_check').fetchall():
                raise ValueError('Backup contains inconsistent references')
    destination.chmod(0o600)
    return {'status': 'ok', 'destination': str(destination), 'integrity_check': 'ok',
            'permissions': '0600', 'boundary': 'SQLite snapshot; not host disaster recovery'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('destination')
    args = parser.parse_args()
    try:
        result = backup(args.source, args.destination)
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f'Backup not completed ({type(error).__name__}); any destination file is retained.\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
