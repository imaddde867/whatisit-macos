from pathlib import Path
import sys
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

