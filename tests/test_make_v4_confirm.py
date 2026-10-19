import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import make_v4_confirm
from build_verified_dataset import load_verdicts, select


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


KEYMAP = {
    'x0000': {'group': 'v3_kept', 'rid': 'r00001', 'command': 'echo one'},
    'x0001': {'group': 'v3_kept', 'rid': 'r00002', 'command': 'echo two'},
    'x0002': {'group': 'no_majority', 'rid': 'r00003', 'command': 'a -2'},
    'x0003': {'group': 'no_majority', 'rid': 'r00003', 'command': 'z -1'},
    'x0004': {'group': 'no_majority', 'rid': 'r00004', 'command': 'e -4'},
    'x0005': {'group': 'no_majority', 'rid': 'r00005', 'command': 'f -5'},
}

VERDICTS = {
    'batch': 'b00', 'judge': 'fixture',
    'cases': [
        {'case': 'r00001', 'verdicts': [
            {'key': 'x0000', 'verdict': 'correct', 'category': None, 'evidence': 'Matches.'}]},
        {'case': 'r00002', 'verdicts': [
            {'key': 'x0001', 'verdict': 'incorrect', 'category': 'other', 'evidence': 'Wrong.'}]},
        {'case': 'r00003', 'verdicts': [
            {'key': 'x0002', 'verdict': 'correct', 'category': None, 'evidence': 'OK.'},
            {'key': 'x0003', 'verdict': 'incorrect', 'category': 'other', 'evidence': 'No.'}]},
        {'case': 'r00004', 'verdicts': [
            {'key': 'x0004', 'verdict': 'unsure', 'category': None, 'evidence': 'Unclear.'}]},
        {'case': 'r00005', 'verdicts': [
            {'key': 'x0005', 'verdict': 'incorrect', 'category': 'other', 'evidence': 'No.'}]},
    ],
}


class ConfirmTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'keymap.json').write_text(json.dumps(KEYMAP, indent=2))
        write_jsonl(self.root / 'raw.jsonl', [
            {'id': 'r00003', 'request': 'Raw three.', 'samples': [
                {'cmd': 'a -2'}, {'cmd': 'a -2'}, {'cmd': 'z -1'}]},
            {'id': 'r00004', 'request': 'Raw four.', 'samples': [{'cmd': 'e -4'}]},
            {'id': 'r00005', 'request': 'Raw five.', 'samples': [{'cmd': 'f -5'}]},
        ])
        write_jsonl(self.root / 'v3_requests.jsonl', [
            {'id': 'r00001', 'request': 'V3 request one.'},
            {'id': 'r00002', 'request': 'V3 request two.'},
        ])
        (self.root / 'verdicts').mkdir()
        (self.root / 'verdicts' / 'b00.json').write_text(json.dumps(VERDICTS, indent=2))

    def confirm(self, out_dir, **kwargs):
        kwargs.setdefault('effective', stub_effective)
        return make_v4_confirm.build_confirm(
            self.root / 'keymap.json', self.root / 'raw.jsonl',
            self.root / 'v3_requests.jsonl', self.root / 'verdicts', Path(out_dir), **kwargs)

    def test_selection_parity_with_select_and_sample_1_keeps_all(self):
        # Parity: rebuild the documented selection rules here with the real select().
        correct = {key for key, verdict in load_verdicts(self.root / 'verdicts').items()
                   if verdict == 'correct'}
        self.assertEqual(correct, {'x0000', 'x0002'})
        counts = {'a -2': 2, 'z -1': 1}
        self.assertEqual(select({cmd: counts[cmd]
                                 for key, cmd in [('x0002', 'a -2'), ('x0003', 'z -1')]
                                 if key in correct}), 'a -2')
        self.assertIsNone(select({cmd: counts[cmd] for key, cmd in [('x0004', 'e -4')]
                                  if key in correct}))
        self.assertIsNone(select({cmd: counts[cmd] for key, cmd in [('x0005', 'f -5')]
                                  if key in correct}))

        out = self.root / 'out'
        manifest = self.confirm(out, sample=1.0, seed=13, batch_size=1)
        self.assertEqual(manifest, {'selected_total': 2, 'sampled': 2, 'sample': 1.0,
                                    'seed': 13, 'batch_size': 1})
        self.assertEqual(json.loads((out / 'b00.json').read_text()), {
            'batch': 'b00',
            'items': [{'case': 'r00001', 'request': 'V3 request one.',
                       'candidates': [{'key': 'x0000', 'command': 'echo one'}]}]})
        self.assertEqual(json.loads((out / 'b01.json').read_text()), {
            'batch': 'b01',
            'items': [{'case': 'r00003', 'request': 'Raw three.',
                       'candidates': [{'key': 'x0002', 'command': 'a -2'},
                                      {'key': 'x0003', 'command': 'z -1'}]}]})
        self.assertFalse((out / 'b02.json').exists())

    def test_sampling_respects_seed_and_sample_fraction(self):
        out = self.root / 'out'
        manifest = self.confirm(out, sample=0.5, seed=13)
        self.assertEqual(manifest['selected_total'], 2)
        self.assertEqual(manifest['sampled'], 1)
        self.assertEqual(manifest['sample'], 0.5)
        self.assertEqual(manifest['seed'], 13)
        self.assertEqual(manifest['batch_size'], 90)
        batch = json.loads((out / 'b00.json').read_text())
        self.assertEqual(batch['batch'], 'b00')
        self.assertEqual(len(batch['items']), 1)
        self.assertIn(batch['items'][0]['case'], {'r00001', 'r00003'})
        self.assertFalse((out / 'b01.json').exists())

    def test_counts_drift_raises_naming_rid_key_and_command(self):
        def effective(sample, request):
            return 'stale' if sample['cmd'] == 'e -4' else sample['cmd']

        with self.assertRaisesRegex(ValueError, r"r00004.*x0004.*'e -4'"):
            self.confirm(self.root / 'out', sample=1.0, effective=effective)

    def test_rerun_is_byte_identical(self):
        first, second = self.root / 'out1', self.root / 'out2'
        self.confirm(first, sample=0.5, seed=13)
        self.confirm(second, sample=0.5, seed=13)
        self.assertEqual(tree_bytes(first), tree_bytes(second))

    def test_pool_then_confirm_end_to_end(self):
        import build_v4_pool
        root = self.root / 'e2e'
        write_jsonl(root / 'corpus.jsonl', [{'id': 'r00001', 'request': 'Corpus one.'},
                                            {'id': 'r00003', 'request': 'Corpus three.'}])
        write_jsonl(root / 'raw.jsonl', [
            {'id': 'r00003', 'request': 'Raw three.',
             'samples': [{'cmd': 'ls a'}, {'cmd': 'ls b'}]}])
        write_jsonl(root / 'v3' / 'train.jsonl', [
            {'id': 'r00001', 'messages': [{'content': 'x'}, {'content': 'echo one'}]}])
        write_jsonl(root / 'v3' / 'requests.jsonl', [{'id': 'r00001', 'request': 'V3 one.'}])
        build_v4_pool.build_pool(root / 'corpus.jsonl', root / 'raw.jsonl', root / 'v3',
                                 root / 'pool', effective=stub_effective,
                                 validate=stub_validate)
        keymap = json.loads((root / 'pool' / 'keymap.json').read_text())
        self.assertEqual(list(keymap), ['x0000', 'x0001', 'x0002'])
        (root / 'verdicts').mkdir()
        (root / 'verdicts' / 'b00.json').write_text(json.dumps({
            'batch': 'b00', 'judge': 'fixture', 'cases': [
                {'case': 'r00001', 'verdicts': [
                    {'key': 'x0000', 'verdict': 'correct', 'category': None, 'evidence': 'OK.'}]},
                {'case': 'r00003', 'verdicts': [
                    {'key': 'x0001', 'verdict': 'correct', 'category': None, 'evidence': 'OK.'},
                    {'key': 'x0002', 'verdict': 'incorrect', 'category': 'other',
                     'evidence': 'No.'}]}],
        }))
        manifest = make_v4_confirm.build_confirm(
            root / 'pool' / 'keymap.json', root / 'raw.jsonl',
            root / 'v3' / 'requests.jsonl', root / 'verdicts', root / 'confirm',
            sample=1.0, seed=13, effective=stub_effective)
        self.assertEqual(manifest['selected_total'], 2)
        pool_batch = json.loads((root / 'pool' / 'batches' / 'b00.json').read_text())
        confirm_batch = json.loads((root / 'confirm' / 'b00.json').read_text())
        self.assertEqual(confirm_batch, pool_batch)


if __name__ == '__main__':
    unittest.main()
