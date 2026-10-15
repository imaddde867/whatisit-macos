import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location('eval_learning64', Path(__file__).resolve().parents[1] / 'tools/eval_learning64.py')
eval64 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(eval64)


def case():
    return {'id': 'one', 'group': 'fit', 'request': 'show directory',
            'messages': [{'role': 'system', 'content': 'exact system'},
                         {'role': 'user', 'content': 'exact user'}],
            'reference': 'pwd', 'accept': ['^pwd$']}


def response(content, finish='stop'):
    return {'model': 'real-model', 'usage': {'completion_tokens': 2},
            'choices': [{'message': {'content': content}, 'finish_reason': finish}]}


class ClassificationTests(unittest.TestCase):
    def score(self, content, finish='stop'):
        return eval64.classify(case(), response(content, finish), lambda raw: raw.strip(),
                               lambda raws: [raws[0][0]] if raws[0][1] == 'stop' else [])

    def test_empty_truncated_parse_and_refusal(self):
        self.assertEqual(self.score('')['generation'], 'empty')
        self.assertEqual(self.score('pwd', 'length')['generation'], 'length')
        self.assertFalse(self.score('pwd', 'length')['accepted'])
        self.assertEqual(eval64.classify(case(), response('bad'), lambda _: '', lambda _: [])['generation'], 'parse')
        self.assertEqual(self.score('I cannot help with that')['generation'], 'complete')
        self.assertEqual(self.score('I cannot help with that')['verdict'], 'needs_review')

    def test_full_response_and_suffix_preserved(self):
        result = self.score('pwd\necho surprise')
        self.assertFalse(result['regex_match'])
        self.assertFalse(result['accepted'])
        self.assertEqual(result['content'], 'pwd\necho surprise')
        self.assertEqual(self.score('pwd')['generation'], 'complete')
        self.assertTrue(self.score('pwd')['accepted'])

    def test_shell_whitespace_keeps_quotes_and_lines(self):
        self.assertTrue(eval64.same_shell_whitespace('echo   "a b"', 'echo "a b"'))
        self.assertFalse(eval64.same_shell_whitespace('echo "a  b"', 'echo "a b"'))
        self.assertFalse(eval64.same_shell_whitespace('echo a\necho b', 'echo a echo b'))
        self.assertFalse(eval64.same_shell_whitespace(r'cat a\ b', r'cat a\   b'))
        self.assertFalse(eval64.same_shell_whitespace('echo "broken', 'echo "broken'))

    def test_serving_parser_filter_recorded(self):
        result = eval64.classify(case(), response('pwd'), lambda _: 'pwd', lambda _: [])
        self.assertEqual(result['generation'], 'parser_filtered')
        self.assertFalse(result['accepted'])

    def test_optional_mac_harness_gate_and_filter(self):
        record = self.score('pwd')
        from unittest.mock import Mock, patch
        reject = Mock(return_value=False)
        with patch.object(eval64.sys, 'platform', 'linux'):
            skipped = eval64.apply_harness(case(), record, True, reject)
        reject.assert_not_called()
        self.assertEqual(skipped['harness_status'], 'unavailable')
        with patch.object(eval64.sys, 'platform', 'darwin'):
            accepted = eval64.apply_harness(case(), record, True, reject)
            self.assertEqual(accepted['filtered_command'], 'pwd')
            self.assertTrue(accepted['filtered_accepted'])
            reject.assert_called_once_with('pwd', case()['request'])
            reject.return_value = True
            blocked = eval64.apply_harness(case(), record, True, reject)
            self.assertIsNone(blocked['filtered_command'])
            self.assertEqual(blocked['harness_status'], 'rejected')

    def test_malformed_response(self):
        self.assertEqual(eval64.classify(case(), {}, str, lambda _: [])['generation'], 'response_error')


class InputAndTransportTests(unittest.TestCase):
    def test_validation_rejects_duplicate_invalid_and_unanchored(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'cases.jsonl'
            for rows in [[case(), case()], [{**case(), 'accept': ['pwd']}],
                         [{**case(), 'messages': []}], [{**case(), 'reference': ''}]]:
                path.write_text('\n'.join(json.dumps(row) for row in rows))
                with self.assertRaises(ValueError):
                    eval64.load_cases(path)
            path.write_text(json.dumps(case()) + '\n')
            cases, digest = eval64.load_cases(path)
            self.assertEqual(cases, [case()])
            self.assertEqual(len(digest), 64)

    def test_exact_payload_and_full_http_body_retained(self):
        from unittest.mock import patch
        raw = json.dumps(response('pwd')).encode()
        class HTTP:
            status = 200
            headers = {'Content-Type': 'application/json'}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return raw
        with patch.object(eval64.urllib.request, 'urlopen', return_value=HTTP()) as opened:
            result = eval64.query('http://localhost:8080/v1', case()['messages'])
        self.assertEqual(result['body'], raw.decode())
        self.assertEqual(result['response'], response('pwd'))
        sent = json.loads(opened.call_args.args[0].data)
        self.assertEqual(sent['messages'], case()['messages'])
        self.assertEqual(sent['stop'], ['\n', '<|im_end|>', '```'])
        self.assertEqual((sent['seed'], sent['temperature'], sent['max_tokens']), (42, 0, 256))

    def test_refuses_existing_output_before_network(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'out.json'
            path.write_text('keep')
            with self.assertRaises(FileExistsError):
                eval64.run('http://localhost:8080/v1', [], 'hash', path, 'base', str, lambda _: [])
            self.assertEqual(path.read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
