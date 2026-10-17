from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from train_distill_cuda import chat_tokens, split_validation, MACOS_PREFIX


class TokenizerProbe:
    def apply_chat_template(self, messages, **kwargs):
        assert kwargs['return_dict'] is False
        if kwargs['add_generation_prompt']:
            return [10, 11, 12]
        return [10, 11, 12] + ([20] if messages[-1]['content'] else []) + [99, 13]

    def convert_tokens_to_ids(self, token):
        assert token == '<|im_end|>'
        return 99


class CudaChatTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('WHATISIT_CUDA_ASSETS'), 'requires pinned CUDA assets')
    def test_zero_step_saves_unmerged_adapter_and_hashes(self):
        from whatisit import config
        assets = Path(os.environ['WHATISIT_CUDA_ASSETS'])
        with tempfile.TemporaryDirectory(prefix='whatisit-adapter-test-') as tmp:
            root = Path(tmp)
            row = self.record('pwd')
            row.update(id='synthetic-adapter-probe')
            row['messages'][0]['content'] = config.SYSTEM_PROMPT
            data = root / 'train.jsonl'
            data.write_text(json.dumps(row) + '\n')
            output = root / 'output'
            subprocess.run([sys.executable, 'tools/train_distill_cuda.py',
                            str(assets / 'nl2sh-1.5b-Q4_K_M.gguf'), str(assets / 'student-metadata'),
                            str(data), str(output), '--steps', '0'], check=True)
            self.assertTrue((output / 'adapter/adapter_model.safetensors').is_file())
            self.assertTrue((output / 'adapter/adapter_config.json').is_file())
            report = json.loads((output / 'training-report.json').read_text())
            self.assertTrue(report['zero_update_weights_equal'])
            self.assertEqual(report['adapter_sha256'], {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((output / 'adapter').iterdir()) if p.is_file()})

    def record(self, target=''):
        return {'messages': [{'role': 'system', 'content': 'system'},
                             {'role': 'user', 'content': MACOS_PREFIX + 'Synthetic probe.'},
                             {'role': 'assistant', 'content': target}]}

    def test_masks_prompt_but_trains_empty_target_end_of_turn(self):
        for command, expected in [('', [-100, -100, -100, 99, 13]),
                                  ('printf test', [-100, -100, -100, 20, 99, 13])]:
            with self.subTest(command=command):
                _, labels = chat_tokens(self.record(command), TokenizerProbe(), 'system')
                self.assertEqual(labels, expected)

    def test_refuses_invalid_roles_prefix_and_command(self):
        rows = [self.record('pwd\nls'), self.record()]
        rows[1]['messages'][1]['content'] = 'unprefixed request'
        for row in rows + [{'messages': [None, None, None]}]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                chat_tokens(row, TokenizerProbe(), 'system')

class SplitTests(unittest.TestCase):
    def test_stratified_deterministic_and_disjoint(self):
        rows = [{'messages': [None, None, {'content': '' if i % 4 == 0 else f'cmd{i}'}]} for i in range(200)]
        train, val = split_validation(rows, 0.1)
        self.assertEqual((train, val), split_validation(rows, 0.1))
        self.assertEqual(sorted(train + val), list(range(200)))
        empty = [i for i in val if rows[i]['messages'][2]['content'] == '']
        self.assertEqual((len(val), len(empty)), (20, 5))
        self.assertEqual(split_validation(rows, 0.0), (list(range(200)), []))

    def test_five_percent_grouped_split_keeps_source_families_together(self):
        rows = [{'id': f'r{i}', 'source_id': f'family{i // 2}',
                 'messages': [None, {'content': MACOS_PREFIX + f'request {i} token{i}'},
                              {'content': '' if i % 4 == 0 else f'cmd{i}'}]}
                for i in range(200)]
        train, val = split_validation(rows, 0.05)
        self.assertEqual((train, val), split_validation(rows, 0.05))
        self.assertEqual(sorted(train + val), list(range(200)))
        train_groups = {rows[i]['source_id'] for i in train}
        val_groups = {rows[i]['source_id'] for i in val}
        self.assertFalse(train_groups & val_groups)
        self.assertLessEqual(abs(len(val) - 10), 2)
        self.assertTrue(any(rows[i]['messages'][2]['content'] == '' for i in val))
        self.assertTrue(any(rows[i]['messages'][2]['content'] for i in val))

    def test_grouped_split_merges_same_command_and_near_duplicate_requests(self):
        def row(i, source, request, command):
            return {'id': f'r{i}', 'source_id': source,
                    'messages': [None, {'content': MACOS_PREFIX + request}, {'content': command}]}
        rows = [row(i, f's{i}', f'unique request number {i} alpha{i}', f'cmd{i}') for i in range(100)]
        rows += [row(100, 's100', 'count lines in notes.txt', 'wc -l notes.txt'),
                 row(101, 's101', 'how many lines does report.md have', 'wc -l notes.txt'),
                 row(102, 's102', 'show disk usage of the project folder now', 'du -sh project'),
                 row(103, 's103', 'show disk usage of the project folder please', 'du -sh project/')]
        for fraction in (0.05, 0.2, 0.4):
            train, val = split_validation(rows, fraction)
            for pair in ((100, 101), (102, 103)):
                self.assertEqual(pair[0] in val, pair[1] in val, (fraction, pair))
