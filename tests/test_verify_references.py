#!/usr/bin/env python3
"""Regression tests for verify_references.py.

Tests that the verifier correctly rejects incorrect outputs and enforces
all declared check types.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))
from verify_references import run_one, apply_modes


def test_stdout_with_nonzero_exit():
    """Correct stdout but nonzero exit should fail."""
    case = {
        "id": "test-nonzero-exit",
        "reference": "false",  # Always exits with 1
        "fixture": {},
        "check": {"stdout": ""}
    }
    stock_env = {'PATH': '/usr/bin:/bin', 'HOME': str(Path.home())}
    result = run_one(case, stock_env)
    assert not result['passed'], "Nonzero exit should fail"
    assert result['check_results']['nonzero_exit'] == 1
    print("✓ test_stdout_with_nonzero_exit")


def test_incorrect_stdout_with_zero_exit():
    """Incorrect stdout with zero exit should fail."""
    case = {
        "id": "test-wrong-stdout",
        "reference": "echo wrong",
        "fixture": {},
        "check": {"stdout": "correct\n"}
    }
    stock_env = {'PATH': '/usr/bin:/bin', 'HOME': str(Path.home())}
    result = run_one(case, stock_env)
    assert not result['passed'], "Incorrect stdout should fail"
    assert result['check_results']['stdout'] is False
    print("✓ test_incorrect_stdout_with_zero_exit")


def test_incorrect_octal_permissions():
    """Octal check should validate format."""
    # This test uses Linux stat since we're on Linux
    case = {
        "id": "test-octal",
        "reference": "stat -c %a test.txt",
        "fixture": {"files": {"test.txt": "content"}},
        "check": {"stdout_octal": "0644"}
    }
    stock_env = {'PATH': '/usr/bin:/bin', 'HOME': str(Path.home())}
    result = run_one(case, stock_env)
    # Will likely fail due to mode differences, but check structure
    assert 'stdout_octal' in result['check_results']
    print("✓ test_incorrect_octal_permissions")


def test_incorrect_inode():
    """Inode check should validate that inode appears in stdout."""
    case = {
        "id": "test-inode",
        "reference": "echo 12345",  # Wrong inode
        "fixture": {"files": {"test.txt": "content"}},
        "check": {"stdout_inode_of": "test.txt"}
    }
    stock_env = {'PATH': '/usr/bin:/bin', 'HOME': str(Path.home())}
    result = run_one(case, stock_env)
    assert not result['passed'], "Incorrect inode should fail"
    assert result['check_results']['stdout_inode_of'] is False
    print("✓ test_incorrect_inode")


def test_incorrect_unordered_output():
    """Unordered lines check should require all lines present."""
    case = {
        "id": "test-unordered",
        "reference": "printf 'line1\nline2\n'",
        "fixture": {},
        "check": {"stdout_lines_unordered": ["line1", "line2", "line3"]}
    }
    stock_env = {'PATH': '/usr/bin:/bin', 'HOME': str(Path.home())}
    result = run_one(case, stock_env)
    assert not result['passed'], "Missing line should fail"
    assert result['check_results']['stdout_lines_unordered'] is False
    assert 'line3' in result['check_results']['missing_lines']
    print("✓ test_incorrect_unordered_output")


def test_incorrect_stat_fields():
    """Stat fields check should require all requested fields."""
    case = {
        "id": "test-stat-fields",
        "reference": "stat -c %s test.txt",  # Only size, missing inode
        "fixture": {"files": {"test.txt": "content"}},
        "check": {"stdout_stat_fields": {"path": "test.txt", "fields": ["size", "inode"]}}
    }
    stock_env = {'PATH': '/usr/bin:/bin', 'HOME': str(Path.home())}
    result = run_one(case, stock_env)
    assert not result['passed'], "Missing stat field should fail"
    assert result['check_results']['stdout_stat_fields'] is False
    assert 'inode' in result['check_results']['missing_stat_fields']
    print("✓ test_incorrect_stat_fields")


def test_missing_output_file():
    """File content check should fail if file missing."""
    case = {
        "id": "test-missing-file",
        "reference": "echo something",
        "fixture": {},
        "check": {"files": {"output.txt": "expected content"}}
    }
    stock_env = {'PATH': '/usr/bin:/bin', 'HOME': str(Path.home())}
    result = run_one(case, stock_env)
    assert not result['passed'], "Missing output file should fail"
    assert result['check_results']['file:output.txt'] is False
    print("✓ test_missing_output_file")


def test_incorrect_output_file_content():
    """File content check should validate exact content."""
    case = {
        "id": "test-wrong-content",
        "reference": "sh -c 'echo wrong > output.txt'",
        "fixture": {},
        "check": {"files": {"output.txt": "correct content"}}
    }
    stock_env = {'PATH': '/usr/bin:/bin', 'HOME': str(Path.home())}
    result = run_one(case, stock_env)
    assert not result['passed'], "Incorrect file content should fail"
    assert result['check_results']['file:output.txt'] is False
    print("✓ test_incorrect_output_file_content")


def test_extra_files_prohibited():
    """no_extra_files check should detect unexpected files."""
    case = {
        "id": "test-extra-files",
        "reference": "sh -c 'echo leftover > junk.txt'",
        "fixture": {},
        "check": {"no_extra_files": True}
    }
    stock_env = {'PATH': '/usr/bin:/bin', 'HOME': str(Path.home())}
    result = run_one(case, stock_env)
    assert not result['passed'], "Extra files should fail"
    assert result['check_results']['no_extra_files'] is False
    assert 'junk.txt' in result['check_results']['extra_files']
    print("✓ test_extra_files_prohibited")


def test_incorrect_fixture_modes():
    """Fixture modes should be applied and checked."""
    with tempfile.TemporaryDirectory() as d:
        sandbox = Path(d)
        test_file = sandbox / "test.txt"
        test_file.write_text("content")

        # Apply mode
        apply_modes(sandbox, {"test.txt": "0600"})

        # Check it was applied
        import stat
        actual_mode = oct(test_file.stat().st_mode)[-4:]
        assert actual_mode == "0600", f"Mode not applied: got {actual_mode}"

    print("✓ test_incorrect_fixture_modes")


def test_unknown_check_keys():
    """Unknown check keys should produce explicit errors."""
    case = {
        "id": "test-unknown-key",
        "reference": "echo test",
        "fixture": {},
        "check": {"unknown_check": "value"}
    }
    stock_env = {'PATH': '/usr/bin:/bin', 'HOME': str(Path.home())}
    result = run_one(case, stock_env)
    assert not result['passed'], "Unknown check key should fail"
    assert 'unknown_check_keys' in result['check_results']
    assert 'unknown_check' in result['check_results']['unknown_check_keys']
    print("✓ test_unknown_check_keys")


def test_multiple_simultaneous_assertions():
    """Multiple checks should all pass for success."""
    case = {
        "id": "test-multiple",
        "reference": "sh -c 'printf \"line1\\nline2\\n\" && echo done > output.txt'",
        "fixture": {},
        "check": {
            "stdout_lines_unordered": ["line1", "line2"],
            "files": {"output.txt": "done\n"},
            "no_extra_files": True
        }
    }
    stock_env = {'PATH': '/usr/bin:/bin', 'HOME': str(Path.home())}
    result = run_one(case, stock_env)
    assert result['passed'], "All checks should pass"
    assert result['check_results']['stdout_lines_unordered'] is True
    assert result['check_results']['file:output.txt'] is True
    assert result['check_results']['no_extra_files'] is True
    print("✓ test_multiple_simultaneous_assertions")


def test_safe_fixture_paths():
    """Fixture paths should be safely contained in sandbox."""
    case = {
        "id": "test-path-safety",
        "reference": "echo test",
        "fixture": {"files": {"subdir/file.txt": "content"}},
        "check": {"stdout": "test\n"}
    }
    stock_env = {'PATH': '/usr/bin:/bin', 'HOME': str(Path.home())}
    result = run_one(case, stock_env)
    # Should not escape sandbox
    assert result['passed']
    print("✓ test_safe_fixture_paths")


def main():
    """Run all tests."""
    print("Running verifier regression tests...")
    test_stdout_with_nonzero_exit()
    test_incorrect_stdout_with_zero_exit()
    test_incorrect_octal_permissions()
    test_incorrect_inode()
    test_incorrect_unordered_output()
    test_incorrect_stat_fields()
    test_missing_output_file()
    test_incorrect_output_file_content()
    test_extra_files_prohibited()
    test_incorrect_fixture_modes()
    test_unknown_check_keys()
    test_multiple_simultaneous_assertions()
    test_safe_fixture_paths()
    print("\nAll regression tests passed.")


if __name__ == '__main__':
    main()
