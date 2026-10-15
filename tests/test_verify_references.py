#!/usr/bin/env python3
"""Regression tests for verify_references.py.

These tests prove that the verifier *rejects* outputs that violate a declared
assertion and *accepts* outputs that satisfy it. They include focused tests for
every defect that was repaired:

  - inode match must be a whole token (not a substring of a larger number)
  - unordered-line checks preserve duplicate multiplicity (multiset, not set)
  - stat-field checks require exact ordered tokens (not "somewhere in output")
  - no_extra_files detects directories and symlinks, not only regular files
  - modes declared for a missing fixture path are a hard error
  - fixture paths cannot escape the sandbox (traversal / absolute paths)
  - the output directory is created before the report is written

Platform note: a handful of tests invoke BSD/GNU utilities in the reference
command. They are written to pass under GNU coreutils (the CI platform); the
real 144-case reference proof runs on macOS separately.
"""
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))
import verify_references as vr
from verify_references import run_one, apply_modes, build_fixture, FixtureError, safe_join


STOCK = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'}


def run(case):
    with tempfile.TemporaryDirectory() as d:
        return run_one(case, STOCK, d)


def test_stdout_with_nonzero_exit():
    case = {"id": "t-nonzero", "reference": "false",
            "fixture": {}, "check": {"stdout": ""}}
    r = run(case)
    assert not r['passed'], "Nonzero exit should fail"
    assert r['check_results']['nonzero_exit'] == 1
    print("✓ test_stdout_with_nonzero_exit")


def test_incorrect_stdout_with_zero_exit():
    case = {"id": "t-wrong-stdout", "reference": "echo wrong",
            "fixture": {}, "check": {"stdout": "correct\n"}}
    r = run(case)
    assert not r['passed'], "Incorrect stdout should fail"
    assert r['check_results']['stdout'] is False
    print("✓ test_incorrect_stdout_with_zero_exit")


def test_correct_stdout_with_zero_exit():
    case = {"id": "t-right-stdout", "reference": "printf 'correct\\n'",
            "fixture": {}, "check": {"stdout": "correct\n"}}
    r = run(case)
    assert r['passed'], f"Correct output should pass: {r}"
    assert r['check_results']['stdout'] is True
    print("✓ test_correct_stdout_with_zero_exit")


def test_incorrect_octal_permissions():
    case = {"id": "t-octal", "reference": "printf '0644\\n'",
            "fixture": {"files": {"f.txt": "x"}, "modes": {"f.txt": "0644"}},
            "check": {"stdout_octal": "0600"}}
    r = run(case)
    assert 'stdout_octal' in r['check_results']
    assert r['check_results']['stdout_octal'] is False
    print("✓ test_incorrect_octal_permissions")


def test_correct_octal_permissions():
    case = {"id": "t-octal-ok", "reference": "printf '0600\\n'",
            "fixture": {}, "check": {"stdout_octal": "0600"}}
    r = run(case)
    assert r['check_results']['stdout_octal'] is True
    print("✓ test_correct_octal_permissions")


def test_inode_matches_as_token():
    """Inode printed as a standalone token must pass."""
    case = {"id": "t-inode-ok", "reference": "stat -c %i test.txt",
            "fixture": {"files": {"test.txt": "content"}},
            "check": {"stdout_inode_of": "test.txt"}}
    r = run(case)
    assert r['passed'], f"Inode token match should pass: {r}"
    print("✓ test_inode_matches_as_token")


def test_inode_not_matched_as_substring():
    """Inode embedded inside a larger token must NOT pass (old substring bug)."""
    case = {"id": "t-inode-sub", "reference": "sh -c 'echo \"x$(stat -c %i test.txt)y\"'",
            "fixture": {"files": {"test.txt": "content"}},
            "check": {"stdout_inode_of": "test.txt"}}
    r = run(case)
    assert not r['passed'], "Embedded inode should fail token check"
    assert r['check_results']['stdout_inode_of'] is False
    print("✓ test_inode_not_matched_as_substring")


def test_unordered_requires_missing_line():
    case = {"id": "t-unord", "reference": "printf 'line1\\nline2\\n'",
            "fixture": {}, "check": {"stdout_lines_unordered": ["line1", "line2", "line3"]}}
    r = run(case)
    assert not r['passed'], "Missing line should fail"
    assert r['check_results']['stdout_lines_unordered'] is False
    assert 'line3' in r['check_results']['missing_lines']
    print("✓ test_unordered_requires_missing_line")


def test_unordered_preserves_duplicates():
    """A repeated line must be detected: old set() code silently accepted it."""
    case = {"id": "t-unord-dup", "reference": "printf 'a\\na\\n'",
            "fixture": {}, "check": {"stdout_lines_unordered": ["a"]}}
    r = run(case)
    assert not r['passed'], "Duplicate multiplicity mismatch should fail"
    assert r['check_results']['stdout_lines_unordered'] is False
    assert 'a' in r['check_results']['extra_lines']
    print("✓ test_unordered_preserves_duplicates")


