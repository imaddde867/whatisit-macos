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
        self.assertEqual(len(json.loads(stdout)), 3)

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


if __name__ == "__main__":
    unittest.main()
