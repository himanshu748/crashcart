"""Private saved-video reads from a run's existing hash-bound evidence reference.

No filesystem path is accepted from HTTP. The caller authenticates the operator
and opts in on a loopback server. Only an imported kernel-video-v1 reference
confined to the owned var directory can be opened. Verified immutable bytes are
served, so a subsequent filesystem write cannot swap the streamed content.
"""

from dataclasses import dataclass
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import stat

MAX_VIDEO_BYTES = 64 * 1024 * 1024
RUN_ID = re.compile(r"run_[a-f0-9]{32}")
SHA = re.compile(r"[a-f0-9]{64}")


class RecordingUnavailable(ValueError):
    pass


class InvalidRange(ValueError):
    pass


@dataclass(frozen=True)
class Recording:
    body: bytes
    sha256: str

    @property
    def size(self):
        return len(self.body)


def enabled(server, environ):
    try:
        return (
            environ.get("CRASHCART_ALLOW_PRIVATE_RECORDINGS") == "1"
            and ipaddress.ip_address(server.server_address[0]).is_loopback
        )
    except (ValueError, AttributeError, IndexError):
        return False


def load_recording(store, run_id, private_root):
    """Read only one exact reference using no-follow opens for every component."""
    if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
        raise RecordingUnavailable("Saved checkout unavailable")
    refs = [r for r in store.get_evidence(run_id) if r["kind"] == "kernel-video-v1"]
    if len(refs) != 1 or not SHA.fullmatch(str(refs[0].get("sha256", ""))):
        raise RecordingUnavailable("Saved checkout unavailable")
    reference = refs[0]
    run = store.get_run(run_id)
    if not run or reference.get("mode") != run["mode"]:
        raise RecordingUnavailable("Saved checkout unavailable")
    recorded = [
        e["payload"]["recording"]
        for e in store.get_events(run_id)
        if e["event_type"] == "kernel_recorded_observation"
        and e["source"] == "browser"
        and e["payload"].get("browser_kind") == "KERNEL"
        and e["payload"].get("source_mode") == run["mode"]
        and e["payload"].get("recording", {}).get("sha256") == reference["sha256"]
    ]
    if not recorded:
        raise RecordingUnavailable("Saved checkout unavailable")
    root = Path(private_root).absolute()
    raw_path = reference.get("path")
    try:
        path = Path(raw_path)
        if root != root.resolve() or not path.is_absolute() or any(part in {".", ".."} for part in path.parts):
            raise ValueError()
        parts = path.relative_to(root).parts
        if not parts or len(parts) > 32:
            raise ValueError()
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts[:-1]:
                next_directory = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = next_directory
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        finally:
            os.close(directory)
        with os.fdopen(fd, "rb") as file:
            before = os.fstat(file.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 12 <= before.st_size <= MAX_VIDEO_BYTES:
                raise ValueError()
            body = file.read(MAX_VIDEO_BYTES + 1)
            after = os.fstat(file.fileno())
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise ValueError()
        if (
            len(body) != before.st_size
            or body[4:8] != b"ftyp"
            or hashlib.sha256(body).hexdigest() != reference["sha256"]
            or not all(r.get("bytes") == len(body) and r.get("access") == "PRIVATE_OPERATOR_ARTIFACT" for r in recorded)
        ):
            raise ValueError()
        return Recording(body, reference["sha256"])
    except (OSError, ValueError, TypeError):
        raise RecordingUnavailable("Saved checkout unavailable") from None


def availability(store, run_id, private_root, *, allow):
    """Path-free metadata. A media URL never doubles as a public capability."""
    if not allow:
        return {"availability": "disabled", "access": "operator_only", "fresh_verification": False}
    try:
        recording = load_recording(store, run_id, private_root)
    except RecordingUnavailable:
        return {"availability": "unavailable", "access": "operator_only", "fresh_verification": False}
    return {
        "availability": "available",
        "url": f"/api/runs/{run_id}/recording",
        "access": "operator_only",
        "bytes": recording.size,
        "sha256": recording.sha256,
        "fresh_verification": False,
    }


def byte_range(value, size):
    if value is None:
        return 0, size - 1, False
    if not isinstance(value, str) or len(value) > 100:
        raise InvalidRange()
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value.strip())
    if not match or not any(match.groups()):
        raise InvalidRange()
    first, last = match.groups()
    if not first:
        suffix = int(last)
        if suffix <= 0:
            raise InvalidRange()
        return max(0, size - suffix), size - 1, True
    start = int(first)
    end = min(int(last), size - 1) if last else size - 1
    if start >= size or start > end:
        raise InvalidRange()
    return start, end, True