def test_unordered_accepts_permuted_duplicates():
    case = {"id": "t-unord-ok", "reference": "printf 'b\\na\\na\\n'",
            "fixture": {}, "check": {"stdout_lines_unordered": ["a", "a", "b"]}}
    r = run(case)
    assert r['passed'], f"Permuted multiset should pass: {r}"
    print("✓ test_unordered_accepts_permuted_duplicates")


def test_stat_fields_exact_and_ordered():
    """Stat fields must be the only tokens, in order."""
    case = {"id": "t-stat-ok", "reference": "stat -c '%s %i' test.txt",
            "fixture": {"files": {"test.txt": "1234567"}},
            "check": {"stdout_stat_fields": {"path": "test.txt", "fields": ["size", "inode"]}}}
    r = run(case)
    assert r['passed'], f"Exact ordered stat fields should pass: {r}"
    print("✓ test_stat_fields_exact_and_ordered")


def test_stat_fields_rejects_missing_and_extra():
    """Only size present, inode missing, plus an extra token -> fail."""
    case = {"id": "t-stat-bad", "reference": "stat -c '%s' test.txt; echo extra",
            "fixture": {"files": {"test.txt": "content"}},
            "check": {"stdout_stat_fields": {"path": "test.txt", "fields": ["size", "inode"]}}}
    r = run(case)
    assert not r['passed'], "Missing/extra stat tokens should fail"
    assert r['check_results']['stdout_stat_fields'] is False
    assert r['check_results']['expected_fields'] == ["size", "inode"]
    print("✓ test_stat_fields_rejects_missing_and_extra")


def test_stat_fields_not_just_substring_anywhere():
    """A number that merely includes the field value in the wrong place fails."""
    case = {"id": "t-stat-sub", "reference": "stat -c '9%s9' test.txt",
            "fixture": {"files": {"test.txt": "content"}},
            "check": {"stdout_stat_fields": {"path": "test.txt", "fields": ["size"]}}}
    r = run(case)
    assert not r['passed'], "Wrapped size token should fail exact-token check"
    assert r['check_results']['stdout_stat_fields'] is False
    print("✓ test_stat_fields_not_just_substring_anywhere")


def test_missing_output_file():
    case = {"id": "t-missing-file", "reference": "echo something",
            "fixture": {}, "check": {"files": {"output.txt": "expected content"}}}
    r = run(case)
    assert not r['passed'], "Missing output file should fail"
    assert r['check_results']['file:output.txt'] is False
    print("✓ test_missing_output_file")


def test_incorrect_output_file_content():
    case = {"id": "t-wrong-content", "reference": "sh -c 'echo wrong > output.txt'",
            "fixture": {}, "check": {"files": {"output.txt": "correct content\n"}}}
    r = run(case)
    assert not r['passed'], "Incorrect file content should fail"
    assert r['check_results']['file:output.txt'] is False
    print("✓ test_incorrect_output_file_content")


def test_correct_output_file_content():
    case = {"id": "t-right-content", "reference": "sh -c 'echo correct content > output.txt'",
            "fixture": {}, "check": {"files": {"output.txt": "correct content\n"}}}
    r = run(case)
    assert r['passed'], f"Correct file content should pass: {r}"
    print("✓ test_correct_output_file_content")


def test_extra_files_detects_regular_file():
    case = {"id": "t-extra-file", "reference": "sh -c 'echo leftover > junk.txt'",
            "fixture": {}, "check": {"no_extra_files": True}}
    r = run(case)
    assert not r['passed'], "Extra regular file should fail"
    assert 'junk.txt' in r['check_results']['extra_paths']
    print("✓ test_extra_files_detects_regular_file")


def test_no_extra_files_detects_directory():
    """no_extra_files must catch a stray directory (old is_file missed it)."""
    case = {"id": "t-extra-dir", "reference": "sh -c 'mkdir newdir'",
            "fixture": {}, "check": {"no_extra_files": True}}
    r = run(case)
    assert not r['passed'], "Extra directory should fail"
    assert 'newdir' in r['check_results']['extra_paths']
    print("✓ test_no_extra_files_detects_directory")


def test_no_extra_files_detects_symlink():
    """no_extra_files must catch a stray symlink (old is_file missed it)."""
    case = {"id": "t-extra-link", "reference": "sh -c 'ln -s nowhere newlink'",
            "fixture": {}, "check": {"no_extra_files": True}}
    r = run(case)
    assert not r['passed'], "Extra symlink should fail"
    assert 'newlink' in r['check_results']['extra_paths']
    print("✓ test_no_extra_files_detects_symlink")


