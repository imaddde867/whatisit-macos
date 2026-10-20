import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
try:
    import judge_v4_local as local
except ModuleNotFoundError:
    local = None


class LocalJudgeTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(local, 'local judging controller is not implemented')
        self.batch = {'batch': 'b05', 'items': [{
            'case': 'c0123456789ab', 'request': 'List files, including hidden files.',
            'candidates': [{'key': 'k0123456789ab', 'command': 'ls -la'}]}]}

    def verdict(self, session):
        return {'batch': 'b05', 'judge': session, 'cases': [{
            'case': 'c0123456789ab', 'verdicts': [{
                'key': 'k0123456789ab', 'verdict': 'correct', 'category': None,
                'evidence': '-a includes hidden entries; -l lists details.'}]}]}

    def test_tools_reject_commands_paths_and_unknown_actions(self):
        for name in ['grep; touch pwned', '../controls-map.json', '-f', '/bin/sh']:
            with self.subTest(name=name), self.assertRaises(ValueError):
                local.handle_tool('read_manual', {'name': name})
        with self.assertRaises(ValueError):
            local.handle_tool('shell', {'command': 'echo forbidden'})
        with self.assertRaises(ValueError):
            local.handle_tool('read_manual', {'name': 'grep', 'start': -1})

    def test_tool_loop_and_fresh_batch_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'controls-map.json').write_text('DIRECTOR_SECRET')
            for session in ['local-a', 'local-b']:
                output = root / f'{session}.json'
                calls = []

                def post(base_url, payload, timeout):
                    calls.append(copy.deepcopy(payload))
                    self.assertNotIn('DIRECTOR_SECRET', json.dumps(payload))
                    self.assertFalse(output.exists())
                    if len(calls) == 1:
                        self.assertEqual(len(payload['messages']), 2)
                        message = {'role': 'assistant', 'content': None, 'tool_calls': [{
                            'id': 'tool1', 'type': 'function', 'function': {
                                'name': 'check_stock_tool', 'arguments': '{"name":"printf"}'}}]}
                        return {'choices': [{'finish_reason': 'tool_calls', 'message': message}]}
                    tool = payload['messages'][-1]
                    self.assertEqual(tool['role'], 'tool')
                    self.assertEqual(tool['tool_call_id'], 'tool1')
                    self.assertTrue(json.loads(tool['content'])['found'])
                    return {'choices': [{'finish_reason': 'stop', 'message': {
                        'role': 'assistant', 'content': json.dumps(self.verdict(session))}}]}

                local.judge(self.batch, 'Judge commands using this test rubric.', session,
                            output, root / session, 'http://localhost/v1', 'local', post=post)
                self.assertEqual(json.loads(output.read_text()), self.verdict(session))
                self.assertEqual(len(calls), 2)

    def test_truncated_or_incomplete_response_never_writes_verdict(self):
        for finish, body in [('length', self.verdict('local-a')),
                             ('stop', {'batch': 'b05', 'judge': 'local-a', 'cases': []})]:
            with self.subTest(finish=finish), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / 'verdict.json'

                def post(base_url, payload, timeout):
                    return {'choices': [{'finish_reason': finish, 'message': {
                        'role': 'assistant', 'content': json.dumps(body)}}]}

                with self.assertRaises(ValueError):
                    local.judge(self.batch, 'Rubric', 'local-a', output, Path(tmp) / 'run',
                                'http://localhost/v1', 'local', post=post)
                self.assertFalse(output.exists())

    def test_director_metadata_is_rejected_before_any_request(self):
        for location in ['batch', 'item', 'candidate']:
            batch = copy.deepcopy(self.batch)
            target = {'batch': batch, 'item': batch['items'][0],
                      'candidate': batch['items'][0]['candidates'][0]}[location]
            target['expected'] = 'DIRECTOR_SECRET'
            with self.subTest(location=location), tempfile.TemporaryDirectory() as tmp:
                def forbidden_post(*args):
                    self.fail('director metadata reached the model transport')

                with self.assertRaises(ValueError):
                    local.judge(batch, 'Rubric', 'local-a', Path(tmp) / 'out.json',
                                Path(tmp) / 'run', 'http://localhost/v1', 'local',
                                post=forbidden_post)

    def test_extended_manual_review_can_finish_without_partial_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'verdict.json'
            requests = 0

            def post(base_url, payload, timeout):
                nonlocal requests
                requests += 1
                self.assertFalse(output.exists())
                if requests <= 33:
                    return {'choices': [{'finish_reason': 'tool_calls', 'message': {
                        'role': 'assistant', 'content': None, 'tool_calls': [{
                            'id': f'tool{requests}', 'type': 'function', 'function': {
                                'name': 'check_stock_tool', 'arguments': '{"name":"printf"}'}}]}}]}
                return {'choices': [{'finish_reason': 'stop', 'message': {
                    'role': 'assistant', 'content': json.dumps(self.verdict('local-a'))}}]}

            local.judge(self.batch, 'Rubric', 'local-a', output, Path(tmp) / 'run',
                        'http://localhost/v1', 'local', post=post)
            self.assertEqual(json.loads(output.read_text()), self.verdict('local-a'))


if __name__ == '__main__':
    unittest.main()
