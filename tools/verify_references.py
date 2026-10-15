#!/usr/bin/env python3
"""Verify learning64 references on macOS by running each against its fixture.

Must run on macOS with stock PATH. Creates a temporary directory for each case,
writes fixture files, runs the reference command, and checks all declared checks.
No user data is touched.

Output: JSON with per-case results and a summary.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def apply_modes(sandbox, modes):
    """Apply octal permission modes to fixture files."""
    for name, mode_str in modes.items():
        p = sandbox / name
        if p.exists():
            try:
                # Convert octal string to integer (e.g., "0600" -> 0o600)
                mode = int(mode_str, 8)
                p.chmod(mode)
            except (ValueError, OSError) as e:
                raise ValueError(f"Failed to set mode {mode_str} on {name}: {e}")


def run_one(case, stock_env):
    """Run a single reference against its fixture; return result dict."""
    fixture = case.get('fixture', {})
    check = case.get('check', {})
    result = {'id': case['id'], 'reference': case['reference'], 'passed': False}

    tmp_base = '/private/tmp' if sys.platform == 'darwin' else '/tmp'
    with tempfile.TemporaryDirectory(prefix=f'l64-{case["id"]}-', dir=tmp_base) as d:
        sandbox = Path(d)

        # Create fixture directories first
        for dirname in fixture.get('dirs', []):
            (sandbox / dirname).mkdir(parents=True, exist_ok=True)

        # Write fixture files
        for name, content in fixture.get('files', {}).items():
            p = sandbox / name
            p.parent.mkdir(parents=True, exist_ok=True)
            # Content uses Python string escapes; write as-is (already decoded from JSON)
            p.write_text(content)

        # Apply permission modes
        if 'modes' in fixture:
            apply_modes(sandbox, fixture['modes'])

        # Create symlinks
        for name, target in fixture.get('symlinks', {}).items():
            p = sandbox / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.symlink_to(target)

        # Run the reference command
        try:
            proc = subprocess.run(
                ['/bin/zsh', '-f', '-c', case['reference']],
                cwd=str(sandbox), env=stock_env,
                capture_output=True, text=True, timeout=10)
            result['returncode'] = proc.returncode
            result['stdout'] = proc.stdout
            result['stderr'] = proc.stderr
        except subprocess.TimeoutExpired:
            result['error'] = 'timeout'
            return result
        except Exception as e:
            result['error'] = str(e)
            return result

        # Track all check results
        check_results = {}
        all_passed = True

        # Check stdout exact match
        if 'stdout' in check:
            expected = check['stdout']
            if proc.stdout == expected:
                check_results['stdout'] = True
            else:
                check_results['stdout'] = False
                check_results['expected_stdout'] = expected
                check_results['actual_stdout'] = proc.stdout
                all_passed = False

        # Check stdout octal format
        if 'stdout_octal' in check:
            expected = check['stdout_octal']
            if proc.stdout.strip() == expected:
                check_results['stdout_octal'] = True
            else:
                check_results['stdout_octal'] = False
                check_results['expected_octal'] = expected
                check_results['actual_octal'] = proc.stdout.strip()
                all_passed = False

        # Check stdout contains inode of specific file
        if 'stdout_inode_of' in check:
            target_name = check['stdout_inode_of']
            target_path = sandbox / target_name
            if target_path.exists():
                import stat
                target_inode = target_path.stat().st_ino
                if str(target_inode) in proc.stdout:
                    check_results['stdout_inode_of'] = True
                else:
                    check_results['stdout_inode_of'] = False
                    check_results['expected_inode'] = str(target_inode)
                    check_results['actual_stdout'] = proc.stdout
                    all_passed = False
            else:
                check_results['stdout_inode_of'] = False
                check_results['inode_target_missing'] = target_name
                all_passed = False

        # Check stdout contains all lines in any order
        if 'stdout_lines_unordered' in check:
            expected_lines = set(check['stdout_lines_unordered'])
            actual_lines = set(proc.stdout.strip().split('\n')) if proc.stdout.strip() else set()
            if expected_lines == actual_lines:
                check_results['stdout_lines_unordered'] = True
            else:
                check_results['stdout_lines_unordered'] = False
                check_results['expected_lines'] = sorted(expected_lines)
                check_results['actual_lines'] = sorted(actual_lines)
                check_results['missing_lines'] = sorted(expected_lines - actual_lines)
                check_results['extra_lines'] = sorted(actual_lines - expected_lines)
                all_passed = False

        # Check stdout contains stat fields for specific file
        if 'stdout_stat_fields' in check:
            spec = check['stdout_stat_fields']
            target_name = spec['path']
            target_path = sandbox / target_name
            if target_path.exists():
                import stat
                st = target_path.stat()
                field_map = {
                    'size': str(st.st_size),
                    'inode': str(st.st_ino),
                    'mode': oct(st.st_mode),
                    'nlink': str(st.st_nlink),
                }
                # Check that all requested fields appear in stdout
                missing_fields = []
                for field in spec['fields']:
                    if field in field_map:
                        if field_map[field] not in proc.stdout:
                            missing_fields.append(field)
                    else:
                        missing_fields.append(f"unknown_field:{field}")
                if not missing_fields:
                    check_results['stdout_stat_fields'] = True
                else:
                    check_results['stdout_stat_fields'] = False
                    check_results['missing_stat_fields'] = missing_fields
                    check_results['actual_stdout'] = proc.stdout
                    all_passed = False
            else:
                check_results['stdout_stat_fields'] = False
                check_results['stat_target_missing'] = target_name
                all_passed = False

        # Check resulting file contents
        if 'files' in check:
            for fname, expected_content in check['files'].items():
                actual_path = sandbox / fname
                if actual_path.exists():
                    actual_content = actual_path.read_text()
                    if actual_content == expected_content:
                        check_results[f'file:{fname}'] = True
                    else:
                        check_results[f'file:{fname}'] = False
                        check_results[f'file:{fname}:expected'] = expected_content
                        check_results[f'file:{fname}:actual'] = actual_content
                        all_passed = False
                else:
                    check_results[f'file:{fname}'] = False
                    check_results[f'file:{fname}:missing'] = True
                    all_passed = False

        # Check for no extra files
        if 'no_extra_files' in check and check['no_extra_files']:
            # List all files in sandbox
            all_files = set()
            for p in sandbox.rglob('*'):
                if p.is_file():
                    rel = str(p.relative_to(sandbox))
                    all_files.add(rel)

            # Known fixture files
            known_files = set(fixture.get('files', {}).keys())
            known_files.update(fixture.get('symlinks', {}).keys())

            # Also include any files expected in check.files
            if 'files' in check:
                known_files.update(check['files'].keys())

            extra_files = all_files - known_files
            if not extra_files:
                check_results['no_extra_files'] = True
            else:
                check_results['no_extra_files'] = False
                check_results['extra_files'] = sorted(extra_files)
                all_passed = False

        # Check stdout_contains (legacy)
        if 'stdout_contains' in check:
            if check['stdout_contains'] in proc.stdout:
                check_results['stdout_contains'] = True
            else:
                check_results['stdout_contains'] = False
                check_results['expected_contains'] = check['stdout_contains']
                all_passed = False

        # Check file_exists (legacy)
        if 'file_exists' in check:
            path = sandbox / check['file_exists']
            if path.exists():
                check_results['file_exists'] = True
            else:
                check_results['file_exists'] = False
                check_results['file_missing'] = check['file_exists']
                all_passed = False

        # Check file_content (legacy)
        if 'file_content' in check:
            for fname, expected in check['file_content'].items():
                actual = (sandbox / fname).read_text() if (sandbox / fname).exists() else None
                if actual == expected:
                    check_results[f'file_content:{fname}'] = True
                else:
                    check_results[f'file_content:{fname}'] = False
                    check_results[f'file_content:{fname}:expected'] = expected
                    check_results[f'file_content:{fname}:actual'] = actual
                    all_passed = False

        # Detect unknown check keys
        known_keys = {
            'stdout', 'stdout_octal', 'stdout_inode_of', 'stdout_lines_unordered',
            'stdout_stat_fields', 'files', 'no_extra_files', 'stdout_contains',
            'file_exists', 'file_content'
        }
        unknown_keys = set(check.keys()) - known_keys
        if unknown_keys:
            check_results['unknown_check_keys'] = sorted(unknown_keys)
            all_passed = False

        # Default behavior: if no checks declared, require success
        if not check:
            if proc.returncode == 0:
                check_results['implicit_success'] = True
            else:
                check_results['implicit_success'] = False
                check_results['nonzero_exit'] = proc.returncode
                all_passed = False
        else:
            # If checks are declared, still require zero exit code unless explicitly allowed
            # (current dataset has no explicit nonzero-exit checks)
            if proc.returncode != 0:
                check_results['nonzero_exit'] = proc.returncode
                all_passed = False

        # Store check results
        result['check_results'] = check_results
        result['passed'] = all_passed

    return result


def main():
    if sys.platform != 'darwin':
        print('WARNING: not on macOS; results may not match production', file=sys.stderr)
        # Continue anyway for testing

    cases_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('data/diagnostic-learning64')
    tmp_base = '/private/tmp' if sys.platform == 'darwin' else '/tmp'
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(tmp_base) / 'whatisit-learning64' / 'reference-verification.json'

    stock_env = dict(os.environ, PATH='/usr/bin:/bin:/usr/sbin:/sbin')
    # Remove anything that might affect command behavior
    for key in ('WHATISIT_MODEL', 'WHATISIT_LLAMA_SERVER', 'WHATISIT_DATA_DIR'):
        stock_env.pop(key, None)

    all_cases = []
    for name in ('eval_fit', 'eval_paraphrase', 'eval_operand', 'eval_composition'):
        path = cases_dir / f'{name}.jsonl'
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if line.strip():
                all_cases.append(json.loads(line))

    # Deduplicate by reference + fixture (many cases share the same reference)
    seen = {}
    unique_cases = []
    for case in all_cases:
        key = (case['reference'], json.dumps(case.get('fixture', {}), sort_keys=True))
        if key not in seen:
            seen[key] = case['id']
            unique_cases.append(case)

    results = []
    passed = failed = 0
    for case in unique_cases:
        r = run_one(case, stock_env)
        results.append(r)
        if r['passed']:
            passed += 1
            print(f'  OK  {r["id"]}: {r["reference"]}', flush=True)
        else:
            failed += 1
            print(f'  FAIL {r["id"]}: {r["reference"]}', flush=True)
            if 'check_results' in r:
                for check_key, check_val in r['check_results'].items():
                    if check_val is False or isinstance(check_val, list):
                        print(f'       {check_key}: {check_val}', flush=True)

    summary = {'total': len(results), 'passed': passed, 'failed': failed,
               'all_passed': failed == 0}
    output = {'summary': summary, 'results': results}
    out_path.write_text(json.dumps(output, indent=2) + '\n')
    print(f'\nSummary: {passed}/{len(results)} passed, {failed} failed')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
