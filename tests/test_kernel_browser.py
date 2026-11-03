"""LOCAL_TEST only: injected KERNEL HTTP responses are not cloud-browser proof."""
import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import socket
import tempfile
import time
import unittest
from unittest.mock import patch
from urllib.error import URLError

from crashcart.kernel_browser import KernelBrowser, KernelError, owned_origin, _NoRedirect


IDENTITY = {"run_id": "run_" + "a" * 32, "purchase_id": "purchase_" + "b" * 32, "mode": "LIVE_SANDBOX"}
ORDER = "96L27649A64155625"
ORIGIN = "https://merchant.example.com"
MP4 = b"\x00\x00\x00\x18ftypisom" + b"synthetic-local-test-video"


def public_dns(*args, **kwargs):
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]


def observation(**changes):
    result = {**IDENTITY, "order_id": ORDER, "ticket_id": None, "observed_at": "2026-10-22T10:00:00Z",
              "path": "/shop", "run_state": "AWAITING_APPROVAL", "merchant_title": "0 tickets"}
    result.update(changes)
    return {"success": True, "result": result}


class Transport:
    def __init__(self, *actions, failures=None):
        self.actions = list(actions)
        self.failures = failures or {}
        self.calls = []

    def __call__(self, request, timeout, limit):
        self.calls.append((request, timeout, limit))
        path = request.full_url.removeprefix("https://api.onkernel.com")
        fail = self.failures.get((request.method, path))
        if fail:
            if isinstance(fail, BaseException):
                raise fail
            return fail
        if path == "/browsers":
            value = {"session_id": "kernel-session-1", "browser_live_view_url": "https://view.onkernel.com/?jwt=private-view-token",
                     "cdp_ws_url": "wss://private.invalid/?jwt=secret"}
        elif path.endswith("/playwright/execute"):
            if "authenticated: true" in json.loads(request.data)["code"]:
                value = {"success": True, "result": {"authenticated": True}}
            else:
                value = self.actions.pop(0)
                if isinstance(value, BaseException):
                    raise value
        elif path.endswith("/replays"):
            return 201, json.dumps({"replay_id": "replay-1", "replay_view_url": "https://api.onkernel.com/?jwt=private-replay-token"}).encode(), {}
        elif path.endswith("/stop"):
            return 200, b"", {}
        elif request.method == "GET":
            return 200, MP4, {"Content-Type": "video/mp4"}
        elif request.method == "DELETE":
            return 204, b"", {}
        else:
            raise AssertionError("unexpected request")
        return 200, json.dumps(value).encode(), {}


class KernelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.allowance = self.root / "allowance.json"
        self.grant = {"approval_id": "approved-local-test-1", "owned_origin": ORIGIN,
                      "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                      "max_session_seconds": 60, "scenarios": ["observe", "checkout", "confirm_return", "cancel_return"]}
        self.allowance.write_text(json.dumps(self.grant))
        self.env = {"KERNEL_API_KEY": "private-api-key", "CRASHCART_OPERATOR_TOKEN": "private-operator-token",
                    "CRASHCART_ALLOW_KERNEL": "1", "CRASHCART_PUBLIC_URL": ORIGIN}

    def adapter(self, transport):
        return KernelBrowser(allowance_path=self.allowance, state_dir=self.root / "private", environ=self.env,
                             transport=transport, resolver=public_dns)

    def test_missing_gates_make_no_network_call_or_reservation(self):
        for key in ("KERNEL_API_KEY", "CRASHCART_OPERATOR_TOKEN", "CRASHCART_ALLOW_KERNEL", "CRASHCART_PUBLIC_URL"):
            with self.subTest(key=key):
                env = self.env.pop(key)
                transport = Transport()
                with self.assertRaises(KernelError):
                    with self.adapter(transport).session(**IDENTITY):
                        self.fail("must not start")
                self.assertEqual(transport.calls, [])
                self.assertFalse((self.root / "private").exists())
                self.env[key] = env

    def test_allowance_missing_expired_mismatched_or_unbounded_rejected(self):
        for changes in ({"expires_at": "2000-01-01T00:00:00Z"}, {"max_session_seconds": 301},
                        {"max_session_seconds": True}, {"owned_origin": "https://other.example.com"},
                        {"scenarios": ["arbitrary-code"]}, {"unexpected": "ignored?"}):
            with self.subTest(changes=changes):
                self.allowance.write_text(json.dumps({**self.grant, **changes}))
                transport = Transport()
                with self.assertRaisesRegex(KernelError, "EXPLICIT_ALLOWANCE_REQUIRED"):
                    with self.adapter(transport).session(**IDENTITY):
                        pass
                self.assertFalse(transport.calls)
        self.allowance.unlink()
        with self.assertRaisesRegex(KernelError, "EXPLICIT_ALLOWANCE_REQUIRED"):
            with self.adapter(Transport()).session(**IDENTITY):
                pass

    def test_localhost_credentials_paths_ip_and_private_dns_rejected(self):
        for url in ("http://merchant.example.com", "https://localhost", "https://127.0.0.1", "https://[::1]",
                    "https://2130706433", "https://a.localhost", "https://a.local", "https://a.internal",
                    "https://user:secret@merchant.example.com", ORIGIN + "/path", ORIGIN + "?token=secret",
                    ORIGIN + ":444", "https://a.example.com."):
            with self.subTest(url=url), self.assertRaises(KernelError):
                owned_origin(url, public_dns)
        for ip in ("10.0.0.1", "127.0.0.1", "::1", "169.254.169.254", "100.64.0.1"):
            with self.subTest(ip=ip), self.assertRaises(KernelError):
                owned_origin(ORIGIN, lambda *a, **k: [(2, 1, 6, "", (ip, 443))])

    def test_valid_lifecycle_records_real_shapes_private_video_and_no_secret_urls(self):
        transport = Transport(observation(message="private-api-key buyer@example.com https://view.onkernel.com/?jwt=abc eyJfakeJWT"))
        browser = self.adapter(transport).session(**IDENTITY)
        with browser:
            self.assertIn("jwt=", browser.private_live_view_url())
            observed = browser.perform("observe")
            self.assertEqual(observed["order_id"], ORDER)
        receipt = browser.receipt
        self.assertEqual(receipt["mode"], "LOCAL_TEST")
        self.assertEqual(receipt["status"], "OBSERVED")
        self.assertEqual(receipt["payment_verdict"], "NOT_EVALUATED")
        self.assertEqual(receipt["recording_state"], "SAVED")
        video = Path(receipt["recording"]["private_path"])
        self.assertEqual(video.read_bytes(), MP4)
        self.assertEqual(video.stat().st_mode & 0o777, 0o600)
        self.assertEqual(receipt["recording"]["public_review"], "NOT_REVIEWED")
        encoded = json.dumps(receipt)
        for secret in ("private-api-key", "private-operator-token", "jwt=", "buyer@example.com", "eyJfakeJWT"):
            self.assertNotIn(secret, encoded)
        requests = [r for r, _, _ in transport.calls]
        self.assertTrue(all(r.full_url.startswith("https://api.onkernel.com/") for r in requests))
        self.assertEqual([r.method for r in requests], ["POST", "POST", "POST", "POST", "POST", "GET", "DELETE"])
        create = json.loads(requests[0].data)
        self.assertEqual(create["tags"]["run_id"], IDENTITY["run_id"])
        self.assertEqual(create["network"]["allowed_hosts"][0], "merchant.example.com")
        self.assertNotIn("start_url", create)
        self.assertEqual(json.loads(requests[2].data), {"framerate": 10, "max_duration_in_seconds": 60, "record_audio": False})
        self.assertEqual(browser.receipt["cleanup"]["session_delete"], "SUCCEEDED")

    def test_one_use_allowance_survives_adapter_restart(self):
        with self.adapter(Transport()).session(**IDENTITY):
            pass
        transport = Transport()
        with self.assertRaisesRegex(KernelError, "ALLOWANCE_ALREADY_RESERVED"):
            with self.adapter(transport).session(**IDENTITY):
                pass
        self.assertFalse(transport.calls)

    def test_ambiguous_create_is_not_retried_and_cleanup_uses_reserved_name(self):
        transport = Transport(failures={("POST", "/browsers"): TimeoutError("private-api-key")})
        browser = self.adapter(transport).session(**IDENTITY)
        with self.assertRaisesRegex(KernelError, "KERNEL_TIMEOUT"):
            with browser:
                pass
        self.assertEqual(len(transport.calls), 2)
        self.assertTrue(transport.calls[1][0].full_url.endswith(browser.receipt["session_name"]))
        self.assertEqual(transport.calls[1][0].method, "DELETE")
        self.assertNotIn("session_id", browser.receipt)
        self.assertEqual(browser.receipt["recording_state"], "NOT_STARTED")
        self.assertNotIn("private-api-key", json.dumps(browser.receipt))

    def test_remote_failure_timeout_and_interrupt_save_partial_and_delete(self):
        for error in ({"success": False, "error": "private-api-key", "stderr": "secret"},
                      TimeoutError("private-api-key"), URLError("private-api-key"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                self.grant["approval_id"] = "grant-" + str(time.monotonic_ns())
                self.allowance.write_text(json.dumps(self.grant))
                transport = Transport(error)
                browser = self.adapter(transport).session(**IDENTITY)
                with self.assertRaises((KernelError, KeyboardInterrupt)):
                    with browser:
                        browser.perform("observe")
                self.assertEqual(browser.receipt["recording_state"], "SAVED_PARTIAL")
                self.assertEqual(browser.receipt["cleanup"]["session_delete"], "SUCCEEDED")
                self.assertNotIn("private-api-key", json.dumps(browser.receipt))

    def diagnostic(self, browser):
        return self.root / "private" / (browser.receipt["session_name"] + ".diagnostic.json")

    def test_typed_remote_timeout_is_private_diagnostic_not_observation(self):
        transport = Transport({"success": True, "result": {"crashcart_failure": {
            "stage": "CAPTURE_IDLE", "error": "TIMEOUT", "elapsed_ms": 8042}},
            "stderr": "private-api-key buyer@example.com https://secret.invalid/?jwt=abc"})
        browser = self.adapter(transport).session(**IDENTITY, order_id=ORDER)
        with self.assertRaisesRegex(KernelError, "REMOTE_SCENARIO_FAILED"):
            with browser:
                browser.perform("confirm_return")
        artifact = self.diagnostic(browser)
        diagnostic = json.loads(artifact.read_text())
        self.assertEqual(diagnostic, {"schema_version": 1, "kind": "UNTRUSTED_REMOTE_DIAGNOSTIC",
                         "session_id": "kernel-session-1", "scenario": "confirm_return",
                         "stage": "CAPTURE_IDLE", "error": "TIMEOUT", "elapsed_ms": 8042,
                         "clock": "REMOTE_ELAPSED_CAPPED_20000"})
        self.assertEqual(artifact.stat().st_mode & 0o777, 0o600)
        self.assertEqual(browser._diagnostic_state, "SAVED")
        self.assertEqual(browser.receipt["observations"], [])
        self.assertEqual(browser.receipt["error"], "REMOTE_SCENARIO_FAILED")
        self.assertEqual(browser.receipt["recording_state"], "SAVED_PARTIAL")
        self.assertEqual(browser.receipt["cleanup"]["session_delete"], "SUCCEEDED")
        self.assertNotIn("diagnostic", json.dumps(browser.receipt))
        for secret in ("private-api-key", "buyer@example.com", "https://", "jwt=", "stderr"):
            self.assertNotIn(secret, artifact.read_text())
        execute = [json.loads(r.data) for r, _, _ in transport.calls if r.full_url.endswith("/playwright/execute")][-1]
        self.assertEqual(execute["timeout_sec"], 20)

    def test_remote_error_strings_and_malformed_diagnostics_never_enter_sidecar(self):
        secret = "private-api-key https://secret.invalid/?jwt=abc buyer@example.com"
        good = {"stage": "CAPTURE_RESPONSE", "error": "TIMEOUT", "elapsed_ms": 8001}
        payloads = [{"success": False, "error": secret, "stderr": secret},
                    {"success": True, "result": []}]
        for changes in ({"stage": secret}, {"error": secret}, {"stage": []}, {"error": {}},
                        {"elapsed_ms": True}, {"elapsed_ms": -1}, {"elapsed_ms": 20001},
                        {"elapsed_ms": 8000.5}, {"stderr": secret}):
            payloads.append({"success": True, "result": {"crashcart_failure": {**good, **changes}}})
        payloads.append({"success": True, "result": {"crashcart_failure": good, **observation()["result"]}})
        for index, payload in enumerate(payloads):
            self.grant["approval_id"] = "malformed-diagnostic-" + str(index)
            self.allowance.write_text(json.dumps(self.grant))
            browser = self.adapter(Transport(payload)).session(**IDENTITY)
            with self.subTest(index=index), self.assertRaisesRegex(KernelError, "REMOTE_SCENARIO_FAILED"):
                with browser:
                    browser.perform("observe")
            diagnostic = json.loads(self.diagnostic(browser).read_text())
            self.assertEqual(diagnostic["stage"], "EXECUTE")
            self.assertEqual(diagnostic["error"], "REMOTE_EXECUTION_FAILED" if index < 2 else "MALFORMED_DIAGNOSTIC")
            self.assertIs(type(diagnostic["elapsed_ms"]), int)
            self.assertLessEqual(diagnostic["elapsed_ms"], 20000)
            self.assertEqual(browser.receipt["observations"], [])
            self.assertEqual(browser.receipt["cleanup"]["session_delete"], "SUCCEEDED")
            self.assertNotIn(secret, self.diagnostic(browser).read_text() + json.dumps(browser.receipt))

    def test_sidecar_write_failure_cannot_hide_original_failure_or_skip_cleanup(self):
        browser = self.adapter(Transport({"success": False, "error": "sensitive remote error"})).session(**IDENTITY)
        real_open = os.open

        def fail_diagnostic_only(path, *args):
            if str(path).endswith(".diagnostic.tmp"):
                raise PermissionError("sensitive filesystem error")
            return real_open(path, *args)

        with patch("crashcart.kernel_browser.os.open", side_effect=fail_diagnostic_only):
            with self.assertRaisesRegex(KernelError, "REMOTE_SCENARIO_FAILED"):
                with browser:
                    browser.perform("observe")
        self.assertFalse(self.diagnostic(browser).exists())
        self.assertEqual(browser._diagnostic_state, "UNAVAILABLE")
        self.assertEqual(browser.receipt["error"], "REMOTE_SCENARIO_FAILED")
        self.assertEqual(browser.receipt["cleanup"], {"recording_stop": "SUCCEEDED",
                         "recording_download": "SUCCEEDED", "session_delete": "SUCCEEDED"})
        self.assertNotIn("sensitive", json.dumps(browser.receipt))

    def test_success_has_no_failure_sidecar_and_preserves_receipt_shape(self):
        browser = self.adapter(Transport(observation())).session(**IDENTITY)
        with browser:
            browser.perform("observe")
        self.assertFalse(self.diagnostic(browser).exists())
        self.assertEqual(browser.receipt["status"], "OBSERVED")

    def test_cancel_and_deadline_close_then_refuse_actions_without_network(self):
        for reason in ("CANCELLED", "TIMED_OUT"):
            self.grant["approval_id"] = reason
            self.allowance.write_text(json.dumps(self.grant))
            transport = Transport()
            browser = self.adapter(transport).session(**IDENTITY)
            with browser:
                browser.cancel(reason)
                calls = len(transport.calls)
                with self.assertRaisesRegex(KernelError, "SESSION_CLOSED"):
                    browser.perform("observe")
            self.assertEqual(len(transport.calls), calls)
            self.assertEqual(browser.receipt["status"], reason)
            self.assertEqual(browser.receipt["recording_state"], "SAVED_PARTIAL")

    def test_actual_watchdog_invokes_cleanup_without_another_action(self):
        transport = Transport()
        browser = self.adapter(transport).session(**IDENTITY)
        # Speed only scheduling; the grant and request limits remain unchanged.
        import threading
        real_timer = threading.Timer
        with patch("crashcart.kernel_browser.threading.Timer", side_effect=lambda seconds, fn, args: real_timer(.05, fn, args)):
            with browser:
                deadline = time.monotonic() + 2
                while not browser._closed and time.monotonic() < deadline:
                    time.sleep(.01)
        self.assertEqual(browser.receipt["status"], "TIMED_OUT")
        self.assertEqual(browser.receipt["cleanup"]["session_delete"], "SUCCEEDED")

    def test_wrong_identity_order_path_and_naive_time_are_not_browser_proof(self):
        for changes in ({"run_id": "run_" + "c" * 32}, {"purchase_id": "purchase_" + "c" * 32},
                        {"order_id": "ANOTHERORDER"}, {"path": "https://evil.example/?jwt=x"},
                        {"ticket_id": "not-a-ticket"}, {"observed_at": "2026-10-22T10:00:00"}):
            self.grant["approval_id"] = "grant-" + str(time.monotonic_ns())
            self.allowance.write_text(json.dumps(self.grant))
            browser = self.adapter(Transport(observation(**changes))).session(**IDENTITY, order_id=ORDER)
            with self.subTest(changes=changes), self.assertRaises(KernelError):
                with browser:
                    browser.perform("observe")
            self.assertFalse(browser.receipt["observations"])
            self.assertEqual(browser.receipt["cleanup"]["session_delete"], "SUCCEEDED")

    def test_checkout_binds_new_order_then_capture_requires_exact_return(self):
        transport = Transport(observation(path="/checkoutnow"), observation(path="/return", ticket_id="ticket_" + "d" * 32))
        browser = self.adapter(transport).session(**IDENTITY)
        with browser:
            browser.perform("checkout")
            browser.perform("confirm_return")
        codes = [json.loads(r.data)["code"] for r, _, _ in transport.calls if r.full_url.endswith("/playwright/execute")]
        capture_code = codes[-1]
        self.assertIn('"order_id": "' + ORDER + '"', capture_code)
        self.assertIn("u.searchParams.get('token') !== cfg.order_id", capture_code)
        self.assertIn("data.purchase.amount !== 2900", capture_code)
        self.assertEqual(browser.receipt["observations"][-1]["ticket_id"], "ticket_" + "d" * 32)

    def test_unapproved_scenarios_and_arbitrary_code_rejected_before_execute(self):
        self.grant["scenarios"] = ["observe"]
        self.allowance.write_text(json.dumps(self.grant))
        transport = Transport()
        with self.adapter(transport).session(**IDENTITY) as browser:
            calls = len(transport.calls)
            for scenario in ("checkout", "confirm_return", "await page.goto('https://evil.example')"):
                with self.assertRaisesRegex(KernelError, "SCENARIO_NOT_ALLOWED"):
                    browser.perform(scenario)
            self.assertEqual(len(transport.calls), calls)

    def test_cleanup_failure_is_not_success_and_does_not_prevent_session_delete(self):
        failures = {("POST", "/browsers/kernel-session-1/replays/replay-1/stop"): (500, b'private-api-key', {}),
                    ("GET", "/browsers/kernel-session-1/replays/replay-1"): (202, b'processing', {})}
        browser = self.adapter(Transport(observation(), failures=failures)).session(**IDENTITY)
        with browser:
            browser.perform("observe")
        self.assertEqual(browser.receipt["status"], "INCOMPLETE")
        self.assertEqual(browser.receipt["cleanup"]["session_delete"], "SUCCEEDED")
        self.assertNotIn("recording", browser.receipt)

    def test_download_rejects_html_and_oversize_body(self):
        from crashcart.kernel_browser import MAX_VIDEO
        for body in (b"<html>private-api-key</html>", b"x" * (MAX_VIDEO + 1)):
            self.grant["approval_id"] = "grant-" + str(time.monotonic_ns())
            self.allowance.write_text(json.dumps(self.grant))
            failures = {("GET", "/browsers/kernel-session-1/replays/replay-1"): (200, body, {})}
            browser = self.adapter(Transport(observation(), failures=failures)).session(**IDENTITY)
            with browser:
                browser.perform("observe")
            self.assertEqual(browser.receipt["status"], "INCOMPLETE")
            self.assertNotIn("recording", browser.receipt)

    def test_redirect_handler_never_forwards_api_bearer(self):
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example"))


if __name__ == "__main__":
    unittest.main()
