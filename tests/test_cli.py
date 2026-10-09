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

    def test_model_requires_explicit_documentation_index(self):
        code, stdout, _ = self.invoke(['--json', '--model', '/not/a/model', 'verify app signature'])
        self.assertEqual(code, 2)
        self.assertIn('documentation', json.loads(stdout)['reason'])

    def test_model_is_not_loaded_on_non_macos(self):
        code, stdout, _ = self.invoke(['--json', '--model', '/not/a/model', '--docs-index',
                                      '/not/an/index', 'verify app signature'], system='Linux')
        self.assertEqual(code, 2)
        answer = json.loads(stdout)
        self.assertIsNone(answer['command'])
        self.assertNotIn('model_error', answer)

    def test_unsupported_human_output_goes_to_stderr(self):
        code, stdout, stderr = self.invoke(["show unified logs"])
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

    def test_missing_docs_index_has_visible_error_and_keeps_suggestion(self):
        code, stdout, _ = self.invoke(['--json', '--docs-index', '/nonexistent/docs.sqlite3',
                                      'show sleep assertions'])
        answer = json.loads(stdout)
        self.assertEqual(code, 0)
        self.assertEqual(answer['command'], 'pmset -g assertions')
        self.assertEqual(answer['documentation'], [])
        self.assertTrue(answer['documentation_error'])

    def test_docs_do_not_turn_unsupported_request_into_command(self):
        import tempfile
        from pathlib import Path
        from whatisit_macos.retrieval import Manual, build_index
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / 'docs.sqlite3'
            build_index(index, [Manual('log', '/man/log.1', '/usr/bin/log', '27.0.1',
                                       '2026-10-08', 'Unified logs filter by subsystem.')])
            with patch('subprocess.run', side_effect=AssertionError('execution')):
                code, stdout, _ = self.invoke(['--json', '--docs-index', str(index),
                                              'show unified logs'])
            answer = json.loads(stdout)
            self.assertEqual(code, 2)
            self.assertIsNone(answer['command'])
            self.assertEqual(answer['documentation'][0]['tool'], 'log')


if __name__ == "__main__":
    unittest.main()
