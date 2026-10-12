import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from teacher_sample import parse_answer


class TeacherSampleTests(unittest.TestCase):
    def test_braces_and_escaped_quotes_in_commands(self):
        for command in ("awk '{print $1}' data.tsv",
                        'find tree -exec printf "%s\\n" {} \\;',
                        'echo "{hello}"'):
            with self.subTest(command=command):
                self.assertEqual(parse_answer(json.dumps({'command': command})),
                                 (command, '', True))

    def test_wrapped_final_answer_and_null(self):
        text = '<think>{"command":"wrong"}</think>\n```json\n{"command":null,"reason":"missing"}\n```'
        self.assertEqual(parse_answer(text), (None, 'missing', True))

    def test_malformed_or_multiline_command_is_not_a_null_vote(self):
        for text in ('not JSON', '{"command":', json.dumps({'command': 'pwd\nls'})):
            with self.subTest(text=text):
                self.assertEqual(parse_answer(text), (None, '', False))