def test_no_extra_files_allows_fixture_dirs_and_nesting():
    case = {"id": "t-nested-ok", "reference": "true",
            "fixture": {"dirs": ["d/sub"], "files": {"d/sub/f.txt": "x"}},
            "check": {"no_extra_files": True}}
    r = run(case)
    assert r['passed'], f"Declared fixture dirs/files must not be flagged: {r}"
    print("✓ test_no_extra_files_allows_fixture_dirs_and_nesting")


def test_fixture_modes_applied():
    with tempfile.TemporaryDirectory() as d:
        sandbox = Path(d)
        (sandbox / "test.txt").write_text("content")
        apply_modes(sandbox, {"test.txt": "0600"})
        import stat
        actual_mode = oct(stat.S_IMODE(sandbox.joinpath("test.txt").stat().st_mode))
        assert actual_mode == oct(0o600), f"Mode not applied: {actual_mode}"
    print("✓ test_fixture_modes_applied")


def test_apply_modes_missing_path_errors():
    """A mode declared for a path that does not exist is a hard error."""
    with tempfile.TemporaryDirectory() as d:
        sandbox = Path(d)
        try:
            apply_modes(sandbox, {"nope.txt": "0600"})
        except FixtureError:
            print("✓ test_apply_modes_missing_path_errors")
            return
    raise AssertionError("apply_modes should raise on missing path")


def test_safe_join_rejects_traversal():
    with tempfile.TemporaryDirectory() as d:
        sandbox = Path(d)
        for bad in ("../evil", "/etc/passwd", "~/.ssh", "a/../../b"):
            try:
                safe_join(sandbox, bad)
            except FixtureError:
                continue
            raise AssertionError(f"safe_join should reject {bad!r}")
    print("✓ test_safe_join_rejects_traversal")


def test_build_fixture_traversal_aborts_case():
    """A traversing fixture path fails the case instead of escaping the sandbox."""
    case = {"id": "t-traversal", "reference": "echo hi",
            "fixture": {"files": {"../escape.txt": "x"}}, "check": {"stdout": "hi\n"}}
    r = run(case)
    assert not r['passed'], "Traversing fixture should fail the case"
    assert 'error' in r and 'fixture' in r['error']
    print("✓ test_build_fixture_traversal_aborts_case")


def test_unknown_check_keys():
    case = {"id": "t-unknown-key", "reference": "echo test",
            "fixture": {}, "check": {"unknown_check": "value"}}
    r = run(case)
    assert not r['passed'], "Unknown check key should fail"
    assert 'unknown_check' in r['check_results']['unknown_check_keys']
    print("✓ test_unknown_check_keys")


def test_multiple_simultaneous_assertions():
    case = {"id": "t-multiple",
            "reference": "sh -c 'printf \"line1\\nline2\\n\" && echo done > output.txt'",
            "fixture": {},
            "check": {"stdout_lines_unordered": ["line1", "line2"],
                      "files": {"output.txt": "done\n"},
                      "no_extra_files": True}}
    r = run(case)
    assert r['passed'], f"All checks should pass: {r}"
    assert r['check_results']['stdout_lines_unordered'] is True
    assert r['check_results']['file:output.txt'] is True
    assert r['check_results']['no_extra_files'] is True
    print("✓ test_multiple_simultaneous_assertions")


def test_safe_fixture_paths():
    case = {"id": "t-path-safety", "reference": "printf 'test\\n'",
            "fixture": {"files": {"subdir/file.txt": "content"}},
            "check": {"stdout": "test\n"}}
    r = run(case)
    assert r['passed'], "Nested fixture path should stay in sandbox and pass"
    print("✓ test_safe_fixture_paths")


def test_output_directory_created():
    """main() must create the report's parent directory before writing."""
    with tempfile.TemporaryDirectory() as base:
        cases_dir = Path(base) / "cases"
        cases_dir.mkdir()
        (cases_dir / "eval_fit.jsonl").write_text(
            json.dumps({"id": "one", "reference": "printf 'x\\n'",
                        "fixture": {}, "check": {"stdout": "x\n"}}) + "\n")
        out_path = Path(base) / "deep" / "nested" / "report.json"
        import verify_references as m
        argv_backup = sys.argv
        try:
            sys.argv = ["verify_references.py", str(cases_dir), str(out_path)]
            rc = m.main()
        finally:
            sys.argv = argv_backup
        assert out_path.exists(), "Report must be written into a created directory"
        report = json.loads(out_path.read_text())
        assert report['summary']['total'] == 1
    print("✓ test_output_directory_created")


def main():
    print("Running verifier regression tests...")
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_') and callable(v)]
    for t in tests:
        t()
    print(f"\nAll {len(tests)} verifier regression tests passed.")


if __name__ == '__main__':
    main()
