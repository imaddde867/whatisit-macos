#!/usr/bin/env python3
"""Regression tests for verify_references.py (unittest-discoverable).

These prove that the verifier *rejects* outputs violating a declared assertion
and *accepts* outputs satisfying it, including focused tests for every repaired
defect. They run under ``python -m unittest discover -s tests`` on both Linux
and macOS: reference commands that stat a file use platform-appropriate syntax,
and everything else is POSIX.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import verify_references as vr
from verify_references import run_one, apply_modes, build_fixture, FixtureError, safe_join

IS_MAC = sys.platform == 'darwin'


def stat_inode(name):   # inode of a sandbox file, portable reference command
    return f"stat -f %i {name}" if IS_MAC else f"stat -c %i {name}"


def stat_size(name):
    return f"stat -f %z {name}" if IS_MAC else f"stat -c %s {name}"


def stat_size_inode(name):
    return f"stat -f '%z %i' {name}" if IS_MAC else f"stat -c '%s %i' {name}"


def stat_wrap_size(name):
    return f"stat -f '9%z9' {name}" if IS_MAC else f"stat -c '9%s9' {name}"


STOCK = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'}


class BaseCase(unittest.TestCase):
    def run_case(self, case):
        with tempfile.TemporaryDirectory() as d:
            return run_one(case, STOCK, d)


class StdoutTests(BaseCase):
    def test_nonzero_exit_fails(self):
        r = self.run_case({"id": "t", "reference": "false", "fixture": {},
                            "check": {"stdout": ""}})
        self.assertFalse(r['passed'])
        self.assertEqual(r['check_results']['nonzero_exit'], 1)

    def test_incorrect_stdout_fails(self):
        r = self.run_case({"id": "t", "reference": "echo wrong", "fixture": {},
                            "check": {"stdout": "correct\n"}})
        self.assertFalse(r['passed'])
        self.assertIs(r['check_results']['stdout'], False)

    def test_correct_stdout_passes(self):
        r = self.run_case({"id": "t", "reference": "printf 'correct\\n'", "fixture": {},
                            "check": {"stdout": "correct\n"}})
        self.assertTrue(r['passed'])
        self.assertIs(r['check_results']['stdout'], True)


class OctalTests(BaseCase):
    def test_incorrect_octal_fails(self):
        r = self.run_case({"id": "t", "reference": "printf '0644\\n'",
                            "fixture": {"files": {"f.txt": "x"}, "modes": {"f.txt": "0644"}},
                            "check": {"stdout_octal": "0600"}})
        self.assertIn('stdout_octal', r['check_results'])
        self.assertIs(r['check_results']['stdout_octal'], False)

    def test_correct_octal_passes(self):
        r = self.run_case({"id": "t", "reference": "printf '0600\\n'",
                            "fixture": {}, "check": {"stdout_octal": "0600"}})
        self.assertIs(r['check_results']['stdout_octal'], True)


class InodeTests(BaseCase):
    def test_inode_matches_as_token(self):
        r = self.run_case({"id": "t", "reference": stat_inode("test.txt"),
                            "fixture": {"files": {"test.txt": "content"}},
                            "check": {"stdout_inode_of": "test.txt"}})
        self.assertTrue(r['passed'], f"inode token match should pass: {r}")

    def test_inode_not_matched_as_substring(self):
        ref = (f"zsh -c 'test=$(stat -f %i test.txt); echo \"x${{test}}y\"'" if IS_MAC
               else f"sh -c 'echo \"x$(stat -c %i test.txt)y\"'")
        r = self.run_case({"id": "t", "reference": ref,
                           "fixture": {"files": {"test.txt": "content"}},
                           "check": {"stdout_inode_of": "test.txt"}})
        self.assertFalse(r['passed'], "embedded inode should fail token check")
        self.assertIs(r['check_results']['stdout_inode_of'], False)


class UnorderedTests(BaseCase):
    def test_missing_line_fails(self):
        r = self.run_case({"id": "t", "reference": "printf 'line1\\nline2\\n'", "fixture": {},
                            "check": {"stdout_lines_unordered": ["line1", "line2", "line3"]}})
        self.assertFalse(r['passed'])
        self.assertIs(r['check_results']['stdout_lines_unordered'], False)
        self.assertIn('line3', r['check_results']['missing_lines'])

    def test_duplicate_multiplicity_enforced(self):
        r = self.run_case({"id": "t", "reference": "printf 'a\\na\\n'", "fixture": {},
                            "check": {"stdout_lines_unordered": ["a"]}})
        self.assertFalse(r['passed'], "duplicate multiplicity mismatch should fail")
        self.assertIn('a', r['check_results']['extra_lines'])

    def test_permuted_duplicates_pass(self):
        r = self.run_case({"id": "t", "reference": "printf 'b\\na\\na\\n'", "fixture": {},
                            "check": {"stdout_lines_unordered": ["a", "a", "b"]}})
        self.assertTrue(r['passed'], f"permuted multiset should pass: {r}")


class StatFieldTests(BaseCase):
    def test_exact_ordered_fields_pass(self):
        r = self.run_case({"id": "t", "reference": stat_size_inode("test.txt"),
                           "fixture": {"files": {"test.txt": "1234567"}},
                           "check": {"stdout_stat_fields": {"path": "test.txt",
                                                            "fields": ["size", "inode"]}}})
        self.assertTrue(r['passed'], f"exact ordered stat fields should pass: {r}")

    def test_missing_and_extra_tokens_fail(self):
        r = self.run_case({"id": "t",
                           "reference": stat_size("test.txt") + "; echo extra",
                           "fixture": {"files": {"test.txt": "content"}},
                           "check": {"stdout_stat_fields": {"path": "test.txt",
                                                            "fields": ["size", "inode"]}}})
        self.assertFalse(r['passed'])
        self.assertIs(r['check_results']['stdout_stat_fields'], False)
        self.assertEqual(r['check_results']['expected_fields'], ["size", "inode"])

    def test_field_not_just_substring_anywhere_fails(self):
        r = self.run_case({"id": "t", "reference": stat_wrap_size("test.txt"),
                           "fixture": {"files": {"test.txt": "content"}},
                           "check": {"stdout_stat_fields": {"path": "test.txt",
                                                            "fields": ["size"]}}})
        self.assertFalse(r['passed'])
        self.assertIs(r['check_results']['stdout_stat_fields'], False)


class FileChecks(BaseCase):
    def test_missing_output_file_fails(self):
        r = self.run_case({"id": "t", "reference": "echo something", "fixture": {},
                            "check": {"files": {"output.txt": "expected content"}}})
        self.assertFalse(r['passed'])
        self.assertIs(r['check_results']['file:output.txt'], False)

    def test_incorrect_file_content_fails(self):
        r = self.run_case({"id": "t", "reference": "sh -c 'echo wrong > output.txt'",
                           "fixture": {}, "check": {"files": {"output.txt": "correct\n"}}})
        self.assertFalse(r['passed'])
        self.assertIs(r['check_results']['file:output.txt'], False)

    def test_correct_file_content_passes(self):
        r = self.run_case({"id": "t", "reference": "sh -c 'echo correct content > output.txt'",
                           "fixture": {}, "check": {"files": {"output.txt": "correct content\n"}}})
        self.assertTrue(r['passed'], f"correct file content should pass: {r}")


class NoExtraFilesTests(BaseCase):
    def test_extra_file_fails(self):
        r = self.run_case({"id": "t", "reference": "sh -c 'echo leftover > junk.txt'",
                           "fixture": {}, "check": {"no_extra_files": True}})
        self.assertFalse(r['passed'])
        self.assertIn('junk.txt', r['check_results']['extra_paths'])

    def test_extra_directory_fails(self):
        r = self.run_case({"id": "t", "reference": "sh -c 'mkdir newdir'",
                           "fixture": {}, "check": {"no_extra_files": True}})
        self.assertFalse(r['passed'], "extra directory should fail")
        self.assertIn('newdir', r['check_results']['extra_paths'])

    def test_extra_symlink_fails(self):
        r = self.run_case({"id": "t", "reference": "sh -c 'ln -s nowhere newlink'",
                           "fixture": {}, "check": {"no_extra_files": True}})
        self.assertFalse(r['passed'], "extra symlink should fail")
        self.assertIn('newlink', r['check_results']['extra_paths'])

    def test_fixture_dirs_and_nesting_allowed(self):
        r = self.run_case({"id": "t", "reference": "true",
                           "fixture": {"dirs": ["d/sub"], "files": {"d/sub/f.txt": "x"}},
                           "check": {"no_extra_files": True}})
        self.assertTrue(r['passed'], f"declared fixture must not be flagged: {r}")


class FixtureSafetyTests(BaseCase):
    def test_modes_applied(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "test.txt"; p.write_text("content")
            apply_modes(Path(d), {"test.txt": "0600"})
            import stat
            self.assertEqual(oct(stat.S_IMODE(p.stat().st_mode)), oct(0o600))

    def test_modes_missing_path_errors(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FixtureError):
                apply_modes(Path(d), {"nope.txt": "0600"})

    def test_safe_join_rejects_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            for bad in ("../evil", "/etc/passwd", "~/.ssh", "a/../../b"):
                with self.assertRaises(FixtureError):
                    safe_join(Path(d), bad)

    def test_build_fixture_traversal_aborts(self):
        r = self.run_case({"id": "t", "reference": "echo hi",
                           "fixture": {"files": {"../escape.txt": "x"}},
                           "check": {"stdout": "hi\n"}})
        self.assertFalse(r['passed'])
        self.assertIn('fixture', r['error'])


class MiscTests(BaseCase):
    def test_unknown_check_key_fails(self):
        r = self.run_case({"id": "t", "reference": "echo test", "fixture": {},
                           "check": {"unknown_check": "value"}})
        self.assertFalse(r['passed'])
        self.assertIn('unknown_check', r['check_results']['unknown_check_keys'])

    def test_multiple_assertions_pass(self):
        r = self.run_case({"id": "t",
                           "reference": "sh -c 'printf \"line1\\nline2\\n\" && echo done > output.txt'",
                           "fixture": {},
                           "check": {"stdout_lines_unordered": ["line1", "line2"],
                                     "files": {"output.txt": "done\n"},
                                     "no_extra_files": True}})
        self.assertTrue(r['passed'], f"all checks should pass: {r}")
        self.assertIs(r['check_results']['no_extra_files'], True)

    def test_nested_fixture_path_stays_in_sandbox(self):
        r = self.run_case({"id": "t", "reference": "printf 'test\\n'",
                           "fixture": {"files": {"subdir/file.txt": "content"}},
                           "check": {"stdout": "test\n"}})
        self.assertTrue(r['passed'])


class MainDirTests(unittest.TestCase):
    def test_output_directory_created(self):
        with tempfile.TemporaryDirectory() as base:
            cases = Path(base) / "cases"; cases.mkdir()
            (cases / "eval_fit.jsonl").write_text(json.dumps(
                {"id": "one", "reference": "printf 'x\\n'", "fixture": {},
                 "check": {"stdout": "x\n"}}) + "\n")
            out = Path(base) / "deep" / "nested" / "report.json"
            argv = sys.argv
            try:
                sys.argv = ["verify_references.py", str(cases), str(out)]
                rc = vr.main()
            finally:
                sys.argv = argv
            self.assertEqual(rc, 0)
            self.assertTrue(out.exists())
            self.assertEqual(json.loads(out.read_text())['summary']['total'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
