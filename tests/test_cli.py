import contextlib
import io
import json
import unittest
from unittest.mock import patch

from whatisit_macos.cli import main


class CliTests(unittest.TestCase):
    def invoke(self, args, *, system="Darwin"):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), \
                patch("whatisit_macos.cli.platform.system", return_value=system), \
                patch("whatisit_macos.cli.shutil.which", return_value="/usr/bin/tool"):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_json_suggestion(self):
        code, stdout, stderr = self.invoke(["--json", "show sleep assertions"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["command"], "pmset -g assertions")
        self.assertEqual(stderr, "")

    def test_unsupported_request_uses_local_fallback_with_explicit_inputs(self):
        generated = {'status': 'suggestion', 'command': 'find /tmp -type f',
                     'reason': '', 'notes': ['Generated locally; review before running.'],
                     'sources': ['local model']}
        with patch('whatisit_macos.local_recovery.suggest_local', return_value=generated) as suggest_local:
            code, stdout, _ = self.invoke(['--json', '--path', '/tmp/example', 'find temporary files'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout), generated)
        self.assertEqual(suggest_local.call_args.args, ('find temporary files',))
        self.assertEqual(suggest_local.call_args.kwargs, {'path': '/tmp/example'})

    def test_catalog_only_keeps_unsupported_without_loading_local_runtime(self):
        with patch('whatisit_macos.local_recovery.suggest_local', side_effect=AssertionError('fallback called')):
            code, stdout, _ = self.invoke(['--catalog-only', '--json', 'show arbitrary thing'])
        answer = json.loads(stdout)
        self.assertEqual(code, 2)
        self.assertEqual(answer['status'], 'unsupported')

    def test_local_fallback_does_not_override_needs_input(self):
        with patch('whatisit_macos.local_recovery.suggest_local', side_effect=AssertionError('fallback called')):
            code, stdout, _ = self.invoke(['--json', 'show file metadata'])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout)['status'], 'needs-input')

    def test_missing_input_json_contract(self):
        code, stdout, _ = self.invoke(["--json", "show file metadata"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout)["status"], "needs-input")

    def test_catalog_can_be_listed_on_linux(self):
        code, stdout, _ = self.invoke(["--json", "--list"], system="Linux")
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(stdout)), 6)

    def test_app_signature_cli_and_missing_path(self):
        code, stdout, _ = self.invoke(['--json', '--path', '/tmp/example.app', 'verify app signature'])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)['argv'],
                         ['codesign', '--verify', '--deep', '--strict', '--verbose=2', '/tmp/example.app'])
        code, stdout, _ = self.invoke(['--json', 'verify app signature'])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(stdout)['missing'], ['path'])

    def test_unsupported_human_output_goes_to_stderr(self):
        code, stdout, stderr = self.invoke(["stream unified logs live"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("unsupported", stderr)

    def test_timing_does_not_corrupt_json(self):
        code, stdout, stderr = self.invoke(["--json", "--timing", "show sleep assertions"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["status"], "suggestion")
        self.assertIn("Lookup:", stderr)

    def test_no_request_prints_help(self):
        code, stdout, _ = self.invoke([])
        self.assertEqual(code, 2)
        self.assertIn("usage:", stdout)

    def test_lookup_does_not_execute_or_connect(self):
        with patch("subprocess.run", side_effect=AssertionError("unexpected execution")), \
                patch("socket.create_connection", side_effect=AssertionError("unexpected network call")):
            code, _, _ = self.invoke(["show sleep assertions"])
        self.assertEqual(code, 0)



if __name__ == "__main__":
    unittest.main()
