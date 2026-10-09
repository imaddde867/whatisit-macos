import contextlib
import io
import json
import shlex
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from whatisit_macos import engine, local_model
from whatisit_macos.cli import main
from whatisit_macos.retrieval import Manual, build_index


class LogFilterTests(unittest.TestCase):
    def filters(self, **changes):
        inputs = getattr(engine, 'LogFilter', None)
        self.assertIsNotNone(inputs, 'Typed log-filter inputs are missing')
        values = dict(subsystem='com.example.whatisit', pid=123, level='error',
                      start='2026-10-09 10:00:00+0300', end='2026-10-09 10:01:00+0300')
        return inputs(**(values | changes))

    def query(self, request='Filter unified logs', **kwargs):
        return engine.suggest(request, system='Darwin', which=lambda tool: tool, **kwargs)

    def test_missing_log_inputs_are_reported_without_guessing(self):
        answer = self.query()
        self.assertEqual(answer['status'], 'needs-input')
        self.assertEqual(answer['missing'], ['subsystem', 'pid', 'level', 'start', 'end'])
        self.assertIsNone(answer['command'])
        answer = self.query(log_filter=self.filters(pid=None))
        self.assertEqual(answer['missing'], ['pid'])
        self.assertIsNone(answer['command'])

    def test_explicit_filters_render_one_literal_predicate(self):
        for level in ['error', 'default']:
            with self.subTest(level=level):
                answer = self.query(log_filter=self.filters(level=level))
                self.assertEqual(answer['status'], 'suggestion')
                self.assertEqual(answer['argv'], [
                    'log', 'show', '--style', 'compact', '--start', '2026-10-09 10:00:00+0300',
                    '--end', '2026-10-09 10:01:00+0300', '--predicate',
                    f'subsystem == "com.example.whatisit" AND logType == "{level}" AND processIdentifier == 123'])
                self.assertEqual(shlex.split(answer['command']), answer['argv'])

    def test_invalid_filters_cannot_inject_predicates_or_shell(self):
        for changes in [dict(subsystem='x" OR TRUEPREDICATE OR subsystem == "x'),
                        dict(subsystem='$(touch nope)'), dict(subsystem='a\\b'),
                        dict(subsystem='x\n'), dict(subsystem='x\x00'),
                        dict(subsystem=42), dict(subsystem='x' * 256),
                        dict(pid=0), dict(pid=-1), dict(pid=True), dict(pid='123 OR 1'),
                        dict(level='debug'), dict(level='fault'), dict(level='error" OR 1')]:
            with self.subTest(changes=changes):
                answer = self.query(log_filter=self.filters(**changes))
                self.assertEqual(answer['status'], 'needs-input')
                self.assertIsNone(answer['command'])

    def test_time_bounds_require_valid_ordered_offset_timestamps(self):
        for changes in [dict(start='2026-02-30 10:00:00+0300'),
                        dict(start='2026-10-09 10:00:00'), dict(start='yesterday'),
                        dict(start='2026-10-09 10:00:00+2500'),
                        dict(start='2026-10-09 10:00:00+0300\n'),
                        dict(end='2026-10-09 10:00:00+0300'),
                        dict(end='2026-10-09 09:59:59+0300'),
                        dict(end='2026-10-09 07:00:00+0000')]:
            with self.subTest(changes=changes):
                answer = self.query(log_filter=self.filters(**changes))
                self.assertEqual(answer['status'], 'needs-input')
                self.assertIsNone(answer['command'])
        self.assertEqual(self.query(log_filter=self.filters(
            end='2026-10-09 07:01:00+0000'))['status'], 'suggestion')

    def test_extra_scope_does_not_return_partial_log_answers(self):
        for request in ['Stream unified logs live', 'Filter unified logs as JSON',
                        'Filter unified logs including debug messages',
                        'Filter unified logs by process name', 'Filter unified logs from an archive',
                        'Filter unified logs and show battery cycles',
                        'Filter unified logs for the last hour', 'Filter unified logs since boot',
                        'Filter unified logs containing a message', 'Erase unified logs']:
            with self.subTest(request=request):
                answer = self.query(request, log_filter=self.filters())
                self.assertEqual(answer['status'], 'unsupported')
                self.assertIsNone(answer['command'])

    def test_log_flags_and_paths_are_not_ignored_by_other_operations(self):
        self.assertEqual(self.query('show sleep assertions', log_filter=self.filters())['status'], 'needs-input')
        self.assertEqual(self.query(log_filter=self.filters(), path='/tmp/unused')['status'], 'needs-input')

    def test_platform_and_tool_checks_apply_to_log_filters(self):
        for system, which, status in [('Linux', lambda tool: tool, 'unsupported'),
                                      ('Darwin', lambda tool: None, 'unavailable')]:
            answer = engine.suggest('Filter unified logs', log_filter=self.filters(),
                                    system=system, which=which)
            self.assertEqual(answer['status'], status)
            self.assertIsNone(answer['command'])

    def test_cli_forwards_filters_and_never_executes_the_suggestion(self):
        self.filters()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout), \
                patch('whatisit_macos.cli.platform.system', return_value='Darwin'), \
                patch('whatisit_macos.cli.shutil.which', side_effect=lambda tool: tool), \
                patch('subprocess.run', side_effect=AssertionError('Command executed')):
            code = main(['--json', '--subsystem', 'com.example.whatisit', '--pid', '123',
                         '--level', 'error', '--start', '2026-10-09 10:00:00+0300',
                         '--end', '2026-10-09 10:01:00+0300', 'Filter unified logs'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())['argv'][-1],
                         'subsystem == "com.example.whatisit" AND logType == "error" AND processIdentifier == 123')

    def test_model_selection_uses_shared_validation_and_explicit_inputs(self):
        filters = self.filters()
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / 'docs.sqlite3'
            build_index(index, [Manual('log', 'test:log', '/usr/bin/log', '27.0.1',
                                       '2026-10-09', 'Filter unified logs.')])
            for inputs, status in [(filters, 'suggestion'), (None, 'needs-input'),
                                   (replace(filters, subsystem='x" OR 1'), 'needs-input')]:
                answer = local_model.suggest_with_model(
                    'Filter unified logs', index=index, select=lambda _: '{"operation":"unified-log-filter"}',
                    system='Darwin', which=lambda tool: tool, log_filter=inputs)
                self.assertEqual(answer['status'], status)
                if status != 'suggestion':
                    self.assertIsNone(answer['command'])


if __name__ == '__main__':
    unittest.main()
