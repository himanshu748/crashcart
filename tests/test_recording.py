"""LOCAL_TEST private media bytes and real loopback HTTP; no service calls."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from crashcart import recording, server
from crashcart.store import Store


class RecordingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="crashcart-recording-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "var/recordings").mkdir(parents=True)
        self.file = self.root / "var/recordings/local-test.mp4"
        self.body = b"\x00\x00\x00\x18ftypLOCAL_TEST_MEDIA_NOT_PROVIDER_PROOF"
        self.file.write_bytes(self.body)
        self.store = Store(self.root / "copy.sqlite3")
        self.run = self.store.create_run("Local media route fixture", mode="LOCAL_TEST")
        self.sha = hashlib.sha256(self.body).hexdigest()
        self.ref = self.store.add_evidence(self.run["id"], "kernel-video-v1", self.file, self.sha)
        self.store.record_event(self.run["id"], "browser", "kernel_recorded_observation", {
            "browser_kind": "KERNEL", "source_mode": "LOCAL_TEST", "recording": {
                "sha256": self.sha, "bytes": len(self.body), "access": "PRIVATE_OPERATOR_ARTIFACT"}})
        self.token = "LOCAL_TEST_PRIVATE_RECORDING"
        self.env = patch.dict(os.environ, {"CRASHCART_OPERATOR_TOKEN": self.token, "CRASHCART_PUBLIC_URL": "",
            "CRASHCART_ALLOW_PRIVATE_RECORDINGS": "1", "CRASHCART_ALLOW_SANDBOX": "0", "CRASHCART_ALLOW_MODEL": "0", "CRASHCART_ALLOW_KERNEL": "0"})
        self.env.start(); self.addCleanup(self.env.stop)
        self.web_root = patch.object(server, "ROOT", self.root)
        self.web_root.start(); self.addCleanup(self.web_root.stop)
        connect = socket.socket.connect
        def loopback_only(sock, address):
            if not isinstance(address, tuple) or address[0] != "127.0.0.1":
                raise AssertionError("External network forbidden")
            return connect(sock, address)
        guard = patch.object(socket.socket, "connect", loopback_only)
        guard.start(); self.addCleanup(guard.stop)
        no_payment = patch("crashcart.service.MerchantService", side_effect=AssertionError("Payment service forbidden"))
        self.payment = no_payment.start(); self.addCleanup(no_payment.stop)
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.httpd.store = self.store
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.close)
        self.url = f"/api/runs/{self.run['id']}/recording"

    def close(self):
        self.httpd.shutdown(); self.httpd.server_close(); self.thread.join(timeout=2)
        self.payment.assert_not_called()

    def request(self, path=None, *, auth=True, headers=None, method="GET", body=None):
        headers = dict(headers or {})
        if auth: headers.setdefault("Authorization", "Bearer " + self.token)
        if body is not None:
            body = json.dumps(body); headers["Content-Type"] = "application/json"
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=3)
        try:
            connection.request(method, path or self.url, body, headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def update_ref(self, **values):
        with self.store.connect(write=True) as db:
            for key, value in values.items():
                db.execute("UPDATE evidence_refs SET " + key + "=? WHERE id=?", (value, self.ref["id"]))

    def test_recording_requires_operator_auth_even_for_byte_ranges(self):
        for headers in ({}, {"Authorization": "Bearer wrong"}, {"Cookie": "crashcart_session=wrong", "Range": "bytes=0-4"}):
            self.assertEqual(self.request(auth=False, headers=headers)[0], 401)

    def test_login_cookie_plays_exact_bound_private_bytes_and_security_headers(self):
        status, headers, _ = self.request("/api/login", method="POST", auth=False, body={"token": self.token})
        self.assertEqual(status, 200)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        status, headers, data = self.request(auth=False, headers={"Cookie": cookie})
        self.assertEqual(status, 200); self.assertEqual(data, self.body)
        for key, expected in {"Content-Type": "video/mp4", "Accept-Ranges": "bytes", "Cache-Control": "no-store", "Cross-Origin-Resource-Policy": "same-origin", "X-Content-Type-Options": "nosniff"}.items():
            self.assertEqual(headers[key], expected)
        self.assertNotIn(str(self.file), json.dumps(headers))

    def test_single_ranges_cover_seek_suffix_open_end_and_invalid_requests(self):
        for value, expected in (("bytes=0-7", self.body[:8]), ("bytes=8-", self.body[8:]), ("bytes=-5", self.body[-5:]), ("bytes=0-999", self.body)):
            with self.subTest(value=value):
                status, headers, body = self.request(headers={"Range": value})
                self.assertEqual(status, 206); self.assertEqual(body, expected)
                self.assertEqual(int(headers["Content-Length"]), len(expected))
                self.assertTrue(headers["Content-Range"].endswith("/" + str(len(self.body))))
        for value in ("bytes=999-", "bytes=9-2", "bytes=-0", "bytes=", "items=0-1", "bytes=0-1,4-5", "bytes=" + "1" * 101 + "-"):
            self.assertEqual(self.request(headers={"Range": value})[0], 416)

    def test_private_recordings_are_explicitly_opted_in_on_loopback_only(self):
        os.environ["CRASHCART_ALLOW_PRIVATE_RECORDINGS"] = "0"
        self.assertEqual(self.request()[0], 404)
        _, _, body = self.request(f"/api/runs/{self.run['id']}")
        self.assertEqual(json.loads(body)["recording"]["availability"], "disabled")
        self.assertFalse(recording.enabled(SimpleNamespace(server_address=("0.0.0.0", 80)), {"CRASHCART_ALLOW_PRIVATE_RECORDINGS": "1"}))

    def test_metadata_is_path_free_and_cannot_make_a_public_video_capability(self):
        status, _, body = self.request(f"/api/runs/{self.run['id']}")
        self.assertEqual(status, 200)
        info = json.loads(body)["recording"]
        self.assertEqual(info["availability"], "available"); self.assertEqual(info["url"], self.url)
        self.assertEqual(info["access"], "operator_only"); self.assertFalse(info["fresh_verification"])
        self.assertNotIn(str(self.root), body.decode())
        self.assertEqual(self.request(info["url"], auth=False)[0], 401)

    def test_recording_must_have_exact_imported_evidence_kind_and_observation(self):
        self.update_ref(kind="other-recording")
        self.assertEqual(self.request()[0], 404)
        self.update_ref(kind="kernel-video-v1")
        with self.store.connect(write=True) as db: db.execute("DELETE FROM events")
        self.assertEqual(self.request()[0], 404)

    def test_outside_var_dotdot_and_missing_files_are_rejected_without_path_leak(self):
        outside = self.root / "outside.mp4"; outside.write_bytes(self.body)
        for path in (outside, self.root / "var/../outside.mp4", self.root / "var/missing.mp4"):
            self.update_ref(path=str(path))
            status, _, body = self.request()
            self.assertEqual(status, 404); self.assertNotIn(str(self.root), body.decode())

    def test_final_ancestor_symlinks_and_hardlinks_are_rejected(self):
        final = self.root / "var/final.mp4"; final.symlink_to(self.file)
        ancestor = self.root / "var/alias"; ancestor.symlink_to(self.file.parent, target_is_directory=True)
        hard = self.root / "var/hard.mp4"; hard.hardlink_to(self.file)
        for path in (final, ancestor / self.file.name, hard):
            self.update_ref(path=str(path)); self.assertEqual(self.request()[0], 404)
        hard.unlink()

    def test_hash_corruption_non_mp4_and_size_limits_fail_closed(self):
        self.file.write_bytes(self.body + b"changed")
        self.assertEqual(self.request()[0], 404)
        self.file.write_bytes(self.body)
        with patch.object(recording, "MAX_VIDEO_BYTES", 12):
            self.assertEqual(self.request()[0], 404)
        fake = b"not an mp4 file but a matching hash"
        self.file.write_bytes(fake); self.update_ref(sha256=hashlib.sha256(fake).hexdigest())
        self.assertEqual(self.request()[0], 404)

    def test_replaced_fifo_is_rejected_without_waiting_for_a_writer(self):
        self.file.unlink(); os.mkfifo(self.file)
        self.assertEqual(self.request()[0], 404)

    def test_unknown_or_cross_run_and_extra_path_cannot_select_a_file(self):
        other = self.store.create_run("Another local run", mode="LOCAL_TEST")
        for path in (f"/api/runs/{other['id']}/recording", "/api/runs/run_" + "0" * 32 + "/recording", self.url + "/extra/recording"):
            self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.request(self.url + "?path=/outside.mp4")[2], self.body)

    def test_ambiguous_references_are_rejected_and_verified_bytes_cannot_be_swapped(self):
        held = recording.load_recording(self.store, self.run["id"], self.root / "var")
        self.file.write_bytes(b"changed after verification")
        self.assertEqual(held.body, self.body)
        self.file.write_bytes(self.body)
        other = self.root / "var/another.mp4"; other.write_bytes(self.body)
        self.store.add_evidence(self.run["id"], "kernel-video-v1", other, self.sha)
        self.assertEqual(self.request()[0], 404)


if __name__ == "__main__": unittest.main(verbosity=2)
