#!/usr/bin/env python3
"""Verify learning64 references on macOS by running each against its fixture.

Must run on macOS with stock PATH. Creates a temporary directory for each case,
writes fixture files, runs the reference command, and checks stdout against the
declared check. No user data is touched.

Output: JSON with per-case results and a summary.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run_one(case, stock_env):
    """Run a single reference against its fixture; return result dict."""
    fixture = case.get('fixture', {})
    check = case.get('check', {})
    result = {'id': case['id'], 'reference': case['reference'], 'passed': False}

    with tempfile.TemporaryDirectory(prefix=f'l64-{case["id"]}-', dir='/private/tmp') as d:
        sandbox = Path(d)
        # Write fixture files
        for name, content in fixture.get('files', {}).items():
            p = sandbox / name
            p.parent.mkdir(parents=True, exist_ok=True)
            # Content uses Python string escapes; write as-is (already decoded from JSON)
            p.write_text(content)
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

        # Check stdout if declared
        if 'stdout' in check:
            if proc.stdout == check['stdout']:
                result['passed'] = True
            else:
                result['expected_stdout'] = check['stdout']
                result['stdout_match'] = False
        elif 'stdout_contains' in check:
            if check['stdout_contains'] in proc.stdout:
                result['passed'] = True
            else:
                result['stdout_match'] = False
        else:
            # No stdout check; just verify it ran successfully
            result['passed'] = proc.returncode == 0

        # Check file state if declared
        if 'file_exists' in check:
            path = sandbox / check['file_exists']
            if not path.exists():
                result['passed'] = False
                result['file_missing'] = check['file_exists']
        if 'file_content' in check:
            for fname, expected in check['file_content'].items():
                actual = (sandbox / fname).read_text() if (sandbox / fname).exists() else None
                if actual != expected:
                    result['passed'] = False
                    result['file_mismatch'] = fname

    return result


def main():
    if sys.platform != 'darwin':
        print('ERROR: must run on macOS', file=sys.stderr)
        return 1

    cases_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('data/diagnostic-learning64')
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('/private/tmp/whatisit-learning64/reference-verification.json')

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
            if 'stdout' in r:
                print(f'       stdout={r["stdout"]!r}', flush=True)
            if 'expected_stdout' in r:
                print(f'       expected={r["expected_stdout"]!r}', flush=True)

    summary = {'total': len(results), 'passed': passed, 'failed': failed,
               'all_passed': failed == 0}
    output = {'summary': summary, 'results': results}
    out_path.write_text(json.dumps(output, indent=2) + '\n')
    print(f'\nSummary: {passed}/{len(results)} passed, {failed} failed')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
