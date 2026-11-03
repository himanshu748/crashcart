#!/usr/bin/env python3
"""Export an existing sandbox purchase; never create, capture, or fulfill one.

Optional network probes perform one provider order GET and rejected local price
requests. Credentials stay in memory; only allowlisted payment evidence is saved.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from crashcart.config import load_env
from crashcart.paypal import PayPalSandbox, PayPalError, _NoRedirects, sanitize_snapshot, validate_capture


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def select(data, fields):
    return {key: data[key] for key in fields.split() if key in data}


def ticket(data):
    return select(data, 'id purchase_id created_at')


def merchant(data):
    result = select(data, 'purchase_id run_id order_id known status payment_state ticket_count observed_at')
    result['tickets'] = [ticket(t) for t in data.get('tickets') or []]
    return result


def event(data):
    result = select(data, 'id run_id purchase_id order_id operation_id source event_type event_time observed_at caused_by')
    body = json.loads(data['payload_json'])
    kind = data['event_type']
    if kind in {'order_created', 'pre_capture_read', 'capture_transport_response', 'independent_order_read'}:
        clean = sanitize_snapshot(body)
    elif kind == 'customer_observation':
        clean = select(body, 'action browser_kind url_path visible_text')
    elif kind == 'entitlement_read':
        clean = merchant(body)
    elif kind == 'ticket_fulfilled':
        clean = ticket(body)
    elif kind in {'fault_activated', 'fault_deactivated'}:
        clean = select(body, 'kind merchant delay_seconds')
    elif kind == 'invariant_result':
        clean = select(body, 'deadline invariant_version reason signature source_ids verdict')
    elif kind in {'order_unresolved', 'capture_unresolved'}:
        clean = select(body, 'code ambiguous')
    else:
        raise ValueError('Unreviewed event type cannot be exported: ' + kind)
    result['payload'] = clean
    result['persisted_payload_sha256'] = sha(data['payload_json'].encode())
    return result


def operation(data):
    result = select(data, 'id purchase_id semantic_key request_id state created_at updated_at')
    body = json.loads(data['body_json'])
    clean = sanitize_snapshot(body)
    if 'payment_source' in body:
        experience = body['payment_source']['paypal']['experience_context']
        clean['payment_source'] = {'paypal': {'experience_context': select(experience, 'shipping_preference user_action return_url cancel_url')}}
    # Keep the server-owned, fixed item description without copying unknown fields.
    for unit, original in zip(clean.get('purchase_units', []), body.get('purchase_units', [])):
        if original.get('description') == 'Resilient systems workshop ticket':
            unit['description'] = original['description']
    result['body'] = clean
    result['persisted_body_sha256'] = sha(data['body_json'].encode())
    result['response'] = sanitize_snapshot(json.loads(data['response_json'])) if data['response_json'] else None
    return result


def read_records(db_path, run_id):
    with sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')
        run = dict(db.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone())
        purchase = dict(db.execute('SELECT * FROM purchases WHERE run_id=?', (run_id,)).fetchone())
        ops = [operation(dict(row)) for row in db.execute('SELECT * FROM operations WHERE purchase_id=? ORDER BY created_at,id', (purchase['id'],))]
        events = [event(dict(row)) for row in db.execute('SELECT * FROM events WHERE run_id=? ORDER BY observed_at,id', (run_id,))]
        tickets = [ticket(dict(row)) for row in db.execute('SELECT * FROM tickets WHERE purchase_id=? ORDER BY created_at,id', (purchase['id'],))]
        return {'observed_at': now(), 'run': select(run, 'id state mode fixture_id invariant_version cancel_requested created_at updated_at') | {'fault': json.loads(run['fault_json'])},
                'purchase': select(purchase, 'id run_id amount currency order_id payment_state payment_confirmed capture_id capture_completed_at created_at updated_at'),
                'operations': ops, 'events': events, 'tickets': tickets}


def local_probe(base, path, body, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = Request(base + path, headers=headers, method='POST' if body is not None else 'GET',
                      data=json.dumps(body).encode() if body is not None else None)
    result = {'observed_at': now(), 'method': request.method, 'path': path, 'body': body, 'authenticated': bool(token)}
    try:
        with build_opener(_NoRedirects()).open(request, timeout=15) as response:
            result['http_status'], raw = response.status, response.read(4096)
    except HTTPError as exc:
        result['http_status'], raw = exc.code, exc.read(4096)
        exc.close()
    except (URLError, OSError):
        return result | {'result': 'BLOCKED', 'error': 'Local HTTP transport failed'}
    payload = json.loads(raw)
    result['response'] = select(payload, 'error')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--order-id', required=True)
    parser.add_argument('--capture-id', required=True)
    parser.add_argument('--ticket-id', required=True)
    parser.add_argument('--db', default='var/crashcart.sqlite3')
    parser.add_argument('--source-snapshot', default='evidence/snapshots/core-v4')
    parser.add_argument('--output', required=True)
    parser.add_argument('--provider-read', action='store_true')
    parser.add_argument('--http-probes', action='store_true')
    args = parser.parse_args()
    load_env(ROOT / '.env')
    output = (ROOT / args.output).resolve()
    output.relative_to(ROOT / 'evidence/runs/paypal-live')
    if output.exists():
        raise SystemExit('Refusing to overwrite existing evidence')
    db_path = (ROOT / args.db).resolve()
    db_path.relative_to(ROOT)
    snapshot = (ROOT / args.source_snapshot).resolve()
    snapshot.relative_to(ROOT / 'evidence/snapshots')
    manifest = json.loads((snapshot / 'manifest.json').read_text())
    source_names = ['crashcart/paypal.py', 'crashcart/service.py', 'crashcart/store.py', 'crashcart/server.py', 'crashcart/invariant.py', 'migrations/001_initial.sql']
    sources = {name: sha((ROOT / name).read_bytes()) for name in source_names}
    assert all(value == manifest[name] == sha((snapshot / name).read_bytes()) for name, value in sources.items()), 'Source differs from named snapshot'
    ui_context = {'frozen_path': args.source_snapshot + '/web/app.js', 'frozen_sha256': manifest['web/app.js'], 'current_sha256': sha((ROOT / 'web/app.js').read_bytes()), 'claim': 'This verifier exercises backend records and HTTP only; it does not establish current browser UI behavior.'}
    before = read_records(db_path, args.run_id)
    purchase = before['purchase']
    assert (purchase['order_id'], purchase['capture_id']) == (args.order_id, args.capture_id)
    assert before['run']['mode'] == 'LIVE_SANDBOX' and before['run']['fault'] == {'kind': 'none', 'merchant': 'healthy'}
    assert [t['id'] for t in before['tickets']] == [args.ticket_id]
    checks = []
    def check(name, passed):
        checks.append({'name': name, 'passed': bool(passed)})
    events = before['events']
    by_kind = lambda kind: [e for e in events if e['event_type'] == kind]
    ops = {o['semantic_key']: o for o in before['operations']}
    check('Exactly one create and one capture operation with distinct durable request IDs', len(ops) == len(before['operations']) == 2 and set(ops) == {'order.create', 'order.capture'} and len({o['request_id'] for o in ops.values()}) == 2)
    unit = ops['order.create']['body']['purchase_units'][0]
    check('Server journal fixes USD29 and both logical purchase references', unit['amount'] == {'currency_code': 'USD', 'value': '29.00'} and unit['reference_id'] == unit['custom_id'] == purchase['id'])
    check('Order is recorded before capture operation', ops['order.create']['created_at'] < by_kind('order_created')[0]['observed_at'] < ops['order.capture']['created_at'])
    check('Capture followed independent APPROVED provider state', by_kind('pre_capture_read')[0]['payload']['status'] == 'APPROVED' and by_kind('pre_capture_read')[0]['observed_at'] < by_kind('capture_transport_response')[0]['observed_at'])
    for entry in by_kind('capture_transport_response') + by_kind('independent_order_read'):
        valid = validate_capture(entry['payload'], args.order_id, purchase['id'])
        check('Correlated completed USD29 capture: ' + entry['id'], valid['capture_id'] == args.capture_id and valid['amount'] == 2900 and valid['currency'] == 'USD')
    entitlement_reads = by_kind('entitlement_read')
    check('Repeated fulfillment returns same single ticket before and after reconciliation', len(entitlement_reads) >= 2 and len(by_kind('ticket_fulfilled')) >= 2 and all(e['payload']['ticket_count'] == 1 and [t['id'] for t in e['payload']['tickets']] == [args.ticket_id] for e in entitlement_reads) and all(e['payload']['id'] == args.ticket_id for e in by_kind('ticket_fulfilled')))
    capture_time = datetime.fromisoformat(purchase['capture_completed_at'].replace('Z', '+00:00'))
    ticket_time = datetime.fromisoformat(before['tickets'][0]['created_at'].replace('Z', '+00:00'))
    elapsed = (ticket_time - capture_time).total_seconds()
    check('Healthy ticket issued within fixed60-second capture deadline', 0 <= elapsed <= 60)
    browser = by_kind('customer_observation')
    check('Cancellation observation precedes actual approval return and capture', any(e['payload']['action'] == 'buyer_cancelled' and e['observed_at'] < by_kind('pre_capture_read')[0]['observed_at'] for e in browser) and any(e['payload']['action'] == 'buyer_returned' and e['observed_at'] < by_kind('pre_capture_read')[0]['observed_at'] for e in browser))
    report = {'format': 'crashcart-live-record-verification-v1', 'mode': 'LIVE_SANDBOX', 'executed_at': now(), 'source_snapshot': args.source_snapshot, 'source_hashes': sources, 'ui_context': ui_context, 'verifier_sha256': sha(Path(__file__).read_bytes()), 'environment': {'python': sys.version.split()[0], 'database': args.db, 'transport': 'actual PayPalSandbox urllib; no injected transport'}, 'records_before': before, 'capture_to_ticket_seconds': elapsed, 'checks': checks, 'limits': ['Local operator browser is not a KERNEL session.', 'Stored browser observations require the accompanying operator browser evidence; this extractor did not operate that browser.', 'Earlier provider HTTP401 is operator-reported; persisted order_unresolved retains only PROVIDER_HTTP_ERROR. The new unauthenticated local401 probe is distinct.', 'No webhook, model, recorded-replay, or fresh-repair claim.']}
    if args.provider_read:
        started = time.monotonic()
        try:
            fresh = PayPalSandbox().get_order(args.order_id)
            payment = validate_capture(fresh, args.order_id, purchase['id'])
            report['independent_provider_read'] = {'method': 'GET', 'endpoint': 'https://api-m.sandbox.paypal.com/v2/checkout/orders/' + args.order_id, 'observed_at': now(), 'elapsed_seconds': round(time.monotonic() - started, 6), 'result': 'PASS', 'order': fresh}
            check('Separate verifier provider GET confirms original capture', payment['capture_id'] == args.capture_id)
        except PayPalError as exc:
            report['independent_provider_read'] = {'method': 'GET', 'observed_at': now(), 'result': 'BLOCKED', **exc.as_dict()}
            check('Separate verifier provider GET confirms original capture', False)
    if args.http_probes:
        base = 'http://127.0.0.1:' + os.environ.get('CRASHCART_PORT', '8765')
        token = os.environ.get('CRASHCART_OPERATOR_TOKEN')
        assert token, 'Operator token is missing'
        probes = [local_probe(base, '/api/runs/' + args.run_id, None), local_probe(base, '/api/runs/' + args.run_id + '/order', {'amount': '0.01'}, token), local_probe(base, '/api/runs/' + args.run_id + '/order', {'currency': 'EUR'}, token)]
        report['http_negative_probes'] = {'base': base, 'results': probes}
        check('Unauthenticated local read is rejected', probes[0].get('http_status') == 401)
        for probe in probes[1:]:
            check('Client-owned ' + next(iter(probe['body'])) + ' rejected before payment action', probe.get('http_status') == 400 and probe.get('response', {}).get('error') == 'Order accepts no client price or currency; merchant price is fixed')
    after = read_records(db_path, args.run_id)
    report['records_after'] = {'observed_at': after['observed_at'], 'purchase': after['purchase'], 'operations': after['operations'], 'tickets': after['tickets'], 'event_ids': [e['id'] for e in after['events']]}
    check('Read-only verification and rejected requests preserve journal and entitlement', before['purchase'] == after['purchase'] and before['operations'] == after['operations'] and before['tickets'] == after['tickets'])
    report['result'] = 'PASS' if all(c['passed'] for c in checks) else 'FAIL'
    encoded = json.dumps(report, indent=2) + '\n'
    assert not re.search(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', encoded, re.I), 'Email-like content rejected from evidence'
    for name in ('PAYPAL_CLIENT_ID', 'PAYPAL_CLIENT_SECRET', 'CRASHCART_OPERATOR_TOKEN'):
        secret = os.environ.get(name)
        assert not secret or secret not in encoded, 'Credential rejected from evidence'
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x') as file:
        file.write(encoded)
    print(json.dumps({'result': report['result'], 'passed': sum(c['passed'] for c in checks), 'checks': len(checks), 'artifact': str(output.relative_to(ROOT)), 'sha256': sha(output.read_bytes())}))
    return 0 if report['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
