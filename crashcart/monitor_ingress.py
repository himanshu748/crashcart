"""Bounded ingress for the local monitor; no keys derived from client headers."""

from dataclasses import dataclass
from http.server import ThreadingHTTPServer
import math
import socket
import threading
import time


@dataclass(frozen=True)
class IngressLimits:
    max_handlers: int = 16
    global_burst: int = 60
    global_per_second: float = 10.0
    store_burst: int = 20
    store_per_second: float = 2.0
    max_store_buckets: int = 256
    idle_seconds: float = 600.0
    request_timeout: float = 10.0

    def __post_init__(self):
        for name, maximum in [
            ('max_handlers', 128),
            ('global_burst', 10000),
            ('store_burst', 10000),
            ('max_store_buckets', 4096),
        ]:
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError('Invalid ingress ' + name)
        for name, maximum in [
            ('global_per_second', 1000),
            ('store_per_second', 1000),
            ('idle_seconds', 86400),
            ('request_timeout', 10),
        ]:
            value = getattr(self, name)
            minimum = {'request_timeout': 0.05, 'idle_seconds': 1}.get(name, 0.001)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not minimum <= value <= maximum
            ):
                raise ValueError('Invalid ingress ' + name)


class WebhookLimiter:
    def __init__(self, limits=None, clock=time.monotonic):
        self.limits = limits or IngressLimits()
        if not isinstance(self.limits, IngressLimits):
            raise ValueError('Validated ingress limits required')
        self.clock = clock
        self.lock = threading.Lock()
        now = self._now()
        self.global_bucket = [float(self.limits.global_burst), now]
        self.stores = {}

    def _now(self):
        value = self.clock()
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('Invalid monotonic clock')
        return value

    @staticmethod
    def _take(bucket, capacity, rate, now):
        now = max(now, bucket[1])
        bucket[0] = min(capacity, bucket[0] + (now - bucket[1]) * rate)
        bucket[1] = now
        if bucket[0] >= 1:
            bucket[0] -= 1
            return 0
        return max(1, math.ceil((1 - bucket[0]) / rate))

    def global_admit(self):
        with self.lock:
            return self._take(self.global_bucket, self.limits.global_burst, self.limits.global_per_second, self._now())

    def store_admit(self, store_id):
        """Caller must resolve the registered store before supplying its ID."""
        with self.lock:
            now = self._now()
            if store_id not in self.stores:
                # Only idle, fully recovered buckets may be forgotten. Refusing
                # new keys at capacity prevents eviction from resetting limits.
                for key, bucket in list(self.stores.items()):
                    if (
                        now - bucket[1] >= self.limits.idle_seconds
                        and bucket[0] + (now - bucket[1]) * self.limits.store_per_second >= self.limits.store_burst
                    ):
                        del self.stores[key]
                if len(self.stores) >= self.limits.max_store_buckets:
                    return 1
                self.stores[store_id] = [float(self.limits.store_burst), now]
            return self._take(self.stores[store_id], self.limits.store_burst, self.limits.store_per_second, now)


class BoundedHTTPServer(ThreadingHTTPServer):
    """Refuse excess connections before creating a handler thread or reading HTTP."""

    daemon_threads = True

    def __init__(self, address, handler, *, limits=None):
        self.ingress_limits = limits or IngressLimits()
        if not isinstance(self.ingress_limits, IngressLimits):
            raise ValueError('Validated ingress limits required')
        self._permits = threading.BoundedSemaphore(self.ingress_limits.max_handlers)
        self._admission_lock = threading.Lock()
        self.active_handlers = 0
        self.peak_handlers = 0
        self._requests = {}
        self._closing = False
        self._deadline_stop = threading.Event()
        super().__init__(address, handler)
        self._deadline_thread = threading.Thread(target=self._deadlines, daemon=True)
        self._deadline_thread.start()

    def _deadlines(self):
        while not self._deadline_stop.wait(min(0.05, self.ingress_limits.request_timeout / 4)):
            now = time.monotonic()
            with self._admission_lock:
                expired = [
                    request
                    for request, started in self._requests.values()
                    if now - started >= self.ingress_limits.request_timeout
                ]
            for request in expired:
                try:
                    request.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def server_close(self):
        with self._admission_lock:
            self._closing = True
            sockets = [request for request, _ in self._requests.values()]
        for request in sockets:
            try:
                request.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self._deadline_stop.set()
        if hasattr(self, '_deadline_thread'):
            self._deadline_thread.join(timeout=1)
        super().server_close()

    def _release(self, request):
        with self._admission_lock:
            self._requests.pop(id(request), None)
            self.active_handlers -= 1
        self._permits.release()

    def process_request(self, request, client_address):
        with self._admission_lock:
            admitted = not self._closing and self._permits.acquire(blocking=False)
            if admitted:
                self.active_handlers += 1
                self.peak_handlers = max(self.peak_handlers, self.active_handlers)
                self._requests[id(request)] = (request, time.monotonic())
        if not admitted:
            raw = b'{"error":"The workspace is busy. Try again shortly."}'
            response = (
                b'HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\nRetry-After: 1\r\nContent-Type: application/json\r\nContent-Length: '
                + str(len(raw)).encode()
                + b'\r\nCache-Control: no-store\r\n\r\n'
                + raw
            )
            try:
                request.settimeout(min(0.2, self.ingress_limits.request_timeout))
                request.sendall(response)
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._release(request)
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._release(request)
