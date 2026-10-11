import contextlib
import io
import json
import unittest
from unittest.mock import patch

from whatisit_macos.cli import main

GENERATED = {'status': 'suggestion', 'command': 'find /tmp -type f', 'reason': '',
             'notes': ['Generated locally; review before running.'], 'sources': ['local model']}


class CliTests(unittest.TestCase):
    def invoke(self, args, *, system='Darwin'):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), \
                patch('whatisit_macos.cli.platform.system', return_value=system):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_request_goes_to_local_model_with_explicit_path(self):
        with patch('whatisit_macos.local_recovery.suggest_local', return_value=GENERATED) as suggest_local:
            code, stdout, _ = self.invoke(['--json', '--path', '/tmp/example', 'find temporary files'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout), GENERATED)
        self.assertEqual(suggest_local.call_args.args, ('find temporary files',))
        self.assertEqual(suggest_local.call_args.kwargs, {'path': '/tmp/example'})

    def test_failure_goes_to_stderr_with_exit_2(self):
        failure = {'status': 'unsupported', 'command': None, 'reason': 'no model', 'notes': [], 'sources': []}
        with patch('whatisit_macos.local_recovery.suggest_local', return_value=failure):
            code, stdout, stderr = self.invoke(['do something'])
        self.assertEqual((code, stdout), (2, ''))
        self.assertIn('unsupported: no model', stderr)

    def test_non_macos_never_loads_the_model(self):
        with patch('whatisit_macos.local_recovery.suggest_local', side_effect=AssertionError('called')):
            code, stdout, _ = self.invoke(['--json', 'list files'], system='Linux')
        self.assertEqual(code, 2)
        self.assertIsNone(json.loads(stdout)['command'])

    def test_no_request_prints_help(self):
        code, stdout, _ = self.invoke([])
        self.assertEqual(code, 2)
        self.assertIn('usage:', stdout)


if __name__ == '__main__':
    unittest.main()
