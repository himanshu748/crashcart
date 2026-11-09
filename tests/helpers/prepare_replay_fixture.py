"""Separate, bounded offline fixture setup; never adjusts a product deadline.

Writes actual keyless replay data with before/after source hashes. No env loader,
provider adapter or network call. The 120-second setup bound is independent of
the unchanged 60-second recorded delivery rule and 180-second AI run bound.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import sys

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name('replay_fixture_sources.json')
SETUP_SECONDS = 120


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_hashes():
    names = json.loads(MANIFEST.read_text())
    if not isinstance(names, list) or not names or len(names) != len(set(names)):
        raise ValueError('Invalid fixture source manifest')
    result = {}
    for name in names:
        path = Path(name)
        if not isinstance(name, str) or path.is_absolute() or '..' in path.parts or path.as_posix() != name:
            raise ValueError('Fixture source path rejected')
        result[name] = sha((ROOT / name).read_bytes())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    os.umask(0o077)
    def expired(*_):
        raise TimeoutError('Offline replay fixture setup exceeded its separate 120-second bound')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(SETUP_SECONDS)
    def offline(*_args, **_kwargs):
        raise RuntimeError('Replay fixture setup forbids networking')
    socket.socket.connect = offline
    socket.getaddrinfo = offline
    sys.path.insert(0, str(ROOT))
    before = source_hashes()
    from crashcart.judge import prepare_review
    data = json.loads(prepare_review()['data.json'][1])
    if data['mode'] != 'RECORDED_REPLAY' or data['fresh_execution'] is not False or data['network_calls'] != 0:
        raise ValueError('Replay fixture lost its offline scope')
    if before != source_hashes():
        raise ValueError('Replay fixture sources changed during setup')
    encoded = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    result = {'kind': 'crashcart-ui-replay-fixture-v1', 'scope': 'recorded-offline-replay',
              'generated_at': datetime.now(timezone.utc).isoformat(), 'setup_bound_seconds': SETUP_SECONDS,
              'network_calls': 0, 'source_sha256': before, 'data_sha256': sha(encoded.encode()), 'data_json': encoded}
    raw = (json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    # Canonicalize an existing parent first; macOS /tmp and /var are legitimate
    # system aliases. The final file is still exclusive, no-follow and 0600.
    requested = args.output.absolute()
    destination = requested.parent.resolve(strict=True) / requested.name
    if not destination.parent.is_dir():
        raise ValueError('An existing real output directory is required')
    fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw);handle.flush();os.fsync(handle.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    finally:
        signal.alarm(0)
    print(json.dumps({'fixture': str(destination), 'kind': result['kind'], 'source_files': len(before),
                      'data_sha256': result['data_sha256'], 'network_calls': 0, 'cases': len(data['cases'])}), flush=True)


if __name__ == '__main__':
    main()
