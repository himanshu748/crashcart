"""Exercise readiness/reset handling using the real unchanged loopback receiver."""
import socket
import tempfile
from pathlib import Path
import unittest
from tests.overload_fixture import OverloadFixture


class OverloadFixtureTests(unittest.TestCase):
    def test_reset_recovery_real_saturation_and_clean_release(self):
        attempts = []
        def reset_then_connect(address, **kwargs):
            attempts.append(address)
            if len(attempts) <= 2:
                raise ConnectionResetError('Injected local fixture reset')
            return socket.create_connection(address, **kwargs)
        with tempfile.TemporaryDirectory() as temporary:
            fixture = OverloadFixture(Path(temporary) / 'run', max_pressure_seconds=8,
                                      connect=reset_then_connect)
            try:
                fixture.start()
                ready = fixture.begin()
                self.assertEqual(fixture.server.ingress_limits.max_handlers, 16)
                self.assertEqual(fixture.server.ingress_limits.request_timeout, 10)
                self.assertEqual(ready['before']['active'], 16)
                self.assertEqual(ready['probe']['status'], 503)
                self.assertEqual(fixture.connection_errors, 2)
                released = fixture.release()
                self.assertEqual(released['probe']['status'], 200)
                self.assertTrue(released['facts_unchanged'])
                self.assertEqual(fixture.provider_calls, 0)
            finally:
                fixture.close()
            self.assertEqual(fixture.stats()['active'], 0)
            self.assertFalse(fixture.clients)

    def test_failed_admission_cannot_declare_readiness(self):
        def reset(address, **kwargs):
            raise ConnectionResetError('Injected admission failure')
        with tempfile.TemporaryDirectory() as temporary:
            fixture = OverloadFixture(Path(temporary) / 'run', max_pressure_seconds=.3, connect=reset)
            try:
                fixture.start()
                fixture.worker = __import__('threading').Thread(target=fixture._maintain, daemon=True)
                fixture.worker.start()
                with self.assertRaisesRegex(RuntimeError, 'not confirmed'):
                    fixture.assert_saturated('must-not-exist', timeout=.5)
                self.assertFalse((fixture.output / 'must-not-exist.json').exists())
            finally:
                fixture.close()
            self.assertFalse(fixture.clients)

    def test_output_directory_cannot_overwrite_previous_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileExistsError):
                OverloadFixture(temporary)


if __name__ == '__main__':
    unittest.main()
