"""Local monitoring console. Authenticating webhooks never creates a payment."""
from __future__ import annotations
import argparse
import base64
import binascii
from dataclasses import asdict
from datetime import datetime, timezone
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlsplit
from .monitor_connectors import parse_shopify, parse_woocommerce
from .monitor_store import MonitorStore, ReceiptCapacityError, SHOPIFY_ADDRESS_HINT
from .monitor_ingress import BoundedHTTPServer, IngressLimits, WebhookLimiter
from .paypal import PaymentValidationError, PayPalError, PayPalSandbox, _observed_money, parse_webhook_event

MAX_BODY = 131072
WEB = Path(__file__).resolve().parents[1] / 'web' / 'monitor'
ID = re.compile(r'^[A-Za-z0-9_-]{1,100}$')
COOKIE = 'crashcart_monitor_session'


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field')
            result[key] = value
        return result
    data = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Invalid JSON number')))
    if not isinstance(data, dict):
        raise ValueError('JSON object required')
    pending=[(data,0)]
    while pending:
        value,depth=pending.pop()
        if depth>32:raise ValueError('JSON nesting limit reached')
        if isinstance(value,dict):pending.extend((child,depth+1) for child in value.values())
        elif isinstance(value,list):pending.extend((child,depth+1) for child in value)
    return data


def _prefix(store_id):
    if not ID.fullmatch(store_id):
        raise ValueError('Invalid store reference')
    return 'CC_MONITOR_' + store_id.upper() + '_'


def _commerce_secret(env, item, stores):
    key = 'SHOPIFY_SECRET' if item['platform'] == 'shopify' else 'WOOCOMMERCE_SECRET'
    secret = env.get(_prefix(item['id']) + key)
    if not isinstance(secret, str) or not secret:
        return None, 'Signing secret is not configured'
    for other in stores:
        if other['id'] == item['id']:
            continue
        other_key = 'SHOPIFY_SECRET' if other['platform'] == 'shopify' else 'WOOCOMMERCE_SECRET'
        other_secret = env.get(_prefix(other['id']) + other_key)
        if isinstance(other_secret, str) and other_secret and hmac.compare_digest(secret.encode(), other_secret.encode()):
            return None, 'Each store needs a separate signing secret'
    return secret, None


def _configuration(env, item, stores):
    prefix = _prefix(item['id'])
    secret, setup_error = _commerce_secret(env, item, stores)
    keys = ['PAYPAL_CLIENT_ID', 'PAYPAL_CLIENT_SECRET', 'PAYPAL_WEBHOOK_ID', 'PAYPAL_MERCHANT_ID']
    return {'commerce_configured': bool(secret), 'commerce_setup_error': setup_error,
            'paypal_configured': env.get(prefix + 'ALLOW_SANDBOX') == '1' and all(env.get(prefix + k) for k in keys),
            'environment': 'sandbox', 'connection_verified': False}


