"""No providers: durable public Sandbox abuse/spend reservations and races."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from crashcart.public_live_limits import Limits, PublicLiveLimitError, PREFIX
from crashcart.store import Store


class PublicLiveLimitsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name) / "limits.sqlite")
        self.now = datetime(2026, 11, 11, 10, tzinfo=timezone.utc).timestamp()
        self.env = {
            PREFIX + "ENABLED": "1", PREFIX + "AUTHORIZED_RUNS": "8",
            PREFIX + "AUTHORIZED_UNTIL": "2026-11-12T21:00:00Z",
        }
        self.limits = Limits(self.store, self.env, lambda: self.now)

    def admit(self, index=0, *, ip="203.0.113.1", session=None, key=None, limits=None):
        return (limits or self.limits).admit(
            ip, session or hashlib.sha256(f"session{index}".encode()).hexdigest(),
            key or f"request_{index:016d}")

    def bound(self, index=0, **kwargs):
        reservation = self.admit(index, **kwargs)
        run = self.store.create_run("One ticket within sixty seconds", mode="LIVE_SANDBOX")
        self.limits.bind(reservation["id"], run["id"])
        return reservation, run["id"]

    def code(self, expected, action):
        with self.assertRaises(PublicLiveLimitError) as caught:
            action()
        self.assertEqual(expected, caught.exception.code)
        self.assertNotIn("203.0.113", str(caught.exception))

    def test_default_off_and_finite_owner_grant_required(self):
        for env in ({}, {PREFIX + "ENABLED": "1"},
                    {PREFIX + "ENABLED": "1", PREFIX + "AUTHORIZED_RUNS": "8"}):
            with self.subTest(env=env):
                limits = Limits(self.store, env, lambda: self.now)
                self.assertFalse(limits.snapshot()["enabled"])
                self.code("PUBLIC_LIVE_PAUSED", lambda: self.admit(limits=limits))
        self.assertEqual(0, self.limits.snapshot()["reserved_runs"])

    def test_whole_run_budget_reserved_before_run_exists_and_not_refunded(self):
        reservation = self.admit()
        self.assertTrue(reservation["created"])
        self.assertIsNone(reservation["run_id"])
        self.assertEqual(120_000, reservation["reserved_micro_usd"])
        self.assertEqual(120_000, self.limits.snapshot()["daily_reserved_micro_usd"])
        fresh = Limits(Store(self.store.path), self.env, lambda: self.now)
        retry = self.admit(limits=fresh)
        self.assertFalse(retry["created"])
        self.assertEqual(reservation["id"], retry["id"])
        self.assertIsNone(retry["run_id"])
        self.assertEqual(1, fresh.snapshot()["reserved_runs"])
        # No success/failure/refund hook exists: unknown dispatch stays charged.
        self.now += 3601
        self.assertEqual(120_000, fresh.snapshot()["daily_reserved_micro_usd"])

    def test_idempotency_binding_and_same_key_different_sessions(self):
        reservation, run_id = self.bound()
        self.assertEqual(run_id, self.admit()["run_id"])
        self.assertFalse(self.admit()["created"])
        self.assertEqual(run_id, self.limits.bind(reservation["id"], run_id)["run_id"])
        second = self.admit(1, key="request_0000000000000000")
        self.assertNotEqual(reservation["id"], second["id"])
        another_run = self.store.create_run("Deliver once", mode="LIVE_SANDBOX")["id"]
        self.code("PUBLIC_LIVE_BINDING_CONFLICT", lambda: self.limits.bind(reservation["id"], another_run))
        self.code("PUBLIC_LIVE_BINDING_CONFLICT", lambda: self.limits.bind(second["id"], run_id))
        self.code("PUBLIC_LIVE_UNKNOWN_RESERVATION", lambda: self.limits.bind("unknown", run_id))
        self.code("PUBLIC_LIVE_UNKNOWN_RESERVATION", lambda: self.limits.bind(second["id"], "missing"))

    def test_sliding_hour_is_not_a_clock_hour_bucket(self):
        self.admit(0)
        self.now += 3590
        self.admit(1)
        self.admit(2)
        self.code("PUBLIC_LIVE_IP_LIMIT", lambda: self.admit(3))
        self.now += 10
        self.assertTrue(self.admit(3)["created"])
        self.code("PUBLIC_LIVE_IP_LIMIT", lambda: self.admit(4))

    def test_ipv4_mapped_and_equivalent_ipv6_do_not_bypass_ip_limit(self):
        for i in range(3):
            self.admit(i, ip="203.0.113.1" if i % 2 else "::ffff:203.0.113.1")
        self.code("PUBLIC_LIVE_IP_LIMIT", lambda: self.admit(3, ip="::ffff:cb00:7101"))
        self.admit(4, ip="2001:db8::1")
        self.admit(5, ip="2001:0db8:0000:0000:0000:0000:0000:0001")
        self.admit(6, ip="2001:db8::1")
        self.code("PUBLIC_LIVE_IP_LIMIT", lambda: self.admit(7, ip="2001:db8::1"))

    def test_proxy_header_values_are_not_accepted_as_peer_addresses(self):
        for ip in ("203.0.113.1, 198.51.100.1", "for=203.0.113.1", " 203.0.113.1", "127.0.0.1:80",
                   "[::1]", "fe80::1%en0", "unknown", "", None, {"X-Forwarded-For": "203.0.113.1"}):
            with self.subTest(ip=ip):
                self.code("PUBLIC_LIVE_IP_INVALID", lambda: self.admit(ip=ip))
        self.assertEqual(0, self.limits.snapshot()["reserved_runs"])

    def test_utc_daily_budget_uses_full_reservation_and_never_exceeds_one_dollar(self):
        self.env[PREFIX + "DAILY_MICRO_USD"] = "250000"
        self.admit(0)
        self.admit(1)
        self.code("PUBLIC_LIVE_DAILY_BUDGET", lambda: self.admit(2))
        self.assertEqual(240_000, self.limits.snapshot()["daily_reserved_micro_usd"])
        self.now = datetime(2026, 11, 12, 0, tzinfo=timezone.utc).timestamp()
        self.assertEqual(0, self.limits.snapshot()["daily_reserved_micro_usd"])
        self.assertTrue(self.admit(2)["created"])
        self.assertEqual(3, self.limits.snapshot()["reserved_runs"])

    def test_daily_run_cap_and_lifetime_owner_cap_are_independent(self):
        self.env[PREFIX + "DAILY_RUNS"] = "2"
        self.admit(0)
        self.admit(1)
        self.code("PUBLIC_LIVE_DAILY_RUN_LIMIT", lambda: self.admit(2))
        self.now = datetime(2026, 11, 12, 0, tzinfo=timezone.utc).timestamp()
        self.env[PREFIX + "AUTHORIZED_RUNS"] = "2"
        self.code("PUBLIC_LIVE_OWNER_LIMIT", lambda: self.admit(2))
        self.assertEqual(0, self.limits.snapshot()["remaining_authorized_runs"])

    def test_eight_runs_reserve_ninety_six_cents_not_one_hundred_runs(self):
        for i in range(8):
            self.admit(i, ip=f"203.0.113.{i + 1}")
        self.code("PUBLIC_LIVE_OWNER_LIMIT", lambda: self.admit(8, ip="203.0.113.99"))
        status = self.limits.snapshot()
        self.assertEqual(8, status["daily_reserved_runs"])
        self.assertEqual(960_000, status["daily_reserved_micro_usd"])

    def test_config_cannot_expand_authorization_caps_or_use_unsafe_values(self):
        for name, value in (("AUTHORIZED_RUNS", "100"), ("IP_HOURLY_RUNS", "4"), ("DAILY_RUNS", "9"),
                            ("DAILY_MICRO_USD", "1000001"), ("DAILY_RUNS", "0"), ("ENABLED", "true"),
                            ("AUTHORIZED_RUNS", "1.0"), ("DAILY_MICRO_USD", "-1"), ("DAILY_RUNS", True),
                            ("AUTHORIZED_UNTIL", "2099-01-01T00:00:00Z"),
                            ("AUTHORIZED_UNTIL", "2026-11-12T21:00:00"), ("AUTHORIZED_UNTIL", "invalid")):
            env = {**self.env, PREFIX + name: value}
            with self.subTest(name=name, value=value):
                self.code("PUBLIC_LIVE_CONFIG_INVALID", lambda: self.admit(limits=Limits(self.store, env, lambda: self.now)))
        self.assertEqual(0, self.limits.snapshot()["reserved_runs"])

    def test_kill_switch_and_window_checked_on_every_admission_binding_and_ai_phase(self):
        reservation, run_id = self.bound()
        self.limits.allow_ai(run_id, "model-1")
        self.env[PREFIX + "ENABLED"] = "0"
        for action in (lambda: self.admit(), lambda: self.admit(1),
                       lambda: self.limits.bind(reservation["id"], run_id),
                       lambda: self.limits.allow_ai(run_id, "model-2")):
            self.code("PUBLIC_LIVE_PAUSED", action)
        self.env[PREFIX + "ENABLED"] = "1"
        self.now = datetime(2026, 11, 12, 21, tzinfo=timezone.utc).timestamp()
        self.code("PUBLIC_LIVE_PAUSED", lambda: self.limits.allow_ai(run_id, "model-2"))
        with self.store.connect() as db:
            charged = db.execute("SELECT SUM(reserved_micro_usd) FROM public_live_reservations").fetchone()[0]
        self.assertEqual(120_000, charged)

    def test_model_phases_are_one_use_and_unknown_or_failed_calls_are_not_refunded(self):
        _, run_id = self.bound()
        first = self.limits.allow_ai(run_id, "model-1")
        self.assertEqual((1, 40_000), (first["call_index"], first["reserved_micro_usd"]))
        self.code("PUBLIC_LIVE_AI_PHASE_ALREADY_USED", lambda: self.limits.allow_ai(run_id, "model-1"))
        # Reopening after an unknown first dispatch does not release the phase.
        limits = Limits(Store(self.store.path), self.env, lambda: self.now)
        self.code("PUBLIC_LIVE_AI_PHASE_ALREADY_USED", lambda: limits.allow_ai(run_id, "model-1"))
        self.assertEqual(2, limits.allow_ai(run_id, "model-2")["call_index"])
        self.assertEqual(3, limits.allow_ai(run_id, "model-3")["call_index"])
        self.code("PUBLIC_LIVE_AI_CALL_LIMIT", lambda: limits.allow_ai(run_id, "model-4"))
        self.code("PUBLIC_LIVE_UNKNOWN_RESERVATION", lambda: limits.allow_ai("run_unknown", "model-1"))
        self.code("PUBLIC_LIVE_AI_PHASE_INVALID", lambda: limits.allow_ai(run_id, "model 4"))
        self.assertEqual(120_000, limits.snapshot()["daily_reserved_micro_usd"])

    def test_unused_model_budget_cannot_cross_midnight_and_exceed_next_day_budget(self):
        reservation, run_id = self.bound()
        self.now = datetime(2026, 11, 12, 0, tzinfo=timezone.utc).timestamp()
        self.code("PUBLIC_LIVE_RESERVATION_EXPIRED", lambda: self.limits.allow_ai(run_id, "model-1"))
        self.assertFalse(self.admit()["created"])
        self.assertEqual(reservation["id"], self.admit()["id"])
        self.code("PUBLIC_LIVE_RESERVATION_EXPIRED", lambda: self.limits.bind(reservation["id"], run_id))
        self.assertEqual(1, self.limits.snapshot()["reserved_runs"])

    def test_runtime_tightened_daily_budget_stops_ai_without_refunding_prior_reservations(self):
        _, run_id = self.bound()
        self.env[PREFIX + "DAILY_MICRO_USD"] = "100000"
        self.code("PUBLIC_LIVE_DAILY_BUDGET", lambda: self.limits.allow_ai(run_id, "model-1"))
        self.assertEqual(120_000, self.limits.snapshot()["daily_reserved_micro_usd"])

    def test_runtime_tightened_owner_and_daily_run_caps_stop_new_model_phases(self):
        _, run_id = self.bound()
        self.admit(1)
        self.env[PREFIX + "AUTHORIZED_RUNS"] = "1"
        self.code("PUBLIC_LIVE_OWNER_LIMIT", lambda: self.limits.allow_ai(run_id, "model-1"))
        self.env[PREFIX + "AUTHORIZED_RUNS"] = "8"
        self.env[PREFIX + "DAILY_RUNS"] = "1"
        self.code("PUBLIC_LIVE_DAILY_RUN_LIMIT", lambda: self.limits.allow_ai(run_id, "model-1"))
        self.assertEqual(240_000, self.limits.snapshot()["daily_reserved_micro_usd"])

    def test_bad_identity_and_clock_values_fail_closed(self):
        for session, key in (("short", "request_0000000000000000"), ("a" * 64, "too-short"),
                             ("A" * 64, "request_0000000000000000")):
            self.code("PUBLIC_LIVE_IDENTITY_INVALID", lambda: self.limits.admit("203.0.113.1", session, key))
        self.admit()
        self.now -= 1
        self.code("PUBLIC_LIVE_CLOCK_REVERSED", lambda: self.admit(1))
        for value in (float("nan"), float("inf"), -1, True):
            with self.subTest(value=value):
                self.code("PUBLIC_LIVE_CLOCK_INVALID", lambda: self.admit(limits=Limits(self.store, self.env, lambda: value)))

    def test_snapshot_never_exposes_admission_identity_or_creates_legacy_ledger(self):
        self.admit()
        status = self.limits.snapshot()
        raw = json.dumps(status)
        self.assertNotIn("203.0.113.1", raw)
        self.assertNotIn("session", raw)
        self.assertNotIn("request_", raw)
        self.assertEqual("required_separately_unchanged", status["legacy_model_allowance"])
        self.assertFalse(list(Path(self.directory.name).glob("*.json")))

    def test_concurrent_repeated_posts_charge_exactly_one_and_unbound_retry_never_dispatches(self):
        def request(_):
            return self.admit(limits=Limits(Store(self.store.path), self.env, lambda: self.now))
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(request, range(24)))
        self.assertEqual(1, sum(result["created"] for result in results))
        self.assertEqual(1, len({result["id"] for result in results}))
        self.assertTrue(all(result["run_id"] is None for result in results))
        self.assertEqual(120_000, self.limits.snapshot()["daily_reserved_micro_usd"])

    def test_concurrent_different_posts_cannot_overrun_full_reservation_budget(self):
        self.env[PREFIX + "DAILY_MICRO_USD"] = "250000"
        def request(index):
            try:
                return self.admit(index, ip=f"203.0.113.{index + 1}",
                                  limits=Limits(Store(self.store.path), self.env, lambda: self.now))["created"]
            except PublicLiveLimitError as error:
                self.assertEqual("PUBLIC_LIVE_DAILY_BUDGET", error.code)
                return False
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(request, range(20)))
        self.assertEqual(2, sum(results))
        self.assertEqual(240_000, self.limits.snapshot()["daily_reserved_micro_usd"])

    def test_concurrent_model_phase_retries_dispatch_once_and_total_calls_never_exceed_three(self):
        _, run_id = self.bound()
        def phase(key):
            limits = Limits(Store(self.store.path), self.env, lambda: self.now)
            try:
                return limits.allow_ai(run_id, key)
            except PublicLiveLimitError as error:
                self.assertIn(error.code, {"PUBLIC_LIVE_AI_PHASE_ALREADY_USED", "PUBLIC_LIVE_AI_CALL_LIMIT"})
                return None
        with ThreadPoolExecutor(max_workers=12) as pool:
            first = list(pool.map(phase, ["model-1"] * 12))
            following = list(pool.map(phase, [f"model-{i}" for i in range(2, 14)]))
        self.assertEqual(1, sum(result is not None for result in first))
        self.assertEqual(2, sum(result is not None for result in following))
        self.assertEqual(120_000, self.limits.snapshot()["daily_reserved_micro_usd"])


if __name__ == "__main__":
    unittest.main()
