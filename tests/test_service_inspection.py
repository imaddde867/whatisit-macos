import contextlib
import io
import json
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from whatisit_macos import engine, local_model
from whatisit_macos.cli import main
from whatisit_macos.retrieval import Manual, build_index


class ServiceInspectionTests(unittest.TestCase):
    def target(self, domain='system', label='com.apple.logd'):
        target = getattr(engine, 'ServiceTarget', None)
        self.assertIsNotNone(target, 'Typed service-target inputs are missing')
        return target(domain=domain, label=label)

    def query(self, request='Inspect a known launchd service configuration', **kwargs):
        return engine.suggest(request, system='Darwin', which=lambda tool: tool, **kwargs)

    def test_known_service_requires_explicit_domain_and_label(self):
        answer = self.query()
        self.assertEqual(answer['status'], 'needs-input')
        self.assertEqual(answer['missing'], ['domain', 'label'])
        self.assertIsNone(answer['command'])

        self.assertEqual(self.query(service_target=self.target(domain=None))['missing'], ['domain'])
        self.assertEqual(self.query(service_target=self.target(label=None))['missing'], ['label'])

    def test_known_service_renders_only_explicit_supported_target(self):
        for domain in ['system', 'user/0', 'user/501', 'gui/0', 'gui/501']:
            with self.subTest(domain=domain):
                answer = self.query(service_target=self.target(domain))
                self.assertEqual(answer['status'], 'suggestion')
                self.assertEqual(answer['argv'], ['launchctl', 'print', f'{domain}/com.apple.logd'])
                self.assertEqual(shlex.split(answer['command']), answer['argv'])

    def test_invalid_service_targets_are_rejected(self):
        for domain, label in [('login/7', 'com.apple.logd'), ('pid/123', 'com.apple.logd'),
                              ('system; touch nope', 'com.apple.logd'),
                              ('gui/not-a-uid', 'com.apple.logd'), ('system', 'x; touch nope'),
                              ('system', 'com.apple.logd\n'), ('system', 'x' * 256)]:
            with self.subTest(domain=domain, label=label):
                answer = self.query(service_target=self.target(domain, label))
                self.assertEqual(answer['status'], 'needs-input')
                self.assertIsNone(answer['command'])

    def test_owner_and_full_plist_requests_do_not_get_partial_suggestions(self):
        for request in ['Which launchd service owns PID 123?',
                        'Inspect launchd service configuration and identify its owner',
                        'Show the original launchd plist for this service',
                        'Show launchd service configuration and its running process']:
            with self.subTest(request=request):
                answer = self.query(request, service_target=self.target())
                self.assertEqual(answer['status'], 'unsupported')
                self.assertIsNone(answer['command'])

    def test_service_mutations_and_compound_inspection_do_not_get_print_suggestions(self):
        for request in ['Restart launchd service configuration',
                        'Load launchd service configuration',
                        'Unload launchd service configuration',
                        'Stop launchd service configuration',
                        'Inspect launchd service configuration and battery cycle count']:
            with self.subTest(request=request):
                answer = self.query(request, service_target=self.target())
                self.assertIn(answer['status'], ['unsupported', 'ambiguous'])
                self.assertIsNone(answer['command'])

    def test_service_flags_are_not_ignored_by_other_recipes(self):
        self.assertEqual(self.query('show sleep assertions', service_target=self.target())['status'],
                         'needs-input')
        self.assertEqual(self.query(service_target=self.target(), path='/tmp/unused')['status'], 'needs-input')
        self.assertEqual(self.query(service_target=self.target(), log_filter=engine.LogFilter(pid=123))['status'],
                         'needs-input')

    def test_cli_forwards_explicit_service_target(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), \
                patch('whatisit_macos.cli.platform.system', return_value='Darwin'), \
                patch('whatisit_macos.cli.shutil.which', side_effect=lambda tool: tool), \
                patch('subprocess.run', side_effect=AssertionError('Command executed')):
            code = main(['--json', '--domain', 'system', '--label', 'com.apple.logd',
                         'Inspect a known launchd service configuration'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())['argv'],
                         ['launchctl', 'print', 'system/com.apple.logd'])

    def test_model_selection_uses_shared_service_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / 'docs.sqlite3'
            build_index(index, [Manual('launchctl', 'test:launchctl', '/bin/launchctl', '27.0.1',
                                       '2026-10-09', 'Print a launchd service target.')])
            answer = local_model.suggest_with_model(
                'Inspect a known launchd service configuration', index=index,
                select=lambda _: '{"operation":"launchd-service"}', system='Darwin',
                which=lambda tool: tool, service_target=self.target('user/501'))
            self.assertEqual(answer['argv'], ['launchctl', 'print', 'user/501/com.apple.logd'])
            answer = local_model.suggest_with_model(
                'Which launchd service owns PID 123?', index=index,
                select=lambda _: '{"operation":"launchd-service"}', system='Darwin',
                which=lambda tool: tool, service_target=self.target())
            self.assertEqual(answer['status'], 'unsupported')
            self.assertIsNone(answer['command'])


if __name__ == '__main__':
    unittest.main()
