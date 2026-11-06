import json
import tempfile
import unittest
from pathlib import Path
from crashcart.monitor_store import MonitorStore

T='2026-11-06T00:00:'
def at(seconds):
    from datetime import datetime,timedelta,timezone
    return (datetime(2026,11,6,tzinfo=timezone.utc)+timedelta(seconds=seconds)).isoformat()

class MonitorStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'monitor.sqlite';self.db=MonitorStore(self.path)
        self.a=self.db.create_store('First shop','shopify','first.myshopify.com',60)['id']
        self.b=self.db.create_store('Second shop','woocommerce','https://second.example',120)['id']
    def order(self,store=None,id='order-1',refs=None,status='unfulfilled',fulfilled=None,updated=1,event='order-event',amount=2900,currency='USD'):
        return self.db.upsert_order(store or self.a,id,display_number='#1001',currency=currency,total_minor=amount,payment_references=refs if refs is not None else ['invoice-1'],fulfillment_status=status,fulfilled_at=at(fulfilled) if fulfilled is not None else None,updated_at=at(updated),event_id=event)
    def payment(self,store=None,id='capture-1',reference='invoice-1',completed=0,event='payment-event',amount=2900,currency='USD'):
        return self.db.record_payment(store or self.a,capture_id=id,reference=reference,currency=currency,amount_minor=amount,completed_at=at(completed),event_id=event)
    def test_deadline_boundary_and_one_alert(self):
        self.order();self.payment();self.assertEqual(self.db.scan(at(60)),[])
        alerts=self.db.scan(at(61));self.assertEqual(len(alerts),1);self.assertEqual(alerts[0]['deadline_at'],at(60).replace('+00:00','.000000+00:00'))
        self.assertEqual(self.db.scan(at(120)),[]);self.assertEqual(len(self.db.alerts(self.a)),1)
    def test_restart_replay_cannot_reset_payment_or_deadline(self):
        self.order();self.payment();self.db=MonitorStore(self.path);self.payment(event='new-delivery')
        self.assertEqual(len(self.db.scan(at(61))),1)
        with self.assertRaises(ValueError):self.payment(completed=40,event='different-facts')
        self.assertEqual(self.db.orders(self.a)[0]['paid_at'],at(0).replace('+00:00','.000000+00:00'))
    def test_out_of_order_snapshots_preserve_fulfillment(self):
        self.order(status='fulfilled',fulfilled=30,updated=35,event='new');self.order(updated=10,event='old');self.payment()
        self.assertEqual(self.db.orders(self.a)[0]['fulfillment_status'],'fulfilled');self.assertEqual(self.db.scan(at(100)),[])
    def test_fulfillment_at_deadline_is_on_time(self):
        self.order(status='fulfilled',fulfilled=60,updated=60);self.payment();self.assertEqual(self.db.scan(at(100)),[])
    def test_late_fulfillment_before_scan_preserves_breach(self):
        self.order(status='fulfilled',fulfilled=61,updated=62);self.payment()
        alert=self.db.scan(at(100))[0];self.assertIsNotNone(alert['resolved_at']);self.assertEqual(len(self.db.alerts(self.a)),1)
    def test_later_resolution_and_ack_do_not_erase_alert(self):
        self.order();self.payment();alert=self.db.scan(at(61))[0]
        first=self.db.acknowledge_alert(self.a,alert['id']);second=self.db.acknowledge_alert(self.a,alert['id']);self.assertEqual(first,second)
        self.order(status='fulfilled',fulfilled=90,updated=91,event='fulfilled');self.assertEqual(self.db.scan(at(92)),[])
        self.assertIsNotNone(self.db.alerts(self.a)[0]['resolved_at']);self.assertIsNotNone(self.db.alerts(self.a)[0]['acknowledged_at'])
    def test_store_scoping_for_ids_payments_and_alert_ack(self):
        self.order();self.order(store=self.b);self.payment()
        self.assertEqual(self.db.orders(self.b)[0]['payment_state'],'unmatched')
        alert=self.db.scan(at(61))[0]
        with self.assertRaises(KeyError):self.db.acknowledge_alert(self.b,alert['id'])
        self.payment(store=self.b);self.assertEqual(self.db.scan(at(121))[0]['store_id'],self.b)
    def test_event_reuse_with_changed_payload_rejected_atomically(self):
        self.order()
        with self.assertRaises(ValueError):self.order(amount=1)
        self.assertEqual(self.db.orders(self.a)[0]['total_minor'],2900)
        self.payment()
        with self.assertRaises(ValueError):self.payment(id='capture-2')
        self.assertEqual(self.db.orders(self.a)[0]['payment_state'],'confirmed')
    def test_duplicate_order_delivery_is_idempotent(self):
        self.assertEqual(self.order(),self.order());self.assertEqual(len(self.db.orders(self.a)),1)
    def test_same_timestamp_conflicting_snapshot_rejected(self):
        self.order()
        with self.assertRaises(ValueError):self.order(amount=100,event='other')
    def test_partial_amount_and_currency_mismatch_never_confirm(self):
        self.order();self.payment(amount=100)
        self.assertEqual(self.db.orders(self.a)[0]['payment_state'],'mismatch');self.assertEqual(self.db.scan(at(1000)),[])
        self.order(store=self.b);self.payment(store=self.b,currency='EUR')
        self.assertEqual(self.db.orders(self.b)[0]['payment_state'],'mismatch')
    def test_unmatched_payment_can_match_later_order(self):
        self.payment();self.assertEqual(self.db.scan(at(61)),[]);self.order()
        self.assertEqual(len(self.db.scan(at(62))),1)
    def test_shared_reference_or_multiple_captures_is_ambiguous(self):
        self.order();self.order(id='order-2',event='second-order');self.payment()
        self.assertTrue(all(o['payment_state']=='ambiguous' for o in self.db.orders(self.a)));self.assertEqual(self.db.scan(at(100)),[])
        self.order(store=self.b);self.payment(store=self.b);self.payment(store=self.b,id='capture-2',event='second-capture')
        self.assertEqual(self.db.orders(self.b)[0]['payment_state'],'ambiguous')
    def test_capture_id_can_be_explicit_order_reference(self):
        self.order(refs=['capture-1']);self.payment(reference='unrelated-order-id');self.assertEqual(self.db.orders(self.a)[0]['payment_state'],'confirmed')
    def test_partial_or_cancelled_order_is_not_fulfilled(self):
        self.order(status='partial');self.payment();self.assertEqual(len(self.db.scan(at(61))),1)
    def test_validation_rejects_naive_time_bool_money_and_invalid_fulfillment(self):
        with self.assertRaises(ValueError):self.db.scan('2026-11-06T00:00:00')
        with self.assertRaises(ValueError):self.order(amount=True)
        with self.assertRaises(ValueError):self.order(status='unfulfilled',fulfilled=1)
        with self.assertRaises(ValueError):self.order(status='fulfilled',fulfilled=10,updated=1)
        with self.assertRaises(ValueError):self.payment(reference='')
        with self.assertRaises(ValueError):self.db.create_store('x','shopify','http://unsafe.example',60)
        with self.assertRaises(KeyError):self.db.orders('not-owned')
    def test_late_arriving_on_time_fulfillment_retracts_alert_after_restart(self):
        self.order();self.payment();original=self.db.scan(at(61))[0]
        self.order(status='fulfilled',fulfilled=30,updated=40,event='late-arrival')
        self.assertEqual(self.db.scan(at(90)),[]);self.db=MonitorStore(self.path)
        alert=self.db.alerts(self.a)[0];self.assertEqual(alert['id'],original['id'])
        self.assertIsNotNone(alert['retracted_at']);self.assertEqual(alert['resolution_reason'],'on_time_fulfillment_received_late')
    def test_order_policy_snapshot_survives_store_change_and_restart(self):
        self.order();self.payment()
        with self.db._db() as db:db.execute('UPDATE monitor_stores SET promise_seconds=3600 WHERE id=?',(self.a,))
        self.order(updated=2,event='new-update');self.db=MonitorStore(self.path)
        self.assertEqual(self.db.orders(self.a)[0]['promise_seconds'],60);self.assertEqual(len(self.db.scan(at(61))),1)
        self.assertEqual(self.order(id='new-order',refs=['new-invoice'],event='new-order')['promise_seconds'],3600)
    def test_woocommerce_basepath_preserved_shopify_path_rejected(self):
        item=self.db.create_store('Subdirectory store','woocommerce','https://SITE.example/Shop/',60)
        self.assertEqual(item['domain'],'site.example/Shop')
        with self.assertRaises(ValueError):self.db.create_store('Shopify','shopify','https://shop.myshopify.com/path',60)
        with self.assertRaises(ValueError):self.db.create_store('Bad','woocommerce','https://site.example/../shop',60)
    def test_fulfilled_unknown_time_never_creates_breach_or_invents_timestamp(self):
        self.order(status='fulfilled',updated=70);self.payment()
        self.assertEqual(self.db.scan(at(100)),[])
        order=self.db.orders(self.a)[0];self.assertIsNone(order['fulfilled_at']);self.assertEqual(order['fulfillment_timing'],'unknown')
    def test_unknown_fulfillment_time_corrects_existing_alert_without_deleting_it(self):
        self.order();self.payment();original=self.db.scan(at(61))[0]
        self.order(status='fulfilled',updated=80,event='unknown-completion');self.db.scan(at(100));self.db=MonitorStore(self.path)
        alert=self.db.alerts(self.a)[0];self.assertEqual(alert['id'],original['id']);self.assertIsNone(alert['resolved_at'])
        self.assertIsNotNone(alert['retracted_at']);self.assertEqual(alert['resolution_reason'],'fulfillment_time_unknown')
    def test_missing_timestamp_update_cannot_erase_known_fulfillment_truth(self):
        self.order(status='fulfilled',fulfilled=90,updated=91);self.payment();self.db.scan(at(100))
        self.order(status='fulfilled',updated=110,event='missing-timestamp');self.db.scan(at(120))
        self.assertEqual(self.db.orders(self.a)[0]['fulfilled_at'],at(90).replace('+00:00','.000000+00:00'))
        self.assertEqual(self.db.alerts(self.a)[0]['resolution_reason'],'fulfilled_after_deadline')
    def test_late_timing_evidence_can_resolve_previously_unknown_alert(self):
        self.order();self.payment();original=self.db.scan(at(61))[0]
        self.order(status='fulfilled',updated=80,event='unknown');self.db.scan(at(81))
        self.order(status='fulfilled',fulfilled=90,updated=91,event='known-late');self.db.scan(at(100))
        alert=self.db.alerts(self.a)[0];self.assertEqual(alert['id'],original['id'])
        self.assertIsNone(alert['retracted_at']);self.assertEqual(alert['resolution_reason'],'fulfilled_after_deadline')
    def test_corrected_payment_matching_retracts_existing_alert_and_restores_original_deadline(self):
        cases=[('unmatched',{'refs':['different-invoice']}),('mismatch',{'amount':3000}),('mismatch',{'currency':'EUR'}),('ambiguous',{})]
        for index,(expected,changes) in enumerate(cases):
            with self.subTest(state=expected,changes=changes):
                store=self.db.create_store('Case '+str(index),'shopify',f'case{index}.myshopify.com',60)['id']
                self.order(store=store);self.payment(store=store)
                original=self.db.scan(at(61))[-1]
                if expected=='ambiguous':self.order(store=store,id='other-order',updated=62,event='shared-reference')
                else:self.order(store=store,updated=62,event='correction',**changes)
                self.assertEqual(self.db.orders(store)[0]['payment_state'],expected)
                self.db.scan(at(63));self.db=MonitorStore(self.path)
                alert=next(a for a in self.db.alerts(store) if a['id']==original['id'])
                self.assertIsNotNone(alert['retracted_at']);self.assertEqual(alert['resolution_reason'],'payment_match_uncertain')
                self.assertEqual(alert['deadline_at'],original['deadline_at'])
                if expected=='ambiguous':self.order(store=store,id='other-order',refs=['unrelated'],updated=64,event='unshare-reference')
                else:self.order(store=store,updated=64,event='restored')
                self.db.scan(at(65));self.db=MonitorStore(self.path)
                restored=next(a for a in self.db.alerts(store) if a['id']==original['id'])
                self.assertIsNone(restored['retracted_at']);self.assertIsNone(restored['resolution_reason'])
                self.assertEqual(restored['deadline_at'],original['deadline_at']);self.assertEqual(restored['detected_at'],original['detected_at'])
    def test_restored_match_resolves_retained_alert_when_completion_was_on_time(self):
        self.order();self.payment();original=self.db.scan(at(61))[0]
        self.order(refs=['wrong-invoice'],status='fulfilled',fulfilled=30,updated=62,event='uncertain')
        self.db.scan(at(63));self.assertEqual(self.db.alerts(self.a)[0]['resolution_reason'],'payment_match_uncertain')
        self.order(status='fulfilled',fulfilled=30,updated=64,event='restored-match');self.db.scan(at(65))
        alert=self.db.alerts(self.a)[0];self.assertEqual(alert['id'],original['id'])
        self.assertEqual(alert['resolution_reason'],'on_time_fulfillment_received_late');self.assertIsNotNone(alert['retracted_at'])
        self.assertEqual(alert['deadline_at'],original['deadline_at'])
    def test_direct_capture_switch_cannot_reanchor_deadline_and_original_can_be_restored(self):
        self.order();self.payment();original=self.db.scan(at(61))[0]
        self.payment(id='capture-2',reference='invoice-2',completed=70,event='later-payment')
        switched=self.order(refs=['invoice-2'],updated=80,event='switch-payment')
        self.assertEqual(switched['payment_state'],'ambiguous');self.assertIsNone(switched['deadline_at'])
        self.assertEqual(self.db.scan(at(81)),[]);self.db=MonitorStore(self.path)
        self.assertEqual(self.db.orders(self.a)[0]['payment_state'],'ambiguous')
        alert=self.db.alerts(self.a)[0];self.assertEqual(alert['id'],original['id'])
        self.assertEqual(alert['resolution_reason'],'payment_match_uncertain');self.assertEqual(alert['deadline_at'],original['deadline_at'])
        self.order(updated=90,event='restore-original');self.db.scan(at(91));self.db=MonitorStore(self.path)
        restored=self.db.orders(self.a)[0];self.assertEqual(restored['capture_id'],'capture-1')
        self.assertEqual(restored['deadline_at'],original['deadline_at']);self.assertIsNone(self.db.alerts(self.a)[0]['retracted_at'])
        self.assertEqual(self.db.alerts(self.a)[0]['id'],original['id'])
    def test_first_confirmation_is_bound_before_any_external_order_read(self):
        self.order();self.payment()
        self.payment(id='capture-2',reference='invoice-2',completed=20,event='second')
        order=self.order(refs=['capture-2'],updated=30,event='direct-switch')
        self.assertEqual(order['payment_state'],'ambiguous')
    def test_binding_upgrade_preserves_existing_alert_clock_over_current_changed_reference(self):
        self.order();self.payment();original=self.db.scan(at(61))[0]
        self.payment(id='capture-2',reference='invoice-2',completed=70,event='later')
        self.order(refs=['invoice-2'],updated=80,event='switch')
        with self.db._db() as db:db.execute('DROP TABLE monitor_associations')
        self.db=MonitorStore(self.path)
        self.assertEqual(self.db.orders(self.a)[0]['payment_state'],'ambiguous')
        self.db.scan(at(90));self.assertEqual(self.db.alerts(self.a)[0]['deadline_at'],original['deadline_at'])
    def test_shopify_rejects_custom_domains_paths_and_ports_without_saving(self):
        before=len(self.db.list_stores())
        for address in ['https://wrong-shop.example.test','wrong-shop.example.test','https://shop.myshopify.com/products','https://shop.myshopify.com:8443','https://shop.myshopify.com:bad','https://shop.myshopify.com:','https://user@shop.myshopify.com','https://shop.myshopify.com?x=1','https://shop.myshopify.com#section','http://shop.myshopify.com','https://a.b.myshopify.com']:
            with self.subTest(address=address),self.assertRaisesRegex(ValueError,'myshopify.com'):
                self.db.create_store('Shopify','shopify',address,60)
        self.assertEqual(len(self.db.list_stores()),before)
    def test_shopify_normalizes_canonical_case_and_default_https_port(self):
        for address in ['shop.myshopify.com','https://SHOP.MyShopify.COM/','https://SHOP.myshopify.com:443/']:
            with self.subTest(address=address):
                item=self.db.create_store('Shopify','shopify',address,60)
                self.assertEqual(item['domain'],'shop.myshopify.com')
    def test_facts_and_private_storage_are_explicit(self):
        self.order();p=self.payment();self.assertEqual(p['verified_by'],'paypal_signature_verifier_caller')
        self.assertIn('not_physical_delivery',self.db.orders(self.a)[0]['fulfillment_basis']);self.assertEqual(self.path.stat().st_mode&0o777,0o600)

if __name__=='__main__':unittest.main()
