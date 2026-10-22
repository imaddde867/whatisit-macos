import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'tests'))

import build_verified_dataset as builder
from v4_campaign import Campaign


class ContestedControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.campaign = Campaign(self.root)
        self.control = self.campaign.control_key('ct0002')
        self.pass1 = self.campaign.write_pass1(overrides={self.control: 'correct'})
        self.adjudication = self.root / 'adjudication.json'

    def write_adjudication(self, keys=None, digest=None):
        record = {
            'revision': 'test',
            'inputs_sha256': {
                'controls-map.json': digest or builder.sha256_file(
                    self.campaign.pool / 'controls-map.json')},
            'contested_keys': [self.control] if keys is None else keys,
        }
        self.adjudication.write_text(json.dumps(record) + '\n')

    def build(self, out='out', **kwargs):
        kwargs.setdefault('sample', 1.0)
        kwargs.setdefault('seed', 13)
        return self.campaign.build_verified(self.root / out, **kwargs)

    def test_flipped_control_fails_without_adjudication(self):
        with self.assertRaisesRegex(ValueError, 'control .*expected'):
            self.campaign.make_confirm(sample=1.0, seed=13)

    def test_contested_control_is_exempt_but_required(self):
        self.write_adjudication()
        self.campaign.make_confirm(sample=1.0, seed=13, adjudication=self.adjudication)
        self.campaign.write_pass2()
        manifest = self.build(adjudication=self.adjudication)
        self.assertEqual(manifest['control_adjudication']['contested_keys'], [self.control])
        self.assertIsNotNone(manifest['control_adjudication']['sha256'])
        self.assertGreater(manifest['rows'], 0)

    def test_contested_control_without_a_verdict_still_fails(self):
        for path in self.campaign.verdict_dir.glob('b*.json'):
            data = json.loads(path.read_text())
            data['cases'] = [case for case in data['cases']
                             if self.control not in {entry['key'] for entry in case['verdicts']}]
            path.write_text(json.dumps(data) + '\n')
        with self.assertRaises(ValueError):
            builder.load_verdicts(self.campaign.verdict_dir, self.campaign.pool_batches,
                                  keymap=self.campaign.keymap,
                                  controls=self.campaign.controls_map,
                                  require_keys=set(self.campaign.keymap)
                                  | set(self.campaign.controls_map),
                                  contested={self.control})

    def test_stale_or_misplaced_adjudication_is_rejected(self):
        self.write_adjudication(digest='0' * 64)
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.campaign.make_confirm(sample=1.0, seed=13,
                                       adjudication=self.adjudication)

        self.write_adjudication(keys=['knotacontrol00000'])
        with self.assertRaisesRegex(ValueError, 'outside the controls map'):
            self.build(out='out-2', adjudication=self.adjudication)

    def test_confirmation_rejects_a_flipped_control_without_adjudication(self):
        with self.assertRaisesRegex(ValueError, 'control .*expected'):
            self.campaign.make_confirm(sample=1.0, seed=13)


if __name__ == '__main__':
    unittest.main()
