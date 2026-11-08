"""Install an already validated append-only Caddy candidate without changing its inode.

Run only after approval and existing-container validation of the exact candidate
hash. This helper does not validate, reload, deploy or contact any service.
"""
import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import re
import stat

HOSTNAME = b'workspace-crashcart.52.202.25.181.sslip.io'


def digest(body):
    return hashlib.sha256(body).hexdigest()


def _read_regular(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError('Regular configuration file required')
        data = handle.read(8 * 1024 * 1024 + 1)
    if len(data) > 8 * 1024 * 1024:
        raise ValueError('Configuration exceeds candidate limit')
    return data


def _replace_in_place(handle, data):
    handle.seek(0)
    view = memoryview(data)
    while view:
        written = handle.write(view)
        if not written:
            raise OSError('Incomplete configuration write')
        view = view[written:]
    handle.truncate()
    handle.flush()
    os.fsync(handle.fileno())


def install_validated(target, combined, expected_old, expected_validated, backup):
    """CAS under the original inode lock; preserve it for Docker file bind mounts."""
    if any(not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value)
           for value in (expected_old, expected_validated)):
        raise ValueError('Exact SHA-256 checksums required')
    candidate = _read_regular(combined)
    if digest(candidate) != expected_validated:
        raise ValueError('Validated candidate changed')
    fragment = _read_regular(Path(__file__).with_name('Caddyfile.fragment'))
    fd = os.open(target, os.O_RDWR | os.O_NOFOLLOW)
    with os.fdopen(fd, 'r+b', buffering=0) as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        info = os.fstat(handle.fileno())
        current_path = os.stat(target, follow_symlinks=False)
        if (not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) !=
                (current_path.st_dev, current_path.st_ino)):
            raise ValueError('Configuration identity changed')
        original = handle.read(8 * 1024 * 1024 + 1)
        if digest(original) != expected_old:
            raise ValueError('Current configuration changed; rebuild and revalidate')
        if HOSTNAME in original or candidate != original + b'\n' + fragment:
            raise ValueError('Only the reviewed new hostname may be appended')
        backup_fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(backup_fd, 'wb') as saved:
            saved.write(original);saved.flush();os.fsync(saved.fileno())
        directory_fd = os.open(Path(backup).parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        try:
            _replace_in_place(handle, candidate)
            handle.seek(0)
            if digest(handle.read()) != expected_validated:
                raise OSError('Installed checksum differs')
            open_info = os.fstat(handle.fileno())
            path_info = os.stat(target, follow_symlinks=False)
            if (open_info.st_dev, open_info.st_ino) != (path_info.st_dev, path_info.st_ino):
                raise ValueError('Configuration path identity changed during installation')
        except BaseException:
            # Local write failures restore the old bytes in the same inode.
            # Power loss still requires the durable exclusive backup to recover.
            _replace_in_place(handle, original)
            raise
    return expected_validated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target');parser.add_argument('combined')
    parser.add_argument('expected_old');parser.add_argument('expected_validated')
    parser.add_argument('backup')
    args = parser.parse_args()
    print(install_validated(args.target, args.combined, args.expected_old, args.expected_validated, args.backup))


if __name__ == '__main__':
    main()
