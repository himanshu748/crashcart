"""Synthetic replay probes: no provider traffic; real sockets target owned loopback only."""
from concurrent.futures import ThreadPoolExecutor
import socket
import sys
import threading
import unittest
from unittest.mock import patch

from crashcart import replay as module
from tests.test_replay import synthetic_package


class ReplayNetworkGuardTests(unittest.TestCase):
    def test_measures_and_blocks_connect_and_connect_ex_without_replacing_socket(self):
        original_store = module._clocked_store
        original_connect = socket.socket.connect
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            listener.settimeout(0.02)
            target = listener.getsockname()

            def probe(path, clock):
                for method in ('connect', 'connect_ex'):
                    with socket.socket() as client:
                        with self.assertRaisesRegex(module.ReplayError, 'blocked a socket connection'):
                            getattr(client, method)(target)
                return original_store(path, clock)

            with patch.object(module, '_clocked_store', side_effect=probe):
                result = module.replay(synthetic_package(), merchant='healthy')
            self.assertEqual(2, result['network_calls'])
            self.assertEqual('PASS', result['verdict'])
            self.assertIs(original_connect, socket.socket.connect)
            with self.assertRaises(TimeoutError):
                listener.accept()
            # After replay, the same real socket API may connect to our listener.
            with socket.socket() as client:
                client.connect(target)
                accepted, _ = listener.accept()
                accepted.close()

    def test_uncaught_attempt_fails_and_the_scope_is_restored_on_exception(self):
        def probe(*_):
            sys.audit('socket.connect', None, ('127.0.0.1', 1))
        with patch.object(module, '_clocked_store', side_effect=probe):
            with self.assertRaisesRegex(module.ReplayError, 'blocked a socket connection'):
                module.replay(synthetic_package())
        # An audit event outside the replay scope is not rejected by this guard.
        sys.audit('socket.connect', None, ('127.0.0.1', 1))
        self.assertEqual(0, module.replay(synthetic_package())['network_calls'])

    def test_concurrent_replays_measure_only_their_own_attempts(self):
        original_store = module._clocked_store
        barrier = threading.Barrier(2)
        attempts = threading.local()

        def probe(path, clock):
            barrier.wait(timeout=5)
            for _ in range(attempts.count):
                try:
                    sys.audit('socket.connect', None, ('127.0.0.1', 1))
                except module.ReplayError:
                    pass
            return original_store(path, clock)

        def execute(count):
            attempts.count = count
            return module.replay(synthetic_package())['network_calls']

        with patch.object(module, '_clocked_store', side_effect=probe), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(execute, (1, 3)))
        self.assertEqual([1, 3], results)

    def test_other_thread_is_not_guarded_while_replay_is_active(self):
        original_store = module._clocked_store
        arrived, release = threading.Event(), threading.Event()

        def probe(path, clock):
            arrived.set()
            if not release.wait(timeout=5):
                raise AssertionError('test did not release replay')
            return original_store(path, clock)

        with patch.object(module, '_clocked_store', side_effect=probe), ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(module.replay, synthetic_package())
            try:
                self.assertTrue(arrived.wait(timeout=5))
                sys.audit('socket.connect', None, ('127.0.0.1', 1))
            finally:
                release.set()
            self.assertEqual(0, pending.result(timeout=5)['network_calls'])

    def test_outer_scope_measures_nested_attempt_and_both_scopes_restore(self):
        original_store = module._clocked_store
        nested = []
        depth = 0

        def probe(path, clock):
            nonlocal depth
            if depth == 0:
                depth += 1
                try:
                    nested.append(module.replay(synthetic_package()))
                finally:
                    depth -= 1
            try:
                sys.audit('socket.connect', None, ('127.0.0.1', 1))
            except module.ReplayError:
                pass
            return original_store(path, clock)

        with patch.object(module, '_clocked_store', side_effect=probe):
            result = module.replay(synthetic_package())
        self.assertEqual(1, nested[0]['network_calls'])
        self.assertEqual(2, result['network_calls'])
        self.assertEqual(0, module.replay(synthetic_package())['network_calls'])


if __name__ == '__main__':
    unittest.main()
