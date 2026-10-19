import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_v4_pool

OPAQUE_CASE = re.compile(r'^c[0-9a-f]{12}$')
OPAQUE_KEY = re.compile(r'^k[0-9a-f]{12}$')


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


def stub_effective(sample, request):
    return sample['cmd']


def stub_validate(rid, command, request):
    return None


def tree_bytes(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in sorted(root.rglob('*')) if path.is_file()}


def controls(positives, negatives, start=1):
    rows = []
    for index in range(positives + negatives):
        expected = 'correct' if index < positives else 'incorrect'
        number = start + index
        rows.append({'key': f'ct{number:04d}', 'case': f'CTL-{number:02d}',
                     'request': f'Control request {number}.',
                     'command': f'ctl-{number} -{index}',
                     'expected': expected,
                     'source': f'docs/eval-audit/items.json#x{number:04d}',
                     'provenance': f'fixture pass2 r{index}.json correct'})
    return rows


CONTROLS = controls(3, 3)


class PoolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        write_jsonl(self.root / 'corpus.jsonl', [
            {'id': 'r00001', 'request': 'Corpus one.'},
            {'id': 'r00002', 'request': 'Corpus two.'},
            {'id': 'r00003', 'request': 'Corpus three (corpus copy).'},
            {'id': 'r00004', 'request': 'Corpus four.'},
            {'id': 'r00005', 'request': 'Corpus five.'},
        ])
        write_jsonl(self.root / 'raw.jsonl', [
            {'id': 'r00003', 'request': 'Raw three.', 'samples': [
                {'cmd': 'z -1'}, {'cmd': None}, {'cmd': 'a -2'}, {'cmd': 'a -2'}]},
            {'id': 'r00004', 'request': 'Raw four.', 'samples': [{'cmd': None}]},
            {'id': 'r00005', 'request': 'Raw five.', 'samples': [
                {'cmd': 'd -5'}, {'cmd': 'b -5'}]},
        ])
        write_jsonl(self.root / 'v3' / 'train.jsonl', [
            {'id': 'r00001', 'messages': [{'content': 'x'}, {'content': 'echo one'}]},
            {'id': 'r00002', 'messages': [{'content': 'x'}, {'content': ''}]},
        ])
        write_jsonl(self.root / 'v3' / 'requests.jsonl', [
            {'id': 'r00001', 'request': 'V3 request one.', 'path': 'docs/report.pdf'},
            {'id': 'r00002', 'request': 'V3 request two.'},
        ])
        write_jsonl(self.root / 'controls.jsonl', CONTROLS)

    def build(self, out_dir, **kwargs):
        kwargs.setdefault('batch_size', 1)
        kwargs.setdefault('effective', stub_effective)
        kwargs.setdefault('validate', stub_validate)
        return build_v4_pool.build_pool(
            self.root / 'corpus.jsonl', self.root / 'raw.jsonl', self.root / 'v3',
            Path(out_dir), **kwargs)

    def test_keymap_and_batches_without_controls(self):
        out = self.root / 'out'
        manifest = self.build(out, batch_size=2)
        keymap = json.loads((out / 'keymap.json').read_text())
        self.assertEqual(len(keymap), 5)
        for key, entry in keymap.items():
            self.assertRegex(key, OPAQUE_KEY)
            self.assertRegex(entry['case'], OPAQUE_CASE)
            self.assertEqual(set(entry), {'case', 'group', 'rid', 'command', 'count'})
        by_rid = {}
        for key, entry in keymap.items():
            by_rid.setdefault(entry['rid'], []).append(entry['command'])
        self.assertEqual(by_rid['r00001'], ['echo one'])
        self.assertEqual(sorted(by_rid['r00003']), ['a -2', 'z -1'])
        self.assertEqual(sorted(by_rid['r00005']), ['b -5', 'd -5'])
        self.assertEqual(keymap[next(key for key, entry in keymap.items()
                                   if entry['rid'] == 'r00003' and entry['command'] == 'a -2')]['count'], 2)
        self.assertEqual(keymap[next(key for key, entry in keymap.items()
                                   if entry['rid'] == 'r00003' and entry['command'] == 'z -1')]['count'], 1)
        self.assertEqual([item['case'] for item in json.loads(
            (out / 'batches' / 'b00.json').read_text())['items']],
            [keymap[next(key for key in keymap if keymap[key]['rid'] == 'r00001')]['case'],
             keymap[next(key for key in keymap if keymap[key]['rid'] == 'r00003')]['case']])
        self.assertFalse((out / 'controls-map.json').exists())
        self.assertTrue((out / 'director-map.json').exists())
        self.assertEqual(manifest['counts']['controls_total'], 0)
        self.assertEqual(manifest['counts']['controls_injected'], 0)
        self.assertEqual(set(manifest['inputs_sha256']),
                         {'corpus', 'raw_samples', 'v3_train', 'v3_requests'})
        self.assertEqual(set(manifest['artifacts_sha256']),
                         {'keymap', 'director_map', 'batches'})

    def test_v3_path_item_carries_explicit_inputs_line(self):
        out = self.root / 'out'
        self.build(out, batch_size=90)
        batch = json.loads((out / 'batches' / 'b00.json').read_text())
        requests = {item['case']: item['request'] for item in batch['items']}
        self.assertIn('V3 request one.\nExplicit inputs: {"path": "docs/report.pdf"}',
                      requests.values())
        self.assertNotIn('Explicit inputs', requests[
            next(case for case, entry in ((item['case'], item) for item in batch['items'])
                 if entry['request'] == 'Raw three.')])

    def test_controls_are_opaque_mixed_and_interleaved(self):
        out = self.root / 'out'
        manifest = self.build(out, controls_path=self.root / 'controls.jsonl',
                              controls_per_batch=3, control_seed=13)
        controls_map = json.loads((out / 'controls-map.json').read_text())
        director = json.loads((out / 'director-map.json').read_text())
        self.assertEqual(len(controls_map), len(CONTROLS))
        self.assertEqual(manifest['counts']['controls_injected'], len(CONTROLS))
        self.assertEqual(manifest['counts']['controls_total'], len(CONTROLS))
        self.assertEqual(manifest['counts']['controls_correct'], 3)
        self.assertEqual(manifest['counts']['controls_incorrect'], 3)
        self.assertEqual(set(controls_map), set(director[case]['candidates'][0]['key']
                                                for case in director
                                                if director[case]['kind'] == 'control'))
        seen_cases, seen_keys = set(), set()
        text = ''
        for path in sorted((out / 'batches').glob('b*.json')):
            text += path.read_text()
            batch = json.loads(path.read_text())
            correct = incorrect = 0
            positions = []
            for index, item in enumerate(batch['items']):
                self.assertRegex(item['case'], OPAQUE_CASE)
                seen_cases.add(item['case'])
                for candidate in item['candidates']:
                    self.assertRegex(candidate['key'], OPAQUE_KEY)
                    seen_keys.add(candidate['key'])
                if item['case'] in director and director[item['case']]['kind'] == 'control':
                    positions.append(index)
                    if director[item['case']]['expected'] == 'correct':
                        correct += 1
                    else:
                        incorrect += 1
            self.assertGreaterEqual(correct, 1)
            self.assertGreaterEqual(incorrect, 1)
            self.assertFalse(all(position == len(batch['items']) - 1 for position in positions))
        self.assertEqual(seen_cases, set(director))
        self.assertEqual(seen_keys, set(controls_map) | set(json.loads(
            (out / 'keymap.json').read_text())))
        self.assertNotIn('CTL-', text)
        self.assertNotIn('ct000', text)
        self.assertNotIn('r9', text)
        self.assertTrue(any(director[case]['kind'] == 'control' for case in director))

    def test_insufficient_positive_controls_fails_closed(self):
        root = self.root / '25'
        write_jsonl(root / 'corpus.jsonl', [])
        write_jsonl(root / 'raw.jsonl', [])
        write_jsonl(root / 'v3' / 'train.jsonl', [
            {'id': f'r{i:05d}', 'messages': [{'content': 'x'}, {'content': f'echo {i}'}]}
            for i in range(1, 26)])
        write_jsonl(root / 'v3' / 'requests.jsonl', [
            {'id': f'r{i:05d}', 'request': f'Request {i}.'} for i in range(1, 26)])
        write_jsonl(root / 'controls.jsonl', controls(24, 40))
        with self.assertRaisesRegex(ValueError, 'insufficient correct controls'):
            build_v4_pool.build_pool(root / 'corpus.jsonl', root / 'raw.jsonl', root / 'v3',
                                     root / 'out', batch_size=1,
                                     controls_path=root / 'controls.jsonl',
                                     controls_per_batch=3, effective=stub_effective,
                                     validate=stub_validate)

    def test_control_capacity_exceeded_fails_closed(self):
        root = self.root / '25'
        write_jsonl(root / 'corpus.jsonl', [])
        write_jsonl(root / 'raw.jsonl', [])
        write_jsonl(root / 'v3' / 'train.jsonl', [
            {'id': f'r{i:05d}', 'messages': [{'content': 'x'}, {'content': f'echo {i}'}]}
            for i in range(1, 26)])
        write_jsonl(root / 'v3' / 'requests.jsonl', [
            {'id': f'r{i:05d}', 'request': f'Request {i}.'} for i in range(1, 26)])
        write_jsonl(root / 'controls.jsonl', controls(25, 26))
        with self.assertRaisesRegex(ValueError, 'insufficient control capacity'):
            build_v4_pool.build_pool(root / 'corpus.jsonl', root / 'raw.jsonl', root / 'v3',
                                     root / 'out', batch_size=1,
                                     controls_path=root / 'controls.jsonl',
                                     controls_per_batch=2, effective=stub_effective,
                                     validate=stub_validate)

    def test_25_batches_all_mixed_and_all_controls_accounted(self):
        root = self.root / '25'
        write_jsonl(root / 'corpus.jsonl', [])
        write_jsonl(root / 'raw.jsonl', [])
        write_jsonl(root / 'v3' / 'train.jsonl', [
            {'id': f'r{i:05d}', 'messages': [{'content': 'x'}, {'content': f'echo {i}'}]}
            for i in range(1, 26)])
        write_jsonl(root / 'v3' / 'requests.jsonl', [
            {'id': f'r{i:05d}', 'request': f'Request {i}.'} for i in range(1, 26)])
        write_jsonl(root / 'controls.jsonl', controls(25, 40))
        out = root / 'out'
        manifest = build_v4_pool.build_pool(
            root / 'corpus.jsonl', root / 'raw.jsonl', root / 'v3', out, batch_size=1,
            controls_path=root / 'controls.jsonl', controls_per_batch=3,
            control_seed=13, effective=stub_effective, validate=stub_validate)
        self.assertEqual(manifest['counts']['batches'], 25)
        self.assertEqual(manifest['counts']['controls_injected'], 65)
        self.assertEqual(manifest['counts']['controls_total'], 65)
        controls_map = json.loads((out / 'controls-map.json').read_text())
        director = json.loads((out / 'director-map.json').read_text())
        self.assertEqual(set(manifest['controls_by_batch']),
                         {f'b{index:02d}' for index in range(25)})
        for batch_name, summary in manifest['controls_by_batch'].items():
            self.assertGreaterEqual(summary['correct'], 1)
            self.assertGreaterEqual(summary['incorrect'], 1)
        for path in sorted((out / 'batches').glob('b*.json')):
            batch = json.loads(path.read_text())
            control_cases = [item['case'] for item in batch['items']
                             if director[item['case']]['kind'] == 'control']
            self.assertTrue(control_cases)
            self.assertTrue(any(director[case]['expected'] == 'correct'
                                for case in control_cases))
            self.assertTrue(any(director[case]['expected'] == 'incorrect'
                                for case in control_cases))
        self.assertEqual(len(controls_map), 65)
        self.assertEqual(sum(1 for case in director if director[case]['kind'] == 'control'), 65)

    def test_duplicate_control_pair_or_source_fails(self):
        write_jsonl(self.root / 'controls.jsonl', CONTROLS + [CONTROLS[0]])
        with self.assertRaisesRegex(ValueError, 'duplicate control key'):
            self.build(self.root / 'out', controls_path=self.root / 'controls.jsonl',
                       controls_per_batch=3)
        duplicate_pair = dict(CONTROLS[1])
        duplicate_pair['key'] = 'ct9999'
        duplicate_pair['case'] = 'CTL-99'
        duplicate_pair['source'] = 'docs/eval-audit/items.json#x9999'
        write_jsonl(self.root / 'controls.jsonl', CONTROLS + [duplicate_pair])
        with self.assertRaisesRegex(ValueError, 'duplicate control request/command pair'):
            self.build(self.root / 'out2', controls_path=self.root / 'controls.jsonl',
                       controls_per_batch=3)

    def test_distribution_is_seeded_and_reproducible(self):
        first, second = self.root / 'out1', self.root / 'out2'
        self.build(first, controls_path=self.root / 'controls.jsonl', controls_per_batch=3,
                   control_seed=13)
        self.build(second, controls_path=self.root / 'controls.jsonl', controls_per_batch=3,
                   control_seed=13)
        self.assertEqual(tree_bytes(first), tree_bytes(second))
        third = self.root / 'out3'
        self.build(third, controls_path=self.root / 'controls.jsonl', controls_per_batch=3,
                   control_seed=14)
        self.assertNotEqual(tree_bytes(first), tree_bytes(third))
        manifest = json.loads((third / 'manifest.json').read_text())
        for summary in manifest['controls_by_batch'].values():
            self.assertGreaterEqual(summary['correct'], 1)
            self.assertGreaterEqual(summary['incorrect'], 1)

    def test_missing_v3_request_raises(self):
        write_jsonl(self.root / 'v3' / 'train.jsonl', [
            {'id': 'r00001', 'messages': [{'content': 'x'}, {'content': 'echo one'}]},
            {'id': 'r00005', 'messages': [{'content': 'x'}, {'content': ''}]},
        ])
        with self.assertRaisesRegex(ValueError, r'1 v3 rows.*r00005'):
            self.build(self.root / 'out')

    def test_zero_batch_size_and_controls_per_batch_raise(self):
        with self.assertRaisesRegex(ValueError, 'batch_size must be >= 1'):
            self.build(self.root / 'out', batch_size=0)
        with self.assertRaisesRegex(ValueError, 'controls_per_batch must be >= 1'):
            self.build(self.root / 'out', controls_per_batch=0)

    def test_missing_raw_samples_row_raises(self):
        write_jsonl(self.root / 'raw.jsonl', [
            {'id': 'r00003', 'request': 'Raw three.', 'samples': [{'cmd': 'z -1'}]},
            {'id': 'r00004', 'request': 'Raw four.', 'samples': [{'cmd': None}]},
        ])
        with self.assertRaisesRegex(ValueError, r'1 corpus ids missing.*r00005'):
            self.build(self.root / 'out')

    def test_validate_exclusion_drops_candidate_and_records_it(self):
        def validate(rid, command, request):
            if (rid, command) == ('r00005', 'd -5'):
                raise ValueError('fixture: fails serving validation')

        out = self.root / 'out'
        manifest = self.build(out, batch_size=90, validate=validate)
        keymap = json.loads((out / 'keymap.json').read_text())
        self.assertEqual(len(keymap), 4)
        self.assertFalse(any(entry['rid'] == 'r00005' and entry['command'] == 'd -5'
                             for entry in keymap.values()))
        self.assertEqual(manifest['excluded_candidates'],
                         [{'rid': 'r00005', 'command': 'd -5'}])
        self.assertEqual(manifest['counts']['excluded_candidates'], 1)
        self.assertEqual(manifest['counts']['candidates'], 4)

    def test_all_candidates_excluded_drops_rid_like_zero_candidates(self):
        def validate(rid, command, request):
            if rid == 'r00005':
                raise ValueError('fixture: fails serving validation')

        out = self.root / 'out'
        manifest = self.build(out, validate=validate)
        keymap = json.loads((out / 'keymap.json').read_text())
        self.assertEqual(len(keymap), 3)
        self.assertFalse(any(entry['rid'] == 'r00005' for entry in keymap.values()))
        self.assertEqual(manifest['excluded_candidates'], [
            {'rid': 'r00005', 'command': 'b -5'},
            {'rid': 'r00005', 'command': 'd -5'},
        ])
        self.assertIn({'rid': 'r00005', 'reason': 'all_candidates_excluded'},
                      manifest['warnings'])

    def test_rerun_is_byte_identical(self):
        first = self.root / 'out1'
        second = self.root / 'out2'
        self.build(first, controls_path=self.root / 'controls.jsonl', controls_per_batch=3)
        self.build(second, controls_path=self.root / 'controls.jsonl', controls_per_batch=3)
        self.assertEqual(tree_bytes(first), tree_bytes(second))

    def test_nonempty_output_directory_fails(self):
        out = self.root / 'out'
        out.mkdir()
        (out / 'stale.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'not empty'):
            self.build(out)

    def test_repository_controls_have_verified_positive_coverage(self):
        path = Path(__file__).resolve().parents[1] / 'data/distill/stage2-v4/judge/controls.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        self.assertEqual(len(rows), 65)
        self.assertEqual(sum(1 for row in rows if row['expected'] == 'correct'), 25)
        self.assertEqual(sum(1 for row in rows if row['expected'] == 'incorrect'), 40)
        self.assertEqual(len({row['source'] for row in rows}), 65)
        self.assertEqual(len({(row['request'], row['command']) for row in rows}), 65)
        repo = path.parents[4]
        items = json.loads((repo / 'docs/eval-audit/items.json').read_text())
        evidence = {
            'ct0061': ('x0283', 'r0.json', 'm012'),
            'ct0062': ('x0509', 'r2.json', 'm009'),
            'ct0063': ('x0520', 'r0.json', 'm024'),
            'ct0064': ('x0540', 'r3.json', 'm044'),
            'ct0065': ('x0571', 'r1.json', 'm076'),
        }
        for key, (xid, pass2, marker) in evidence.items():
            row = next(row for row in rows if row['key'] == key)
            self.assertEqual(row['expected'], 'correct')
            self.assertEqual(row['source'], f'docs/eval-audit/items.json#{xid}')
            self.assertEqual(row['request'], items[xid]['request'])
            self.assertEqual(row['command'], items[xid]['command'])
            self.assertIn(f'pass2-opus/{pass2} {marker} {xid} correct',
                          row['provenance'])
            self.assertIn('pass1 b', row['provenance'])
            pass2_data = json.loads(
                (repo / 'docs/eval-audit/pass2-opus' / pass2).read_text())
            verdict = next(v for case in pass2_data['cases']
                           for v in case['verdicts'] if v['key'] == xid)
            self.assertEqual(verdict['verdict'], 'correct')


if __name__ == '__main__':
    unittest.main()
