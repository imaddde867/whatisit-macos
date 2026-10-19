import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(TESTS.parents[0] / 'tools'))

import build_verified_dataset as builder
import make_v4_confirm
from v4_campaign import Campaign, tree_bytes


class ConfirmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.campaign = Campaign(self.root)
        self.campaign.write_pass1(overrides={
            self.campaign.key('r00003', 'uname -a'): 'incorrect',
            self.campaign.key('r00009', 'whoami'): 'incorrect',
            self.campaign.key('r00006', 'ls -lt'): 'incorrect',
        })

    def confirm(self, out='confirm', **kwargs):
        return self.campaign.make_confirm(self.root / out, **kwargs)

    def test_selection_and_sample_one_keep_every_selected_label(self):
        out = self.root / 'confirm'
        manifest = self.confirm(sample=1.0, seed=13, batch_size=90)
        self.assertEqual(manifest['selected_total'], 11)
        self.assertEqual(manifest['sampled'], 11)
        self.assertEqual(manifest['sample'], 1.0)
        self.assertEqual(manifest['seed'], 13)
        self.assertEqual(manifest['batch_size'], 90)
        self.assertEqual([entry['rid'] for entry in manifest['selected']],
                         ['r00001', 'r00004', 'r00005', 'r00006', 'r00007', 'r00008',
                          'r00010', 'r00011', 'r00012', 'r00013', 'r00014'])
        self.assertEqual(sorted(manifest['selected'], key=lambda item: item['case']),
                         manifest['sample_cases'])
        batch = json.loads((out / 'b00.json').read_text())
        self.assertEqual(len(batch['items']), 11)
        for item in batch['items']:
            self.assertEqual(set(item), {'case', 'request', 'candidates'})
            for candidate in item['candidates']:
                self.assertEqual(set(candidate), {'key', 'command'})
        expected_cases = {entry['case'] for entry in manifest['selected']}
        self.assertEqual({item['case'] for item in batch['items']}, expected_cases)
        control_cases = {entry['case'] for entry in self.campaign.controls_map.values()}
        self.assertTrue(all(entry['case'] not in control_cases
                            for entry in manifest['selected']))
        self.assertFalse((out / 'controls-map.json').exists())

    def test_v3_path_request_gets_explicit_inputs_line(self):
        manifest = self.confirm(sample=1.0, seed=13)
        batch = json.loads((self.root / 'confirm/b00.json').read_text())
        item = next(item for item in batch['items']
                    if item['case'] == self.campaign.case('r00001'))
        self.assertEqual(item['request'],
                         'Show the Working  Directory\n'
                         'Explicit inputs: {"path": "notes/report.txt"}')
        self.assertIn({'case': self.campaign.case('r00001'), 'rid': 'r00001',
                       'group': 'v3_kept',
                       'keys': [self.campaign.key('r00001', 'echo one')]},
                      manifest['sample_cases'])

    def test_twenty_percent_sample_is_exact_and_seeded(self):
        manifest = self.confirm(sample=0.2, seed=13)
        self.assertEqual(manifest['selected_total'], 11)
        self.assertEqual(manifest['sampled'], 2)
        expected = random.Random(13).sample(manifest['selected'], 2)
        expected.sort(key=lambda item: item['case'])
        self.assertEqual(manifest['sample_cases'], expected)
        batch = json.loads((self.root / 'confirm/b00.json').read_text())
        self.assertEqual([item['case'] for item in batch['items']],
                         [item['case'] for item in expected])
        self.assertLess(len(batch['items']), manifest['selected_total'])

    def test_confirm_items_match_pool_items_exactly(self):
        self.confirm(sample=1.0, seed=13)
        pool = {}
        for batch in self.campaign.pool_batches.values():
            pool.update({item['case']: item for item in batch['items']})
        confirm = json.loads((self.root / 'confirm/b00.json').read_text())
        for item in confirm['items']:
            self.assertEqual(item, pool[item['case']])

    def test_empty_sample_fails_closed(self):
        keymap = self.campaign.keymap
        chosen = self.campaign.key('r00001', 'echo one')
        self.campaign.write_pass1(overrides={
            key: 'incorrect' for key in keymap if key != chosen})
        with self.assertRaisesRegex(ValueError, 'confirmation sample is empty'):
            self.confirm(sample=0.2, seed=13)

    def test_no_selected_labels_fails_closed(self):
        self.campaign.write_pass1(overrides={key: 'incorrect'
                                            for key in self.campaign.keymap})
        with self.assertRaisesRegex(ValueError, 'no selected labels to confirm'):
            self.confirm(sample=1.0, seed=13)

    def test_stale_raw_samples_are_rejected(self):
        path = self.root / 'data/teacher/roihu_full_raw_samples.jsonl'
        path.write_text(path.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'raw_samples changed since the pool was built'):
            self.confirm(sample=1.0, seed=13)

    def test_candidate_frequency_drift_is_rejected(self):
        raw_path = self.root / 'data/teacher/roihu_full_raw_samples.jsonl'
        raw = [json.loads(line) for line in raw_path.read_text().splitlines()]
        row = next(row for row in raw if row['id'] == 'r00006')
        row['samples'] = [{'cmd': 'ls -lS'}, {'cmd': 'ls -lS'}, {'cmd': 'ls -lS'},
                          {'cmd': 'ls -lt'}]
        raw_path.write_text(''.join(json.dumps(row) + '\n' for row in raw))
        manifest_path = self.campaign.pool / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['inputs_sha256']['raw_samples'] = builder.sha256_file(raw_path)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        with self.assertRaisesRegex(ValueError, 'frequency changed'):
            self.confirm(sample=1.0, seed=13)

    def test_keymap_must_match_the_pool(self):
        path = self.root / 'other-keymap.json'
        keymap = json.loads(json.dumps(self.campaign.keymap))
        next(iter(keymap.values()))['rid'] = 'r99999'
        path.write_text(json.dumps(keymap))
        with self.assertRaisesRegex(ValueError, 'keymap does not match the pool keymap'):
            make_v4_confirm.build_confirm(
                path, self.root / 'data/teacher/roihu_full_raw_samples.jsonl',
                self.root / 'data/distill/stage2-v3/requests.jsonl',
                self.campaign.verdict_dir, self.root / 'confirm',
                effective=lambda sample, request: sample['cmd'],
                pool_dir=self.campaign.pool)

    def test_pool_artifact_tamper_is_rejected(self):
        path = self.campaign.pool / 'batches/b00.json'
        path.write_text(path.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'pool artifacts do not match'):
            self.confirm(sample=1.0, seed=13)

    def test_pool_without_controls_is_rejected(self):
        path = self.campaign.pool / 'manifest.json'
        manifest = json.loads(path.read_text())
        manifest['counts']['controls_total'] = 0
        manifest['counts']['controls_injected'] = 0
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        with self.assertRaisesRegex(ValueError, 'pool has no controls'):
            self.confirm(sample=1.0, seed=13)

    def test_deterministic_rerun_and_hashes(self):
        first = self.root / 'confirm1'
        second = self.root / 'confirm2'
        manifest1 = self.confirm(out=first.name, sample=0.2, seed=13)
        manifest2 = self.confirm(out=second.name, sample=0.2, seed=13)
        self.assertEqual(manifest1, manifest2)
        self.assertEqual(tree_bytes(first), tree_bytes(second))
        self.assertEqual(set(manifest1['inputs_sha256']), {
            'pool_manifest', 'keymap', 'raw_samples', 'v3_requests', 'pass1_verdicts',
            'pass1_verdict_files', 'quarantine_ids', 'roihu_full_quarantine_ids'})
        for name in ('quarantine_ids', 'roihu_full_quarantine_ids'):
            self.assertEqual(manifest1['inputs_sha256'][name],
                             builder.sha256_file(self.root / f'data/distill/{name}.txt'))
        for name, digest in manifest1['artifacts_sha256'].items():
            self.assertEqual(digest, builder.sha256_file(first / f'{name}.json'))

    def test_nonempty_output_directory_fails(self):
        out = self.root / 'confirm-nonempty'
        out.mkdir()
        (out / 'stale.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'not empty'):
            self.confirm(out=out.name, sample=1.0, seed=13)


if __name__ == '__main__':
    unittest.main()
