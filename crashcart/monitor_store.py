"""Store-scoped monitoring facts. Merchant fulfilment is not physical delivery.

Only a signature/merchant-verifying PayPal ingress may call record_payment.
Commerce payment/status claims alone never establish confirmed payment here.
"""

from __future__ import annotations
import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit


def timestamp(value):
    if not isinstance(value, str) or len(value) > 64:
        raise ValueError('Invalid timestamp')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('Invalid timestamp') from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError('Timezone required')
    return parsed.astimezone(timezone.utc).isoformat(timespec='microseconds')


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def _text(value, name, limit=240):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError('Invalid ' + name)
    return value.strip()


def _money(currency, amount, positive=False):
    if not isinstance(currency, str) or not re.fullmatch('[A-Z]{3}', currency):
        raise ValueError('Invalid currency')
    if type(amount) is not int or not (1 if positive else 0) <= amount <= 10**15:
        raise ValueError('Invalid minor-unit amount')


SHOPIFY_ADDRESS_HINT = 'Use your store’s …myshopify.com address, without a page path or a custom port.'


class ReceiptCapacityError(RuntimeError):
    """Unexpired receipts fill a configured durable admission limit."""


class MonitorStore:
    def __init__(
        self,
        path,
        *,
        receipt_retention_seconds=30 * 86400,
        receipt_alias_limit=32,
        receipt_limit_per_store_kind=10_000,
        receipt_limit_global=100_000,
        clock=None,
        busy_timeout_seconds=2,
    ):
        if type(busy_timeout_seconds) not in {int, float} or not 0 < busy_timeout_seconds <= 5:
            raise ValueError('SQLite busy wait must be above zero and at most five seconds')
        self.busy_timeout_seconds = float(busy_timeout_seconds)
        if type(receipt_retention_seconds) is not int or not 60 <= receipt_retention_seconds <= 365 * 86400:
            raise ValueError('Receipt retention must be between 60 seconds and one year')
        if (
            type(receipt_alias_limit) is not int
            or not 1 <= receipt_alias_limit <= 1024
            or type(receipt_limit_per_store_kind) is not int
            or not 1 <= receipt_limit_per_store_kind <= 1_000_000
            or type(receipt_limit_global) is not int
            or not receipt_limit_per_store_kind <= receipt_limit_global <= 10_000_000
        ):
            raise ValueError('Invalid durable receipt capacity')
        if clock is not None and not callable(clock):
            raise ValueError('Receipt clock must be callable')
        self.receipt_retention_seconds = receipt_retention_seconds
        self.receipt_alias_limit = receipt_alias_limit
        self.receipt_limit_per_store_kind = receipt_limit_per_store_kind
        self.receipt_limit_global = receipt_limit_global
        self._receipt_clock = clock or _now
        migration_time = self._receipt_now()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript(
                (
                    '\n            CREATE TABLE IF NOT EXISTS monitor_stores(id TEXT PRIMARY KEY,name '
                    'TEXT NOT NULL,platform TEXT NOT NULL,domain TEXT NOT NULL,promise_seconds INTEGE'
                    'R NOT NULL,created_at TEXT NOT NULL);\n            CREATE TABLE IF NOT EXISTS mon'
                    'itor_events(store_id TEXT NOT NULL REFERENCES monitor_stores(id),kind TEXT NOT N'
                    'ULL,event_id TEXT NOT NULL,payload_hash TEXT NOT NULL,received_at TEXT NOT NULL,'
                    'PRIMARY KEY(store_id,kind,event_id));\n            CREATE TABLE IF NOT EXISTS mon'
                    'itor_orders(store_id TEXT NOT NULL REFERENCES monitor_stores(id),platform_order_'
                    'id TEXT NOT NULL,display_number TEXT NOT NULL,currency TEXT NOT NULL,total_minor'
                    ' INTEGER NOT NULL,payment_references TEXT NOT NULL,fulfillment_status TEXT NOT N'
                    'ULL,fulfilled_at TEXT,updated_at TEXT NOT NULL,promise_seconds INTEGER NOT NULL,'
                    'PRIMARY KEY(store_id,platform_order_id));\n            CREATE TABLE IF NOT EXISTS'
                    ' monitor_payments(store_id TEXT NOT NULL REFERENCES monitor_stores(id),capture_i'
                    'd TEXT NOT NULL,reference TEXT NOT NULL,currency TEXT NOT NULL,amount_minor INTE'
                    'GER NOT NULL,completed_at TEXT NOT NULL,verified_by TEXT NOT NULL,PRIMARY KEY(st'
                    'ore_id,capture_id));\n            CREATE TABLE IF NOT EXISTS monitor_associations'
                    '(store_id TEXT NOT NULL,platform_order_id TEXT NOT NULL,capture_id TEXT NOT NULL'
                    ',completed_at TEXT NOT NULL,promise_seconds INTEGER NOT NULL,PRIMARY KEY(store_i'
                    'd,platform_order_id),FOREIGN KEY(store_id,platform_order_id) REFERENCES monitor_'
                    'orders(store_id,platform_order_id),FOREIGN KEY(store_id,capture_id) REFERENCES m'
                    'onitor_payments(store_id,capture_id));\n            CREATE TABLE IF NOT EXISTS mo'
                    'nitor_alerts(id TEXT PRIMARY KEY,store_id TEXT NOT NULL,platform_order_id TEXT N'
                    'OT NULL,kind TEXT NOT NULL,capture_id TEXT NOT NULL,deadline_at TEXT NOT NULL,de'
                    'tected_at TEXT NOT NULL,resolved_at TEXT,acknowledged_at TEXT,retracted_at TEXT,'
                    'resolution_reason TEXT,UNIQUE(store_id,platform_order_id,capture_id,deadline_at)'
                    ',FOREIGN KEY(store_id,platform_order_id) REFERENCES monitor_orders(store_id,plat'
                    'form_order_id));\n            '
                )
            )
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            event_columns = {row['name'] for row in db.execute('PRAGMA table_info(monitor_events)')}
            if 'received_at' not in event_columns:
                db.execute('ALTER TABLE monitor_events ADD COLUMN received_at TEXT')
            # Legacy arrival time is unknown. Preserve every old identity for a
            # full receiver-clock retention window; never infer age from payloads.
            db.execute('UPDATE monitor_events SET received_at=? WHERE received_at IS NULL', (migration_time,))
            db.execute('CREATE INDEX IF NOT EXISTS monitor_event_content ON monitor_events(store_id,kind,payload_hash)')
            db.execute('CREATE INDEX IF NOT EXISTS monitor_event_age ON monitor_events(received_at)')
            self._prune_receipts(db, migration_time)
            order_columns = {row['name'] for row in db.execute('PRAGMA table_info(monitor_orders)')}
            if 'promise_seconds' not in order_columns:
                db.execute('ALTER TABLE monitor_orders ADD COLUMN promise_seconds INTEGER')
                db.execute(
                    'UPDATE monitor_orders SET promise_seconds=(SELECT promise_seconds FROM monitor_stores WHERE monitor_stores.id=monitor_orders.store_id) WHERE promise_seconds IS NULL'
                )
            alert_columns = {row['name'] for row in db.execute('PRAGMA table_info(monitor_alerts)')}
            for column in ['retracted_at', 'resolution_reason']:
                if column not in alert_columns:
                    db.execute('ALTER TABLE monitor_alerts ADD COLUMN ' + column + ' TEXT')
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            # Preserve an earlier recorded deadline association when upgrading an
            # existing inbox. Without such history, bind the current unique match.
            for alert in db.execute('SELECT * FROM monitor_alerts ORDER BY detected_at,id').fetchall():
                payment = db.execute(
                    'SELECT completed_at FROM monitor_payments WHERE store_id=? AND capture_id=?',
                    (alert['store_id'], alert['capture_id']),
                ).fetchone()
                if payment:
                    duration = int(
                        (
                            datetime.fromisoformat(alert['deadline_at'])
                            - datetime.fromisoformat(payment['completed_at'])
                        ).total_seconds()
                    )
                    if duration > 0:
                        db.execute(
                            'INSERT OR IGNORE INTO monitor_associations VALUES (?,?,?,?,?)',
                            (
                                alert['store_id'],
                                alert['platform_order_id'],
                                alert['capture_id'],
                                payment['completed_at'],
                                duration,
                            ),
                        )
            for row in db.execute('SELECT id FROM monitor_stores').fetchall():
                list(self._orders(db, row['id']))
        self.path.chmod(0o600)

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=self.busy_timeout_seconds)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _store(db, store_id):
        row = db.execute('SELECT * FROM monitor_stores WHERE id=?', (store_id,)).fetchone()
        if row is None:
            raise KeyError('Store not found')
        return dict(row)

    def _receipt_now(self):
        value = self._receipt_clock()
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError('Receipt clock needs a timezone')
            value = value.isoformat()
        return timestamp(value)

    def _prune_receipts(self, db, now):
        cutoff = (datetime.fromisoformat(now) - timedelta(seconds=self.receipt_retention_seconds)).isoformat(
            timespec='microseconds'
        )
        return db.execute('DELETE FROM monitor_events WHERE received_at<=?', (cutoff,)).rowcount

    def prune_receipts(self):
        """Expire receiver-time receipts only; retain all business history.

        SQLite may retain freed pages. This bounds live receipt rows, not bytes.
        """
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            return self._prune_receipts(db, self._receipt_now())

    def _event(self, db, store_id, kind, event_id, facts):
        """Retain every accepted identity for a finite receiver-time window.

        Original and alias IDs cannot change facts while retained. Identical
        normalized content under a new ID gets a bounded identity receipt but
        does not repeat business mutation. Capacity exhaustion fails closed;
        unexpired identities are never evicted to admit another delivery.
        Redelivery never refreshes an existing receipt's arrival time.
        After expiry, immutable payments, first associations and order chronology
        protect business history, but the old ID conflict guarantee has ended.
        """
        event_id = _text(event_id, 'event id')
        digest = hashlib.sha256(json.dumps(facts, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        now = self._receipt_now()
        self._prune_receipts(db, now)
        old = db.execute(
            'SELECT payload_hash FROM monitor_events WHERE store_id=? AND kind=? AND event_id=?',
            (store_id, kind, event_id),
        ).fetchone()
        if old:
            if old[0] != digest:
                raise ValueError('Event id reused with different facts')
            return False
        aliases = db.execute(
            'SELECT COUNT(*) FROM monitor_events WHERE store_id=? AND kind=? AND payload_hash=?',
            (store_id, kind, digest),
        ).fetchone()[0]
        local = db.execute(
            'SELECT COUNT(*) FROM monitor_events WHERE store_id=? AND kind=?', (store_id, kind)
        ).fetchone()[0]
        total = db.execute('SELECT COUNT(*) FROM monitor_events').fetchone()[0]
        if (
            aliases >= self.receipt_alias_limit
            or local >= self.receipt_limit_per_store_kind
            or total >= self.receipt_limit_global
        ):
            raise ReceiptCapacityError('Receipt storage is full; retry after retained receipts expire')
        db.execute(
            'INSERT INTO monitor_events (store_id,kind,event_id,payload_hash,received_at) VALUES (?,?,?,?,?)',
            (store_id, kind, event_id, digest, now),
        )
        return aliases == 0

    def create_store(self, name, platform, domain, promise_seconds):
        name = _text(name, 'store name', 100)
        if platform not in {'shopify', 'woocommerce'}:
            raise ValueError('Unsupported platform')
        origin = _text(domain, 'domain', 255)
        parts = urlsplit(origin if '://' in origin else 'https://' + origin)
        shop_domain = None
        if platform == 'shopify':
            hint = SHOPIFY_ADDRESS_HINT
            try:
                host = parts.hostname or ''
                port = parts.port
            except ValueError as exc:
                raise ValueError(hint) from exc
            if (
                parts.scheme != 'https'
                or not re.fullmatch(r'[a-z0-9][a-z0-9-]*\.myshopify\.com', host.lower())
                or parts.username
                or parts.password
                or parts.query
                or parts.fragment
                or parts.path not in {'', '/'}
                or port not in {None, 443}
                or (':' in parts.netloc and port is None)
            ):
                raise ValueError(hint)
            shop_domain = host.lower()
        elif (
            parts.scheme != 'https'
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
        ):
            raise ValueError('HTTPS store origin required')
        if type(promise_seconds) is not int or not 1 <= promise_seconds <= 31536000:
            raise ValueError('Invalid promise duration')
        store_path = parts.path.rstrip('/')
        if any(part in {'.', '..'} for part in store_path.split('/')) or '%' in store_path or '\\' in store_path:
            raise ValueError('Invalid store base path')
        store = dict(
            id='store_' + uuid.uuid4().hex,
            name=name,
            platform=platform,
            domain=shop_domain or parts.netloc.lower() + store_path,
            promise_seconds=promise_seconds,
            created_at=_now(),
        )
        with self._db() as db:
            db.execute(
                'INSERT INTO monitor_stores VALUES (:id,:name,:platform,:domain,:promise_seconds,:created_at)', store
            )
        return store

    def get_store(self, store_id):
        with self._db() as db:
            return self._store(db, store_id)

    def list_stores(self):
        with self._db() as db:
            return [dict(r) for r in db.execute('SELECT * FROM monitor_stores ORDER BY created_at,id')]

    def upsert_order(
        self,
        store_id,
        platform_order_id,
        *,
        display_number,
        currency,
        total_minor,
        payment_references,
        fulfillment_status,
        fulfilled_at,
        updated_at,
        event_id,
    ):
        platform_order_id = _text(platform_order_id, 'order id')
        display_number = _text(display_number, 'order number')
        _money(currency, total_minor)
        if not isinstance(payment_references, list) or len(payment_references) > 100:
            raise ValueError('Invalid payment references')
        refs = sorted(set(_text(r, 'payment reference') for r in payment_references))
        if fulfillment_status not in {'unfulfilled', 'partial', 'fulfilled', 'cancelled'}:
            raise ValueError('Invalid fulfilment status')
        updated_at = timestamp(updated_at)
        fulfilled_at = timestamp(fulfilled_at) if fulfilled_at is not None else None
        if fulfillment_status != 'fulfilled' and fulfilled_at is not None:
            raise ValueError('Only completed fulfilment has a timestamp')
        if fulfilled_at and fulfilled_at > updated_at:
            raise ValueError('Fulfilment follows its snapshot')
        facts = dict(
            platform_order_id=platform_order_id,
            display_number=display_number,
            currency=currency,
            total_minor=total_minor,
            payment_references=refs,
            fulfillment_status=fulfillment_status,
            fulfilled_at=fulfilled_at,
            updated_at=updated_at,
        )
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            store = self._store(db, store_id)
            fresh = self._event(db, store_id, 'order', event_id, facts)
            old = db.execute(
                'SELECT * FROM monitor_orders WHERE store_id=? AND platform_order_id=?', (store_id, platform_order_id)
            ).fetchone()
            effective_fulfilled_at = fulfilled_at
            if (
                fulfillment_status == 'fulfilled'
                and fulfilled_at is None
                and old
                and old['fulfillment_status'] == 'fulfilled'
            ):
                effective_fulfilled_at = old['fulfilled_at']
            if fresh and (old is None or updated_at > old['updated_at']):
                db.execute(
                    (
                        'INSERT INTO monitor_orders (store_id,platform_order_id,display_number,currency,t'
                        'otal_minor,payment_references,fulfillment_status,fulfilled_at,updated_at,promise'
                        '_seconds) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(store_id,platform_order_id) D'
                        'O UPDATE SET display_number=excluded.display_number,currency=excluded.currency,t'
                        'otal_minor=excluded.total_minor,payment_references=excluded.payment_references,f'
                        'ulfillment_status=excluded.fulfillment_status,fulfilled_at=excluded.fulfilled_at'
                        ',updated_at=excluded.updated_at'
                    ),
                    (
                        store_id,
                        platform_order_id,
                        display_number,
                        currency,
                        total_minor,
                        json.dumps(refs),
                        fulfillment_status,
                        effective_fulfilled_at,
                        updated_at,
                        store['promise_seconds'],
                    ),
                )
            elif fresh and old is not None and updated_at == old['updated_at']:
                comparable = dict(old)
                comparable.pop('store_id')
                comparable.pop('promise_seconds')
                comparable['payment_references'] = json.loads(comparable['payment_references'])
                effective_facts = {**facts, 'fulfilled_at': effective_fulfilled_at}
                if comparable != effective_facts:
                    raise ValueError('Conflicting order snapshots at same timestamp')
            list(self._orders(db, store_id))
        return next(o for o in self.orders(store_id) if o['platform_order_id'] == platform_order_id)

    def record_payment(self, store_id, *, capture_id, reference, currency, amount_minor, completed_at, event_id):
        """Caller must first verify signature AND the configured PayPal merchant."""
        capture_id = _text(capture_id, 'capture id')
        reference = _text(reference, 'reference')
        _money(currency, amount_minor, True)
        facts = dict(
            capture_id=capture_id,
            reference=reference,
            currency=currency,
            amount_minor=amount_minor,
            completed_at=timestamp(completed_at),
            verified_by='paypal_signature_verifier_caller',
        )
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            self._store(db, store_id)
            self._event(db, store_id, 'paypal', event_id, facts)
            old = db.execute(
                'SELECT * FROM monitor_payments WHERE store_id=? AND capture_id=?', (store_id, capture_id)
            ).fetchone()
            if old:
                previous = dict(old)
                previous.pop('store_id')
                if previous != facts:
                    raise ValueError('Capture facts are immutable')
            else:
                db.execute(
                    'INSERT INTO monitor_payments VALUES (?,?,?,?,?,?,?)',
                    (
                        store_id,
                        capture_id,
                        reference,
                        currency,
                        amount_minor,
                        facts['completed_at'],
                        facts['verified_by'],
                    ),
                )
            list(self._orders(db, store_id))
        return dict(store_id=store_id, **facts)

    def _orders(self, db, store_id):
        self._store(db, store_id)
        orders = [
            dict(r)
            for r in db.execute('SELECT * FROM monitor_orders WHERE store_id=? ORDER BY platform_order_id', (store_id,))
        ]
        payments = [dict(r) for r in db.execute('SELECT * FROM monitor_payments WHERE store_id=?', (store_id,))]
        for order in orders:
            order['payment_references'] = json.loads(order['payment_references'])
        matches = {
            p['capture_id']: [
                o['platform_order_id']
                for o in orders
                if p['reference'] in o['payment_references'] or p['capture_id'] in o['payment_references']
            ]
            for p in payments
        }
        for order in orders:
            candidates = [p for p in payments if order['platform_order_id'] in matches[p['capture_id']]]
            order.update(
                payment_state='unmatched',
                capture_id=None,
                paid_at=None,
                deadline_at=None,
                verified_by=None,
                fulfillment_basis='merchant_reported_completion_not_physical_delivery',
                fulfillment_timing='unknown'
                if order['fulfillment_status'] == 'fulfilled' and not order['fulfilled_at']
                else 'recorded',
            )
            if len(candidates) > 1 or any(len(matches[p['capture_id']]) != 1 for p in candidates):
                order['payment_state'] = 'ambiguous'
            elif candidates:
                p = candidates[0]
                if p['currency'] != order['currency'] or p['amount_minor'] != order['total_minor']:
                    order['payment_state'] = 'mismatch'
                else:
                    db.execute(
                        'INSERT OR IGNORE INTO monitor_associations VALUES (?,?,?,?,?)',
                        (
                            store_id,
                            order['platform_order_id'],
                            p['capture_id'],
                            p['completed_at'],
                            order['promise_seconds'],
                        ),
                    )
                    binding = db.execute(
                        'SELECT * FROM monitor_associations WHERE store_id=? AND platform_order_id=?',
                        (store_id, order['platform_order_id']),
                    ).fetchone()
                    if binding['capture_id'] != p['capture_id']:
                        order['payment_state'] = 'ambiguous'
                    else:
                        order.update(
                            payment_state='confirmed',
                            capture_id=binding['capture_id'],
                            paid_at=binding['completed_at'],
                            deadline_at=(
                                datetime.fromisoformat(binding['completed_at'])
                                + timedelta(seconds=binding['promise_seconds'])
                            ).isoformat(timespec='microseconds'),
                            verified_by=p['verified_by'],
                        )
            yield order

    def orders(self, store_id):
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            return list(self._orders(db, store_id))

    def scan(self, now):
        now = timestamp(now)
        new = []
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            for store in db.execute('SELECT id FROM monitor_stores ORDER BY id').fetchall():
                for o in self._orders(db, store['id']):
                    if o['payment_state'] != 'confirmed':
                        db.execute(
                            'UPDATE monitor_alerts SET retracted_at=COALESCE(retracted_at,?),resolution_reason=? WHERE store_id=? AND platform_order_id=?',
                            (now, 'payment_match_uncertain', store['id'], o['platform_order_id']),
                        )
                        continue
                    deadline = o['deadline_at']
                    fulfilled = o['fulfilled_at']
                    if o['fulfillment_status'] == 'fulfilled' and fulfilled is None:
                        db.execute(
                            'UPDATE monitor_alerts SET retracted_at=COALESCE(retracted_at,?),resolution_reason=? WHERE store_id=? AND platform_order_id=? AND capture_id=? AND deadline_at=?',
                            (
                                now,
                                'fulfillment_time_unknown',
                                store['id'],
                                o['platform_order_id'],
                                o['capture_id'],
                                deadline,
                            ),
                        )
                        continue
                    if fulfilled and fulfilled <= deadline:
                        db.execute(
                            'UPDATE monitor_alerts SET resolved_at=?,retracted_at=COALESCE(retracted_at,?),resolution_reason=? WHERE store_id=? AND platform_order_id=? AND capture_id=? AND deadline_at=?',
                            (
                                fulfilled,
                                now,
                                'on_time_fulfillment_received_late',
                                store['id'],
                                o['platform_order_id'],
                                o['capture_id'],
                                deadline,
                            ),
                        )
                        continue
                    if now <= deadline:
                        continue
                    if fulfilled and fulfilled > now:
                        fulfilled = None
                    alert = dict(
                        id='alert_' + uuid.uuid4().hex,
                        store_id=store['id'],
                        platform_order_id=o['platform_order_id'],
                        kind='late_fulfillment',
                        capture_id=o['capture_id'],
                        deadline_at=deadline,
                        detected_at=now,
                        resolved_at=fulfilled,
                        acknowledged_at=None,
                        retracted_at=None,
                        resolution_reason='fulfilled_after_deadline' if fulfilled else None,
                    )
                    result = db.execute(
                        (
                            'INSERT OR IGNORE INTO monitor_alerts (id,store_id,platform_order_id,kind,capture'
                            '_id,deadline_at,detected_at,resolved_at,acknowledged_at,retracted_at,resolution_'
                            'reason) VALUES (:id,:store_id,:platform_order_id,:kind,:capture_id,:deadline_at,'
                            ':detected_at,:resolved_at,:acknowledged_at,:retracted_at,:resolution_reason)'
                        ),
                        alert,
                    )
                    if result.rowcount:
                        new.append(alert)
                    elif fulfilled:
                        db.execute(
                            "UPDATE monitor_alerts SET resolved_at=?,retracted_at=NULL,resolution_reason='fulfilled_after_deadline' WHERE store_id=? AND platform_order_id=? AND capture_id=? AND deadline_at=?",
                            (fulfilled, store['id'], o['platform_order_id'], o['capture_id'], deadline),
                        )
                    else:
                        db.execute(
                            'UPDATE monitor_alerts SET resolved_at=NULL,retracted_at=NULL,resolution_reason=NULL WHERE store_id=? AND platform_order_id=? AND capture_id=? AND deadline_at=?',
                            (store['id'], o['platform_order_id'], o['capture_id'], deadline),
                        )
        return new

    def alerts(self, store_id):
        with self._db() as db:
            self._store(db, store_id)
            return [
                dict(r)
                for r in db.execute(
                    'SELECT * FROM monitor_alerts WHERE store_id=? ORDER BY detected_at DESC,id', (store_id,)
                )
            ]

    def acknowledge_alert(self, store_id, alert_id):
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            self._store(db, store_id)
            result = db.execute(
                'UPDATE monitor_alerts SET acknowledged_at=COALESCE(acknowledged_at,?) WHERE store_id=? AND id=?',
                (_now(), store_id, alert_id),
            )
            if not result.rowcount:
                raise KeyError('Alert not found')
            return dict(
                db.execute('SELECT * FROM monitor_alerts WHERE store_id=? AND id=?', (store_id, alert_id)).fetchone()
            )
