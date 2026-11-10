"""Public motion assets stay self-hosted, bounded and correctly served."""
import hashlib
from http.client import HTTPConnection
from pathlib import Path
import tempfile
import threading
import unittest

from crashcart import judge


class JudgeMotionAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = judge.prepare_review()

    def test_vendored_versions_and_original_notices_are_retained(self):
        for name in ('assets/vendor/gsap.min.js', 'assets/vendor/ScrollTrigger.min.js'):
            body = self.files[name][1]
            self.assertIn(b'3.15.1', body[:300])
            self.assertIn(b'Copyright 2026, GreenSock', body[:500])
            self.assertIn(b'https://gsap.com/standard-license', body[:500])
        self.assertIn(b'GRANT OF LICENSE', self.files['assets/vendor/GSAP-LICENSE.txt'][1])
        for name in ('INSTRUMENT-SERIF-OFL.txt', 'MANROPE-OFL.txt'):
            self.assertIn(b'SIL OPEN FONT LICENSE', self.files['assets/fonts/' + name][1])

    def test_fonts_media_and_total_asset_budget(self):
        for name in ('instrument-serif-latin.woff2', 'manrope-latin.woff2'):
            content_type, body = self.files['assets/fonts/' + name]
            self.assertEqual(content_type, 'font/woff2')
            self.assertEqual(body[:4], b'wOF2')
        self.assertNotIn(b'https://', self.files['assets/fonts.css'][1])
        for name in ('delivery-timing.webp', 'payment-evidence.webp'):
            content_type, body = self.files['assets/media/' + name]
            self.assertEqual(content_type, 'image/webp')
            self.assertEqual(body[:4], b'RIFF')
            self.assertEqual(body[8:12], b'WEBP')
        self.assertLess(sum(len(self.files[name][1]) for name in judge.ASSETS), 1_500_000)

    def test_binary_assets_export_without_packages_or_byte_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'export'
            receipt = judge.export_site(target)
            for name in judge.ASSETS:
                original = (judge.ROOT / 'web/judge' / name).read_bytes()
                self.assertEqual((target / name).read_bytes(), original, name)
                self.assertEqual(receipt['sha256'][name], hashlib.sha256(original).hexdigest())

    def test_local_server_mimes_and_policy_allow_only_self_hosted_fonts(self):
        server = judge.make_server(self.files, port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for name, expected in (
                ('assets/fonts/manrope-latin.woff2', 'font/woff2'),
                ('assets/media/payment-evidence.webp', 'image/webp'),
                ('assets/vendor/gsap.min.js', 'text/javascript; charset=utf-8'),
                ('assets/vendor/GSAP-LICENSE.txt', 'text/plain; charset=utf-8'),
            ):
                connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                try:
                    connection.request('GET', '/' + name)
                    response = connection.getresponse()
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.getheader('Content-Type'), expected)
                    self.assertEqual(response.read(), self.files[name][1])
                    policy = response.getheader('Content-Security-Policy')
                    self.assertIn("font-src 'self'", policy)
                    self.assertIn("script-src 'self'", policy)
                    self.assertNotIn('unsafe-', policy)
                    self.assertNotIn('*', policy)
                finally:
                    connection.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)
