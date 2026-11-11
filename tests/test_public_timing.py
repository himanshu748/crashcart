"""The actual MIT Scheduler stays keyless, self-hosted and isolated from private tooling."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from crashcart import judge
from crashcart.public_assets import TIMING_ASSETS


class PublicTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = judge.prepare_review()

    def test_public_assets_have_exact_vendor_hashes_and_mit_notice(self):
        prefix = 'assets/vendor/bryntum/'
        manifest = json.loads(self.files[prefix + 'manifest.json'][1])
        self.assertEqual(manifest['version'], '8.0.0-beta.1')
        self.assertEqual(manifest['license'], 'MIT')
        self.assertIn(b'Copyright (c) 2009-2026 Bryntum', self.files[prefix + 'LICENSE.txt'][1])
        for name, row in manifest['files'].items():
            raw = self.files[prefix + name][1]
            self.assertEqual(len(raw), row['bytes'])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row['sha256'])
        self.assertLess(sum(len(self.files[n][1]) for n in TIMING_ASSETS), 4_000_000)

    def test_static_export_includes_the_actual_chart_without_private_api_or_licence(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'public'
            judge.export_site(target)
            for name in TIMING_ASSETS:
                self.assertEqual((target / name).read_bytes(), self.files[name][1])
        bundle = self.files['assets/vendor/bryntum/timing.js'][1]
        self.assertFalse(b'/api/runs' in bundle, 'Public timing must exclude private API code')
        self.assertFalse(b'AG_STUDIO_LICENSE_KEY' in bundle, 'No Studio licence code in public timing')
        page = self.files['timing.html'][1]
        self.assertIn(b'Bryntum Community Scheduler', page)
        self.assertIn(b'8 November', page)
        self.assertNotIn(b'unsafe-inline', page)
        self.assertNotIn(b'/studio/', page)
