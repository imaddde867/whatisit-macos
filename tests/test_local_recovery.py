import json
import re
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from whatisit_macos import local_recovery
from whatisit_macos import local_recovery_worker


class LocalRecoveryTests(unittest.TestCase):
    def test_worker_uses_json_and_drops_remote_configuration(self):
        response = {'status': 'suggestion', 'command': 'find . -type f',
                    'reason': '', 'notes': ['Review before running.'],
                    'sources': ['local model']}
        env = {'PATH': '/usr/bin', 'HOME': '/tmp/home',
               'WHATISIT_MODEL': '/tmp/model.gguf',
               'WHATISIT_OPENAI_BASE_URL': 'https://example.invalid/v1',
               'NL2SH_OPENAI_API_KEY': 'secret', 'OPENAI_API_KEY': 'secret',
               'NVIDIA_API_KEY': 'secret'}
        with patch.dict(os.environ, env, clear=True), \
                patch('whatisit_macos.local_recovery.subprocess.run',
                      return_value=SimpleNamespace(returncode=0, stdout=json.dumps(response), stderr='')) as run:
            answer = local_recovery.suggest_local('find files', path='/tmp/example')

        self.assertEqual(answer, response)
        invocation = run.call_args.kwargs
        self.assertEqual(run.call_args.args[0], [sys.executable, '-m', 'whatisit_macos.local_recovery_worker'])
        self.assertEqual(json.loads(invocation['input']),
                         {'request': 'find files', 'path': '/tmp/example'})
        self.assertEqual(invocation['env']['WHATISIT_MODEL'], '/tmp/model.gguf')
        self.assertNotIn('WHATISIT_OPENAI_BASE_URL', invocation['env'])
        self.assertNotIn('NL2SH_OPENAI_API_KEY', invocation['env'])
        self.assertNotIn('OPENAI_API_KEY', invocation['env'])
        self.assertNotIn('NVIDIA_API_KEY', invocation['env'])

    def test_worker_failure_returns_visible_abstention(self):
        with patch('whatisit_macos.local_recovery.subprocess.run',
                   side_effect=OSError('worker is missing')):
            answer = local_recovery.suggest_local('find files')
        self.assertEqual(answer['status'], 'unsupported')
        self.assertIsNone(answer['command'])
        self.assertIn('local generation failed', answer['reason'].lower())

    def test_invalid_request_is_rejected_before_worker_start(self):
        with patch('whatisit_macos.local_recovery.subprocess.run') as run:
            for request in ['', 'x' * 2001, 'show\nfiles']:
                with self.subTest(request=request[:10]):
                    answer = local_recovery.suggest_local(request)
                    self.assertEqual(answer['status'], 'unsupported')
                    self.assertIsNone(answer['command'])
        run.assert_not_called()

    def test_malformed_worker_result_is_not_reported_as_success(self):
        malformed = [
            {'status': 'suggestion', 'command': None, 'reason': '', 'notes': [], 'sources': []},
            {'status': 'suggestion', 'command': 'find .', 'reason': '', 'notes': [], 'sources': 'local'},
            {'status': 'unsupported', 'command': 'find .', 'reason': 'failed', 'notes': [], 'sources': []},
        ]
        for response in malformed:
            with self.subTest(response=response), patch(
                    'whatisit_macos.local_recovery.subprocess.run',
                    return_value=SimpleNamespace(returncode=0, stdout=json.dumps(response), stderr='')):
                answer = local_recovery.suggest_local('find files')
                self.assertEqual(answer['status'], 'unsupported')
                self.assertIsNone(answer['command'])

    def run_worker(self, *, mode='server', findings=None, command='find . -type f', request='list files'):
        with tempfile.TemporaryDirectory() as directory:
            model = os.path.join(directory, 'model.gguf')
            server = os.path.join(directory, 'llama-server')
            Path(model).touch()
            Path(server).touch()
            config = types.ModuleType('whatisit.config')
            config.DEFAULTS = {'max_tokens': 64}
            config.load_config = lambda: {'threads': 2, 'force_tcp': True,
                                          'server_port': 4096,
                                          'openai_base_url': 'https://example.invalid/v1'}
            config.find_model = lambda: Path(model)
            config.data_dir = lambda: Path(directory)
            config.env = lambda name: os.environ.get(f'WHATISIT_{name}')
            engine = types.ModuleType('whatisit.engine')
            calls = []

            def generate(prompt, cfg, **kwargs):
                calls.append((prompt, cfg, kwargs))
                return [command], 0.2, mode

            engine.generate = generate
            safety = types.ModuleType('whatisit.safety')
            safety.check = lambda command: findings or []
            safety.PLACEHOLDER_HINT = re.compile(r'/path/to/|\bmy[-_]')
            package = types.ModuleType('whatisit')
            package.config, package.engine, package.safety = config, engine, safety
            with patch.dict(sys.modules, {'whatisit': package, 'whatisit.config': config,
                                          'whatisit.engine': engine, 'whatisit.safety': safety}), \
                    patch.dict(os.environ, {'WHATISIT_LLAMA_SERVER': server}, clear=True):
                answer = local_recovery_worker.suggest(
                    {'request': request, 'path': '/tmp/example'})
        return answer, calls

    def test_worker_reuses_upstream_server_and_reports_cautions(self):
        answer, calls = self.run_worker(findings=[('CAUTION', 'uses sudo')])
        self.assertEqual(answer['status'], 'suggestion')
        self.assertEqual(answer['command'], 'find . -type f')
        self.assertIn('review before running', answer['notes'][0].lower())
        self.assertIn('uses sudo', answer['notes'][1])
        prompt, cfg, kwargs = calls[0]
        self.assertIn('Target system: macOS', prompt)
        self.assertIn('/tmp/example', prompt)
        self.assertEqual((cfg['max_tokens'], cfg['ctx_size'], cfg['idle_timeout']), (256, 4096, 60))
        self.assertFalse(cfg['host_context'])
        self.assertEqual(cfg['openai_base_url'], '')
        self.assertEqual((cfg['threads'], cfg['force_tcp'], cfg['server_port']), (2, True, 4096))
        self.assertEqual(kwargs, {'force_oneshot': False, 'quiet': True})

    def test_worker_rejects_oneshot_and_dangerous_output(self):
        answer, _ = self.run_worker(mode='oneshot')
        self.assertEqual(answer['status'], 'unsupported')
        self.assertIsNone(answer['command'])
        answer, _ = self.run_worker(findings=[('DANGER', 'deletes data')])
        self.assertEqual(answer['status'], 'unsupported')
        self.assertIsNone(answer['command'])

    @unittest.skipUnless(sys.platform == 'darwin', 'lint reads this Mac\'s man pages')
    def test_worker_rejects_gnu_only_output(self):
        answer, _ = self.run_worker(command='du -x --max-depth=1 | sort -n')
        self.assertEqual(answer['status'], 'unsupported')
        self.assertIsNone(answer['command'])
        self.assertIn('--max-depth', answer['reason'])

    @unittest.skipUnless(sys.platform == 'darwin', 'lint reads this Mac\'s man pages')
    def test_worker_rejects_placeholders_the_user_did_not_name(self):
        answer, _ = self.run_worker(command='du -h /path/to/folder', request='how much free disk space')
        self.assertEqual(answer['status'], 'unsupported')
        self.assertIn('/path/to/', answer['reason'])
        for command, request in [('cat my_notes.txt', 'show my_notes.txt'),
                                 ('sort <names.txt >sorted.txt', 'sort names.txt into sorted.txt')]:
            answer, _ = self.run_worker(command=command, request=request)
            self.assertEqual(answer['status'], 'suggestion', command)


if __name__ == '__main__':
    unittest.main()
