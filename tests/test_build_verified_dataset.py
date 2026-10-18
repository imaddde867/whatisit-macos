import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import call, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
try:
    import build_verified_dataset as builder
    from whatisit_macos.local_recovery_worker import MACOS_PREFIX
except ImportError as error:  # the scorer import is lazy, so only a broken environment skips
    raise unittest.SkipTest(str(error))


class SelectTests(unittest.TestCase):
    def test_none_correct_gives_no_label(self):
        self.assertIsNone(builder.select({}))

    def test_largest_equivalence_cluster_wins_over_single_most_frequent_string(self):
        counts = {'ls -l -a': 1, 'ls -a -l': 1, 'ls -la .': 0, 'find . -maxdepth 1': 2}
        self.assertIn(builder.select(counts), {'ls -l -a', 'ls -a -l'})

    def test_within_cluster_most_frequent_then_shortest(self):
        self.assertEqual(builder.select({'stat -f %B a.txt': 2, 'stat  -f %B a.txt': 3}), 'stat  -f %B a.txt')
        self.assertEqual(builder.select({'wc -l a': 1, 'wc -l  a': 1}), 'wc -l a')


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / 'out'
        records = {
            self.root / 'data/corpus/requests.jsonl': [
                {'id': 'r00001', 'request': 'Show the Working  Directory', 'kind': 'answer'},
                {'id': 'r00002', 'request': 'what time is it', 'kind': 'abstain'},
                {'id': 'r00003', 'request': 'list files by size', 'kind': 'answer'},
                {'id': 'r00004', 'request': 'summarize the disk usage of this folder', 'kind': 'answer'},
                {'id': 'r00005', 'request': 'show the working directory', 'kind': 'answer'},
                {'id': 'r00006', 'request': 'print the kernel version', 'kind': 'answer'},
                {'id': 'r00007', 'request': 'Summarize the  disk usage of this folder', 'kind': 'answer'},
            ],
            self.root / 'data/distill/stage2-v3/train.jsonl': [
                {'id': 'r00001', 'messages': [
                    {'role': 'system', 'content': 'SYS'},
                    {'role': 'user', 'content': MACOS_PREFIX + 'Show the Working  Directory'},
                    {'role': 'assistant', 'content': 'pwd -P'}]},
                {'id': 'r00002', 'messages': [
                    {'role': 'system', 'content': 'SYS'},
                    {'role': 'user', 'content': MACOS_PREFIX + 'what time is it'},
                    {'role': 'assistant', 'content': ''}]},
                {'id': 'r00006', 'messages': [
                    {'role': 'system', 'content': 'SYS'},
                    {'role': 'user', 'content': MACOS_PREFIX + 'print the kernel version'},
                    {'role': 'assistant', 'content': 'uname -a'}]},
            ],
            self.root / 'data/distill/stage2-v3/requests.jsonl': [
                {'id': 'r00001', 'request': 'Show the Working  Directory', 'kind': 'answer'},
                {'id': 'r00002', 'request': 'what time is it', 'kind': 'abstain'},
                {'id': 'r00006', 'request': 'print the kernel version', 'kind': 'answer'},
            ],
            self.root / 'data/teacher/roihu_full_raw_samples.jsonl': [
                {'id': 'r00003', 'request': 'list files by size',
                 'samples': [{'command': 'ls -lS'}] * 3 + [{'command': 'ls -lt'}] * 2},
                {'id': 'r00004', 'request': 'summarize the disk usage of this folder',
                 'samples': [{'command': 'du -sh .'}] * 3},
                {'id': 'r00005', 'request': 'show the working directory',
                 'samples': [{'command': 'pwd'}] * 3},
                # M2: mirrors quarantined r00004's request; pre-add drops must not enter seen
                {'id': 'r00007', 'request': 'Summarize the  disk usage of this folder',
                 'samples': [{'command': 'du -sh .'}] * 3},
            ],
        }
        for path, rows in records.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        (self.root / 'data/distill/roihu_full_quarantine_ids.txt').write_text(
            'r00006 # historical list; r00006 is a v3 row, so only the corpus list below matters\n')
        (self.root / 'data/distill/quarantine_ids.txt').write_text(
            'r00004 # corpus-level list, names only this id\n')
        (self.root / 'eval').mkdir()
        for split in ('dev', 'everyday', 'frozen', 'heldout'):
            (self.root / 'eval' / f'{split}.jsonl').write_text(json.dumps(
                {'request': f'unrelated {split} task', 'reference': 'echo unrelated'}) + '\n')
        self.keymap = {
            'x0001': {'group': 'v3_kept', 'rid': 'r00001', 'command': 'pwd -P'},
            'x0003': {'group': 'no_majority', 'rid': 'r00003', 'command': 'ls -lS'},
            'x0004': {'group': 'no_majority', 'rid': 'r00004', 'command': 'du -sh .'},
            'x0005': {'group': 'no_majority', 'rid': 'r00005', 'command': 'pwd'},
            'x0006': {'group': 'v3_kept', 'rid': 'r00006', 'command': 'uname -a'},
            'x0007': {'group': 'no_majority', 'rid': 'r00007', 'command': 'du -sh .'},
        }
        self.verdicts = {'x0001': 'correct', 'x0003': 'correct', 'x0004': 'correct',
                         'x0005': 'correct', 'x0006': 'incorrect', 'x0007': 'correct'}
        self.confirmed = {'x0003': 'correct'}

    def run_build(self):
        fake = types.ModuleType('score_teacher_eval')
        fake.effective_command = lambda sample, request: sample.get('command')
        with patch.object(builder, 'ROOT', self.root), \
                patch.object(builder, 'validate_command', return_value=None) as validate, \
                patch.dict(sys.modules, {'score_teacher_eval': fake}):
            manifest = builder.build(self.keymap, self.verdicts, self.confirmed, self.out)
        return manifest, validate

    def test_happy_path_keeps_drops_and_adds_by_verdict(self):
        manifest, validate = self.run_build()
        rows = builder.read_jsonl(self.out / 'train.jsonl')
        self.assertEqual([row['id'] for row in rows], ['r00001', 'r00002', 'r00003', 'r00007'])
        self.assertEqual(rows[1]['messages'][-1]['content'], '')
        self.assertEqual(rows[2]['messages'], [
            {'role': 'system', 'content': 'SYS'},
            {'role': 'user', 'content': MACOS_PREFIX + 'list files by size'},
            {'role': 'assistant', 'content': 'ls -lS'}])
        self.assertEqual((manifest['rows'], manifest['commands'], manifest['empty_targets']), (4, 3, 1))
        self.assertEqual(manifest['actions'], {'keep_v3': 2, 'add_verified': 2,
                                               'drop_v3_judged_incorrect': 1, 'drop_quarantine': 1,
                                               'drop_duplicate_request': 1})
        self.assertEqual(validate.call_args_list, [
            call('r00003', 'ls -lS', 'list files by size'),
            call('r00007', 'du -sh .', 'Summarize the  disk usage of this folder')])
        audit = builder.read_jsonl(self.out / 'audit.jsonl')
        self.assertIn({'id': 'r00003', 'action': 'add_verified', 'target': 'ls -lS'}, audit)
        self.assertIn({'id': 'r00006', 'action': 'drop_v3_judged_incorrect', 'target': 'uname -a'}, audit)

    def test_corpus_quarantine_list_only_row_is_dropped(self):
        self.run_build()
        self.assertIn({'id': 'r00004', 'action': 'drop_quarantine'},
                      builder.read_jsonl(self.out / 'audit.jsonl'))
        self.assertNotIn('r00004', [row['id'] for row in builder.read_jsonl(self.out / 'train.jsonl')])

    def test_v3_row_with_target_missing_from_keymap_raises(self):
        self.keymap.pop('x0001')
        with self.assertRaisesRegex(ValueError, '1 v3 rows.*r00001'):
            self.run_build()

    def test_keymap_candidate_missing_from_fresh_counts_raises(self):
        self.keymap['x0003']['command'] = 'ls -ltr'
        self.verdicts['x0003'] = 'incorrect'  # raises even when the candidate is not judged correct
        with self.assertRaisesRegex(ValueError, "r00003.*x0003.*'ls -ltr'"):
            self.run_build()

    def test_duplicate_of_kept_request_is_dropped_naming_first_occurrence(self):
        self.run_build()
        self.assertIn({'id': 'r00005', 'action': 'drop_duplicate_request', 'duplicate_of': 'r00001'},
                      builder.read_jsonl(self.out / 'audit.jsonl'))
        self.assertNotIn('r00005', [row['id'] for row in builder.read_jsonl(self.out / 'train.jsonl')])

    def test_duplicate_of_quarantined_request_is_still_added(self):
        self.run_build()
        audit = builder.read_jsonl(self.out / 'audit.jsonl')
        self.assertIn({'id': 'r00007', 'action': 'add_verified', 'target': 'du -sh .'}, audit)
        self.assertNotIn('drop_duplicate_request', [a['action'] for a in audit if a['id'] == 'r00007'])

    def test_corpus_and_raw_request_mismatch_raises(self):
        raw_path = self.root / 'data/teacher/roihu_full_raw_samples.jsonl'
        raw = builder.read_jsonl(raw_path)
        raw[0]['request'] = 'list every file by size'
        raw_path.write_text(''.join(json.dumps(row) + '\n' for row in raw))
        with self.assertRaisesRegex(ValueError, 'r00003.*differ'):
            self.run_build()

    def test_module_import_needs_no_upstream_whatisit_and_stays_lazy(self):
        repo = Path(__file__).resolve().parents[1]
        env = {**os.environ, 'PYTHONPATH': os.pathsep.join([str(repo / 'src'), str(repo / 'tools')])}
        code = ("import sys; sys.modules['whatisit'] = None; import build_verified_dataset; "
                "assert 'score_teacher_eval' not in sys.modules, 'scorer imported eagerly'")
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
