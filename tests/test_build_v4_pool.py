import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_v4_pool


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


CONTROLS = [
    {'key': 'ct0001', 'case': 'CTL-01', 'request': 'Control one.', 'command': 'ctl -1',
     'expected': 'incorrect', 'source': 'docs/eval-audit/items.json#c1'},
    {'key': 'ct0002', 'case': 'CTL-02', 'request': 'Control two.', 'command': 'ctl -2',
     'expected': 'correct', 'source': 'docs/eval-audit/items.json#c2'},
]


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
            {'id': 'r00001', 'request': 'V3 request one.'},
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

    def test_keymap_contents_key_order_and_batch_slicing(self):
        out = self.root / 'out'
        manifest = self.build(out, batch_size=2)
        keymap = json.loads((out / 'keymap.json').read_text())
        self.assertEqual(list(keymap), ['x0000', 'x0001', 'x0002', 'x0003', 'x0004'])
        self.assertEqual(keymap, {
            'x0000': {'group': 'v3_kept', 'rid': 'r00001', 'command': 'echo one'},
            'x0001': {'group': 'no_majority', 'rid': 'r00003', 'command': 'a -2'},
            'x0002': {'group': 'no_majority', 'rid': 'r00003', 'command': 'z -1'},
            'x0003': {'group': 'no_majority', 'rid': 'r00005', 'command': 'b -5'},
            'x0004': {'group': 'no_majority', 'rid': 'r00005', 'command': 'd -5'},
        })
        self.assertEqual(json.loads((out / 'batches' / 'b00.json').read_text()), {
            'batch': 'b00',
            'items': [{'case': 'r00001', 'request': 'V3 request one.',
                       'candidates': [{'key': 'x0000', 'command': 'echo one'}]},
                      {'case': 'r00003', 'request': 'Raw three.',
                       'candidates': [{'key': 'x0001', 'command': 'a -2'},
                                      {'key': 'x0002', 'command': 'z -1'}]}],
        })
        self.assertEqual(json.loads((out / 'batches' / 'b01.json').read_text()), {
            'batch': 'b01',
            'items': [{'case': 'r00005', 'request': 'Raw five.',
                       'candidates': [{'key': 'x0003', 'command': 'b -5'},
                                      {'key': 'x0004', 'command': 'd -5'}]}],
        })
        self.assertFalse((out / 'batches' / 'b02.json').exists())
        self.assertFalse((out / 'controls-map.json').exists())
        self.assertEqual(manifest['counts'], {
            'v3_rows': 2, 'v3_items': 1, 'v3_candidates': 1,
            'no_majority_considered': 3, 'no_majority_with_candidates': 2,
            'excluded_candidates': 0,
            'items': 3, 'candidates': 5, 'batches': 2,
            'controls_injected': 0, 'controls_total': 0,
        })
        self.assertEqual(manifest['excluded_candidates'], [])
        self.assertEqual(manifest['warnings'], [{'rid': 'r00004', 'reason': 'no_candidates'}])
        self.assertEqual(manifest['batch_size'], 2)
        self.assertEqual(set(manifest['inputs_sha256']),
                         {'corpus', 'raw_samples', 'v3_train', 'v3_requests'})

    def test_controls_are_injected_after_items_and_mapped(self):
        out = self.root / 'out'
        manifest = self.build(out, controls_path=self.root / 'controls.jsonl',
                              controls_per_batch=1)
        b00 = json.loads((out / 'batches' / 'b00.json').read_text())
        b01 = json.loads((out / 'batches' / 'b01.json').read_text())
        self.assertEqual([item['case'] for item in b00['items']], ['r00001', 'CTL-01'])
        self.assertEqual(b00['items'][1], {
            'case': 'CTL-01', 'request': 'Control one.',
            'candidates': [{'key': 'ct0001', 'command': 'ctl -1'}]})
        self.assertEqual([item['case'] for item in b01['items']], ['r00003', 'CTL-02'])
        b02 = json.loads((out / 'batches' / 'b02.json').read_text())
        self.assertEqual([item['case'] for item in b02['items']], ['r00005'])
        self.assertEqual(json.loads((out / 'controls-map.json').read_text()), {
            'ct0001': {'expected': 'incorrect', 'source': 'docs/eval-audit/items.json#c1'},
            'ct0002': {'expected': 'correct', 'source': 'docs/eval-audit/items.json#c2'},
        })
        self.assertEqual(manifest['counts']['controls_injected'], 2)
        self.assertEqual(manifest['counts']['controls_total'], 2)
        self.assertIn('controls', manifest['inputs_sha256'])

    def test_controls_beyond_batch_capacity_warn_without_injecting(self):
        write_jsonl(self.root / 'controls.jsonl', CONTROLS + [
            {'key': 'ct0003', 'case': 'CTL-03', 'request': 'Control three.',
             'command': 'ctl -3', 'expected': 'incorrect',
             'source': 'docs/eval-audit/items.json#c3'}])
        out = self.root / 'out'
        manifest = self.build(out, batch_size=90, controls_path=self.root / 'controls.jsonl',
                              controls_per_batch=1)
        self.assertEqual(manifest['counts']['controls_injected'], 1)
        self.assertEqual(manifest['counts']['controls_total'], 3)
        self.assertEqual(json.loads((out / 'controls-map.json').read_text()), {
            'ct0001': {'expected': 'incorrect', 'source': 'docs/eval-audit/items.json#c1'}})
        self.assertEqual(manifest['warnings'][-1],
                         {'reason': 'controls_not_injected', 'keys': ['ct0002', 'ct0003']})

    def test_missing_v3_request_raises(self):
        write_jsonl(self.root / 'v3' / 'train.jsonl', [
            {'id': 'r00001', 'messages': [{'content': 'x'}, {'content': 'echo one'}]},
            {'id': 'r00005', 'messages': [{'content': 'x'}, {'content': ''}]},
        ])
        with self.assertRaisesRegex(ValueError, r'1 v3 rows.*r00005'):
            self.build(self.root / 'out')

    def test_validate_exclusion_drops_candidate_and_records_it(self):
        def validate(rid, command, request):
            if (rid, command) == ('r00005', 'd -5'):
                raise ValueError('fixture: fails serving validation')

        out = self.root / 'out'
        manifest = self.build(out, batch_size=90, validate=validate)
        keymap = json.loads((out / 'keymap.json').read_text())
        self.assertEqual(list(keymap), ['x0000', 'x0001', 'x0002', 'x0003'])
        self.assertEqual(keymap['x0003'], {'group': 'no_majority', 'rid': 'r00005',
                                           'command': 'b -5'})
        items = {item['case']: item
                 for item in json.loads((out / 'batches' / 'b00.json').read_text())['items']}
        self.assertEqual(items['r00005']['candidates'],
                         [{'key': 'x0003', 'command': 'b -5'}])
        self.assertEqual(items['r00003']['candidates'],
                         [{'key': 'x0001', 'command': 'a -2'},
                          {'key': 'x0002', 'command': 'z -1'}])
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
        self.assertEqual(list(keymap), ['x0000', 'x0001', 'x0002'])
        self.assertEqual(json.loads((out / 'batches' / 'b01.json').read_text()), {
            'batch': 'b01',
            'items': [{'case': 'r00003', 'request': 'Raw three.',
                       'candidates': [{'key': 'x0001', 'command': 'a -2'},
                                      {'key': 'x0002', 'command': 'z -1'}]}],
        })
        self.assertFalse((out / 'batches' / 'b02.json').exists())
        self.assertEqual(manifest['excluded_candidates'], [
            {'rid': 'r00005', 'command': 'b -5'},
            {'rid': 'r00005', 'command': 'd -5'},
        ])
        self.assertEqual(manifest['counts']['excluded_candidates'], 2)
        self.assertEqual(manifest['counts']['no_majority_with_candidates'], 1)
        self.assertEqual(manifest['counts']['items'], 2)
        self.assertIn({'rid': 'r00005', 'reason': 'all_candidates_excluded'},
                      manifest['warnings'])

    def test_rerun_is_byte_identical(self):
        first = self.root / 'out1'
        second = self.root / 'out2'
        self.build(first, controls_path=self.root / 'controls.jsonl', controls_per_batch=2)
        self.build(second, controls_path=self.root / 'controls.jsonl', controls_per_batch=2)
        self.assertEqual(tree_bytes(first), tree_bytes(second))


if __name__ == '__main__':
    unittest.main()