def make_server(db_path, *, host='127.0.0.1', port=8790, environ=None,
                paypal_factory=None, start_scanner=True, ingress_limits=None, ingress_clock=time.monotonic):
    if host not in {'127.0.0.1', 'localhost'}:
        raise ValueError('Monitoring server must bind to loopback')
    limits = ingress_limits or IngressLimits()
    limiter = WebhookLimiter(limits, ingress_clock)
    env = dict(os.environ if environ is None else environ)
    token = env.get('CRASHCART_MONITOR_TOKEN', '')
    if not isinstance(token, str) or len(token) < 24:
        raise ValueError('Set a private CRASHCART_MONITOR_TOKEN of at least 24 characters')
    public_origin = env.get('CRASHCART_MONITOR_PUBLIC_ORIGIN', '')
    if public_origin:
        origin = urlsplit(public_origin)
        if origin.scheme != 'https' or not origin.hostname or origin.username or origin.password or origin.path not in {'', '/'} or origin.query or origin.fragment:
            raise ValueError('Public origin must be an exact HTTPS origin')
        public_origin = 'https://' + origin.netloc
    secure_cookie = bool(public_origin) or env.get('CRASHCART_MONITOR_SECURE_COOKIE') == '1'
    store = MonitorStore(db_path)
    sessions, lock, stop = {}, threading.Lock(), threading.Event()
    failed_logins = {}
    scan_state = {'status': 'starting' if start_scanner else 'disabled', 'last_scan_at': None}
    paypal_factory = paypal_factory or (lambda values: PayPalSandbox(environ=values, timeout=5))

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def setup(self):
            super().setup()
            self.connection.settimeout(limits.request_timeout)

        def log_message(self, *args):
            pass

        def send(self, status, data, kind='application/json', cookie=None, retry_after=None):
            try:
                return self._send(status,data,kind,cookie,retry_after)
            except OSError:
                self.close_connection=True

        def _send(self, status, data, kind='application/json', cookie=None, retry_after=None):
            raw = data if isinstance(data, bytes) else json.dumps(data, allow_nan=False).encode()
            self.close_connection = True
            self.send_response(status)
            self.send_header('Connection', 'close')
            for key, value in {'Content-Type': kind, 'Content-Length': str(len(raw)),
                'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
                'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"}.items():
                self.send_header(key, value)
            if retry_after is not None:
                self.send_header('Retry-After', str(retry_after))
            if cookie:
                self.send_header('Set-Cookie', cookie)
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(raw)

        def body(self):
            if self.headers.get_all('Transfer-Encoding', []) or len(self.headers.get_all('Content-Length', [])) != 1:
                raise ValueError('One Content-Length required')
            if not re.fullmatch(r'[0-9]{1,10}', self.headers['Content-Length']):
                raise ValueError('Invalid Content-Length')
            size = int(self.headers['Content-Length'])
            if not 0 < size <= MAX_BODY:
                raise ValueError('Body too large or empty')
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError('Incomplete body')
            return raw

        def unique_headers(self):
            names = ['Host','Origin','Cookie','X-CrashCart-Request','Content-Length','Transfer-Encoding',
                'X-Shopify-Hmac-Sha256','X-Shopify-Shop-Domain','X-Shopify-Topic','X-Shopify-Webhook-Id',
                'X-WC-Webhook-Signature','X-WC-Webhook-Source','X-WC-Webhook-Topic','X-WC-Webhook-Delivery-ID',
                'Paypal-Auth-Algo','Paypal-Cert-Url','Paypal-Transmission-Id','Paypal-Transmission-Sig','Paypal-Transmission-Time']
            return all(len(self.headers.get_all(name, [])) <= 1 for name in names)

        def paypal_headers_valid(self):
            required = ['Paypal-Auth-Algo','Paypal-Cert-Url','Paypal-Transmission-Id','Paypal-Transmission-Sig','Paypal-Transmission-Time']
            if any(len(self.headers.get_all(name, [])) != 1 or not 0 < len(self.headers[name]) <= 8192 or any(ord(char)<33 or ord(char)>126 for char in self.headers[name]) for name in required):return False
            try:
                cert=urlsplit(self.headers['Paypal-Cert-Url'])
                stamp=datetime.fromisoformat(self.headers['Paypal-Transmission-Time'].replace('Z','+00:00'))
                signature=base64.b64decode(self.headers['Paypal-Transmission-Sig'],validate=True)
                return bool(signature) and stamp.tzinfo is not None and self.headers['Paypal-Auth-Algo']=='SHA256withRSA' and cert.scheme=='https' and cert.hostname in {'api.paypal.com','api.sandbox.paypal.com','api-m.sandbox.paypal.com'} and not cert.username and not cert.password and cert.port in (None,443) and cert.path.startswith('/v1/notifications/certs/') and not cert.query and not cert.fragment
            except (ValueError,TypeError,binascii.Error):return False

        def admit_webhook(self,path):
            retry=limiter.global_admit()
            if retry:
                self.send(503,{'error':'Too many deliveries. Try again shortly.'},retry_after=retry);return None
            if not self.unique_headers():
                self.send(400,{'error':'Duplicate request headers are not accepted'});return None
            bits=path.strip('/').split('/')
            if len(bits)!=3 or not ID.fullmatch(bits[1]):
                self.send(404,{'error':'Webhook not found'});return None
            item=store.get_store(bits[1])
            retry=limiter.store_admit(item['id'])
            if retry:
                self.send(503,{'error':'Store delivery limit reached. Try again shortly.'},retry_after=retry);return None
            return item

        def reject_method(self):
            try:
                path=urlsplit(self.path).path
                if path.startswith('/webhooks/') and self.admit_webhook(path) is None:return
                self.send(405,{'error':'This method is not supported'})
            except ValueError:self.send(400,{'error':'Invalid request target'})
            except KeyError:self.send(404,{'error':'Store not found'})
            except sqlite3.Error:self.send(503,{'error':'Monitoring is busy. Try again shortly.'},retry_after=1)

        do_PUT=do_PATCH=do_DELETE=do_OPTIONS=do_HEAD=reject_method

        def authenticated(self):
            try:
                value = SimpleCookie(self.headers.get('Cookie', '')[:8192])[COOKIE].value
            except (KeyError, ValueError, CookieError):
                return False
            key = hashlib.sha256(value.encode()).hexdigest()
            with lock:
                if sessions.get(key, 0) <= time.monotonic():
                    sessions.pop(key, None)
                    return False
            return True

        def csrf(self):
            if self.headers.get('X-CrashCart-Request') != '1':
                return False
            origin = self.headers.get('Origin')
            if not origin:
                return True
            host_header = self.headers.get('Host', '')
            scheme = 'https' if secure_cookie else 'http'
            allowed_hosts = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            if public_origin:
                allowed_hosts.add(urlsplit(public_origin).netloc)
            return host_header in allowed_hosts and hmac.compare_digest(origin, scheme + '://' + host_header)

        def public_store(self, item):
            return {**item, 'connections': _configuration(env, item, store.list_stores())}

        def do_GET(self):
            try:path = urlsplit(self.path).path
            except ValueError:return self.send(400, {'error': 'Invalid request target'})
            if path.startswith('/webhooks/'):
                return self.reject_method()
            if not self.unique_headers():
                return self.send(400, {'error': 'Duplicate request headers are not accepted'})
            if path in {'/', '/app.js', '/style.css'}:
                name = {'/': 'index.html', '/app.js': 'app.js', '/style.css': 'style.css'}[path]
                if not (WEB / name).is_file():
                    return self.send(503, {'error': 'Monitoring interface is being prepared'})
                kind = {'index.html': 'text/html; charset=utf-8', 'app.js': 'application/javascript', 'style.css': 'text/css'}[name]
                return self.send(200, (WEB / name).read_bytes(), kind)
            if path == '/healthz':
                return self.send(200, {'status': 'degraded' if scan_state['status'] == 'error' else 'ok', 'mode': 'monitor', 'payment_environment': 'sandbox', 'scanner': dict(scan_state)})
            if not self.authenticated():
                return self.send(401, {'error': 'Sign in to continue'})
            try:
                if path == '/api/session':
                    return self.send(200, {'authenticated': True})
                if path == '/api/stores':
                    return self.send(200, {'stores': [self.public_store(x) for x in store.list_stores()]})
                bits = path.strip('/').split('/')
                if len(bits) == 4 and bits[:2] == ['api', 'stores'] and ID.fullmatch(bits[2]):
                    store.get_store(bits[2])
                    if bits[3] == 'orders':
                        return self.send(200, {'orders': store.orders(bits[2])})
                    if bits[3] == 'alerts':
                        return self.send(200, {'alerts': store.alerts(bits[2])})
                return self.send(404, {'error': 'Page not found'})
            except sqlite3.Error:
                return self.send(503, {'error': 'Monitoring is busy. Try again shortly.'}, retry_after=1)
            except KeyError:
                return self.send(404, {'error': 'Store not found'})
            except ValueError:
                return self.send(400, {'error': 'Invalid request'})

        def do_POST(self):
            try:
                path = urlsplit(self.path).path
                if path.startswith('/webhooks/'):
                    item=self.admit_webhook(path)
                    if item is None:return
                    return self.webhook(path,self.body(),item)
                if not self.unique_headers():
                    return self.send(400, {'error': 'Duplicate request headers are not accepted'})
                raw = self.body()
                if not self.csrf():
                    return self.send(403, {'error': 'Request was not accepted'})
                data = _json(raw)
                if path == '/api/login':
                    value = data.get('token', '')
                    peer, now = self.client_address[0], time.monotonic()
                    with lock:
                        attempts = [stamp for stamp in failed_logins.get(peer, []) if now - stamp < 60]
                        failed_logins[peer] = attempts
                        if len(attempts) >= 5:
                            return self.send(429, {'error': 'Wait a minute before trying again'})
                    if not isinstance(value, str) or not hmac.compare_digest(value, token):
                        with lock:
                            failed_logins[peer].append(now)
                        return self.send(401, {'error': 'Access key was not accepted'})
                    with lock:
                        failed_logins.pop(peer, None)
                    value = secrets.token_urlsafe(32)
                    with lock:
                        now = time.monotonic()
                        for key in list(sessions):
                            if sessions[key] <= now:
                                del sessions[key]
                        if len(sessions) >= 64:
                            return self.send(429, {'error': 'Too many active sessions'})
                        sessions[hashlib.sha256(value.encode()).hexdigest()] = now + 28800
                    secure = '; Secure' if secure_cookie else ''
                    return self.send(200, {'authenticated': True}, cookie=f'{COOKIE}={value}; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800{secure}')
                if not self.authenticated():
                    return self.send(401, {'error': 'Sign in to continue'})
                if path == '/api/logout':
                    cookie = SimpleCookie(self.headers.get('Cookie', ''))
                    with lock:
                        sessions.pop(hashlib.sha256(cookie[COOKIE].value.encode()).hexdigest(), None)
                    return self.send(200, {'authenticated': False}, cookie=f'{COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0')
                if path == '/api/stores':
                    item = store.create_store(data.get('name'), data.get('platform'), data.get('domain'), data.get('promise_seconds'))
                    return self.send(201, {'store': self.public_store(item)})
                bits = path.strip('/').split('/')
                if len(bits) == 6 and bits[:2] == ['api', 'stores'] and bits[3] == 'alerts' and bits[5] == 'ack':
                    store.acknowledge_alert(bits[2], bits[4])
                    return self.send(200, {'acknowledged': True})
                return self.send(404, {'error': 'Action not found'})
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True
                return
            except sqlite3.Error:
                return self.send(503, {'error': 'Monitoring is busy. Try again shortly.'}, retry_after=1)
            except ReceiptCapacityError:
                return self.send(503, {'error': 'This workspace cannot receive more store updates right now. Try again later.'}, retry_after=60)
            except PaymentValidationError:
                return self.send(400, {'error': 'Payment data was not accepted'})
            except PayPalError:
                return self.send(503, {'error': 'Payment verification is unavailable'})
            except KeyError:
                return self.send(404, {'error': 'Reference not found'})
            except (ValueError, TypeError, UnicodeError, TimeoutError, RecursionError) as exc:
                error = SHOPIFY_ADDRESS_HINT if str(exc) == SHOPIFY_ADDRESS_HINT else 'The request could not be accepted'
                return self.send(400, {'error': error})

        def webhook(self, path, raw, item):
            bits = path.strip('/').split('/')
            if len(bits) != 3 or not ID.fullmatch(bits[1]):
                return self.send(404, {'error': 'Webhook not found'})
            provider, prefix = bits[2], _prefix(item['id'])
            headers = dict(self.headers.items())
            for name in ['X-Shopify-Hmac-Sha256', 'X-WC-Webhook-Signature', 'Paypal-Transmission-Sig']:
                if len(self.headers.get_all(name, [])) > 1:
                    return self.send(401, {'error': 'Signature was not accepted'})
            if provider in {'shopify', 'woocommerce'}:
                if provider != item['platform']:
                    return self.send(400, {'error': 'Store platform does not match'})
                secret, setup_error = _commerce_secret(env, item, store.list_stores())
                if not secret:
                    return self.send(503, {'error': setup_error})
                try:
                    update = parse_shopify(raw, headers, secret, item['domain']) if provider == 'shopify' else parse_woocommerce(raw, headers, secret, 'https://' + item['domain'])
                except ValueError:
                    return self.send(401, {'error': 'Store delivery was not accepted'})
                values = asdict(update)
                values['payment_references'] = list(values['payment_references'])
                store.upsert_order(item['id'], values['platform_order_id'], **{key: values[key] for key in ['display_number', 'currency', 'total_minor', 'payment_references', 'fulfillment_status', 'fulfilled_at', 'updated_at', 'event_id']})
                store.scan(datetime.now(timezone.utc).isoformat())
                return self.send(200, {'received': True})
            if provider != 'paypal':
                return self.send(404, {'error': 'Webhook not found'})
            if not _configuration(env, item, store.list_stores())['paypal_configured']:
                return self.send(503, {'error': 'Payment verification is not configured'})
            if not self.paypal_headers_valid():
                return self.send(401, {'error': 'Signature headers were not accepted'})
            event = parse_webhook_event(raw)
            values = {'CRASHCART_ALLOW_SANDBOX': env[prefix + 'ALLOW_SANDBOX'], **{key: env[prefix + key] for key in ['PAYPAL_CLIENT_ID', 'PAYPAL_CLIENT_SECRET', 'PAYPAL_WEBHOOK_ID']}}
            if not paypal_factory(values).verify_webhook(headers, event, raw_body=raw):
                return self.send(401, {'error': 'Signature was not accepted'})
            if event.get('event_type') != 'PAYMENT.CAPTURE.COMPLETED':
                return self.send(200, {'received': True, 'ignored': True})
            resource = event.get('resource', {})
            if not isinstance(resource, dict) or not isinstance(resource.get('payee'), dict):
                return self.send(400, {'error': 'Payment data was not accepted'})
            if resource.get('status') != 'COMPLETED' or resource.get('payee', {}).get('merchant_id') != env[prefix + 'PAYPAL_MERCHANT_ID']:
                return self.send(400, {'error': 'Payment does not belong to this store'})
            amount, currency = _observed_money(resource.get('amount'))
            store.record_payment(item['id'], capture_id=resource['id'], reference=resource['id'], currency=currency, amount_minor=amount, completed_at=resource['create_time'], event_id=event['id'])
            store.scan(datetime.now(timezone.utc).isoformat())
            return self.send(200, {'received': True})

    server = BoundedHTTPServer((host, port), Handler, limits=limits)
    server.monitor_limiter = limiter
    server.monitor_store, server.monitor_stop = store, stop
    original_close = server.server_close
    def close():
        stop.set()
        if getattr(server, 'monitor_scanner', None):
            server.monitor_scanner.join(timeout=6)
        original_close()
    server.server_close = close
    if start_scanner:
        def scan():
            while not stop.is_set():
                try:
                    checked_at = datetime.now(timezone.utc).isoformat()
                    store.scan(checked_at)
                    scan_state.update(status='running', last_scan_at=checked_at)
                except (ValueError, OSError, sqlite3.Error):
                    scan_state['status'] = 'error'
                stop.wait(5)
        server.monitor_scanner = threading.Thread(target=scan, daemon=True)
        server.monitor_scanner.start()
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='var/monitor.sqlite3')
    parser.add_argument('--port', type=int, default=8790)
    args = parser.parse_args()
    server = make_server(args.db, port=args.port)
    print(f'CrashCart monitoring: http://127.0.0.1:{server.server_port}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
