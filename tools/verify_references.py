#!/usr/bin/env python3
"""Verify learning64 references on macOS by running each against its fixture.

Must run on macOS with stock PATH. Creates a temporary directory for each case,
writes fixture files, runs the reference command under ``/bin/zsh -f``, and then
checks *every* declared assertion in the frozen dataset. No user data is touched.

The verifier deliberately runs the *reference* command from the frozen dataset
(human-authored), never a model-generated command. Its job is to prove that the
declared reference produces exactly the declared expected output on stock macOS.

Each declared check is enforced strictly:

- ``stdout``                : exact byte-for-byte stdout match.
- ``stdout_octal``          : exact match after ``strip()``.
- ``stdout_inode_of``       : the target's inode must appear as a whole token in
                              stdout (substring matching would false-positive on
                              larger numbers that embed the inode digits).
- ``stdout_lines_unordered``: multiset (duplicate-preserving) line comparison, not
                              a plain set (which would discard multiplicity).
- ``stdout_stat_fields``    : the requested stat fields must be the *only*
                              whitespace-separated tokens, in the requested order.
- ``files``                 : exact resulting file content.
- ``no_extra_files``        : no new files, directories, or symlinks beyond the
                              declared fixture/expected set.
- ``fixture.modes``         : octal modes applied; a declared-but-missing path is
                              an error, never silently skipped.
- ``fixture.dirs``/``files``/``symlinks`` are created before execution.
- All fixture and check paths are validated to remain inside the sandbox.
- Non-zero exit fails any case that declares checks (none currently allow it).
- Unknown check keys are reported explicitly (never ignored).

Output: JSON report with provenance (dataset + implementation hashes, platform,
PATH) and per-case stdout/stderr/exit/check results.
"""
import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path


class FixtureError(ValueError):
    """Raised for unsafe or structurally-invalid fixture definitions."""


def safe_join(sandbox: Path, name: str) -> Path:
    """Resolve *name* inside *sandbox*, rejecting anything that escapes it.

    Guards against path-traversal and absolute-path fixture entries.
    """
    if not isinstance(name, str) or not name:
        raise FixtureError(f"invalid path name: {name!r}")
    # Refuse absolute paths and home/expansion tricks up front.
    if name.startswith('/') or name.startswith('~') or '\x00' in name:
        raise FixtureError(f"unsafe fixture path: {name!r}")
    candidate = (sandbox / name)
    # Resolve without requiring existence, then check containment.
    sandbox_resolved = sandbox.resolve()
    candidate_resolved = candidate.resolve()
    try:
        candidate_resolved.relative_to(sandbox_resolved)
    except ValueError:
        raise FixtureError(f"fixture path escapes sandbox: {name!r}")
    return candidate


def apply_modes(sandbox, modes):
    """Apply octal permission modes to fixture files.

    A declared path that does not exist is a hard error (previous behaviour of
    silently skipping it hid fixture/output mismatches).
    """
    for name, mode_str in modes.items():
        p = safe_join(sandbox, name)
        if not p.exists():
            raise FixtureError(f"mode declared for missing fixture path: {name!r}")
        try:
            mode = int(mode_str, 8)  # e.g. "0600" -> 0o600
        except ValueError as e:
            raise FixtureError(f"invalid mode {mode_str!r} for {name!r}: {e}")
        try:
            p.chmod(mode)
        except OSError as e:
            raise FixtureError(f"failed to set mode {mode_str} on {name}: {e}")


def build_fixture(sandbox: Path, fixture: dict):
    """Create directories, files, modes, and symlinks for a case."""
    # Directories first (a declared dir may be named like a file to test -type f).
    for dirname in fixture.get('dirs', []):
        (safe_join(sandbox, dirname)).mkdir(parents=True, exist_ok=True)

    # Files (creating parents as needed).
    for name, content in fixture.get('files', {}).items():
        p = safe_join(sandbox, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)

    # Permission modes.
    if 'modes' in fixture:
        apply_modes(sandbox, fixture['modes'])

    # Symlinks (validated safe; may dangle, so create after files).
    for name, target in fixture.get('symlinks', {}).items():
        p = safe_join(sandbox, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.symlink_to(target)


def iter_entries(sandbox: Path):
    """Yield every filesystem entry (file, dir, symlink) relative to sandbox."""
    for p in sorted(sandbox.rglob('*')):
        yield str(p.relative_to(sandbox))


def _extra_check(expected_roots, sandbox: Path):
    """Compute the set of paths not accounted for by the allowed set.

    ``expected_roots`` is an iterable of allowed relative paths. Parent
    directories of allowed paths are also allowed so that ordinary nesting is
    not flagged. Directories, files, and symlinks are all considered.
    """
    allowed = set()
    for rel in expected_roots:
        allowed.add(str(rel))
        parent = Path(rel).parent
        while str(parent) not in ('', '.'):
            allowed.add(str(parent))
            parent = parent.parent
    present = set(iter_entries(sandbox))
    return sorted(present - allowed)


def evaluate_checks(case: dict, sandbox: Path, proc):
    """Evaluate every declared check; return (check_results, all_passed)."""
    fixture = case.get('fixture', {})
    check = case.get('check', {})
    check_results = {}
    all_passed = True

    def fail(key, **extra):
        nonlocal all_passed
        check_results[key] = False
        check_results.update(extra)
        all_passed = False

    # Exact stdout.
    if 'stdout' in check:
        if proc.stdout == check['stdout']:
            check_results['stdout'] = True
        else:
            fail('stdout', expected_stdout=check['stdout'], actual_stdout=proc.stdout)

    # Octal permission string.
    if 'stdout_octal' in check:
        if proc.stdout.strip() == check['stdout_octal']:
            check_results['stdout_octal'] = True
        else:
            fail('stdout_octal', expected_octal=check['stdout_octal'],
                 actual_octal=proc.stdout.strip())

    # Inode must appear as a full whitespace-delimited token.
    if 'stdout_inode_of' in check:
        target_name = check['stdout_inode_of']
        target_path = safe_join(sandbox, target_name)
        if target_path.exists():
            target_inode = str(target_path.stat().st_ino)
            tokens = proc.stdout.split()
            if target_inode in tokens:
                check_results['stdout_inode_of'] = True
            else:
                fail('stdout_inode_of', expected_inode=target_inode,
                     actual_stdout=proc.stdout, actual_tokens=tokens)
        else:
            fail('stdout_inode_of', inode_target_missing=target_name)

    # Unordered lines with duplicate multiplicity preserved.
    if 'stdout_lines_unordered' in check:
        expected_counter = Counter(check['stdout_lines_unordered'])
        actual_stripped = proc.stdout.strip('\n')
        actual_counter = Counter(actual_stripped.split('\n') if actual_stripped else [])
        if expected_counter == actual_counter:
            check_results['stdout_lines_unordered'] = True
        else:
            missing = list((expected_counter - actual_counter).elements())
            extra = list((actual_counter - expected_counter).elements())
            fail('stdout_lines_unordered',
                 expected_lines=sorted(expected_counter.elements()),
                 actual_lines=sorted(actual_counter.elements()),
                 missing_lines=sorted(missing), extra_lines=sorted(extra))

    # Stat fields: exact, ordered, and the only tokens present.
    if 'stdout_stat_fields' in check:
        spec = check['stdout_stat_fields']
        target_name = spec['path']
        target_path = safe_join(sandbox, target_name)
        if target_path.exists():
            import stat as _stat
            st = target_path.stat()
            field_map = {
                'size': str(st.st_size),
                'inode': str(st.st_ino),
                'mode': oct(_stat.S_IMODE(st.st_mode)),
                'nlink': str(st.st_nlink),
            }
            unknown = [f for f in spec['fields'] if f not in field_map]
            if unknown:
                fail('stdout_stat_fields', unknown_fields=unknown)
            else:
                expected_tokens = [field_map[f] for f in spec['fields']]
                actual_tokens = proc.stdout.split()
                if actual_tokens == expected_tokens:
                    check_results['stdout_stat_fields'] = True
                else:
                    fail('stdout_stat_fields',
                         expected_fields=spec['fields'],
                         expected_tokens=expected_tokens,
                         actual_tokens=actual_tokens,
                         actual_stdout=proc.stdout)
        else:
            fail('stdout_stat_fields', stat_target_missing=target_name)

    # Resulting file contents.
    if 'files' in check:
        for fname, expected_content in check['files'].items():
            actual_path = safe_join(sandbox, fname)
            if actual_path.exists():
                actual_content = actual_path.read_text()
                if actual_content == expected_content:
                    check_results[f'file:{fname}'] = True
                else:
                    fail(f'file:{fname}', **{f'file:{fname}:expected': expected_content,
                                             f'file:{fname}:actual': actual_content})
            else:
                fail(f'file:{fname}', **{f'file:{fname}:missing': True})

    # No new files/dirs/symlinks beyond the declared set.
    if check.get('no_extra_files'):
        allowed = set(fixture.get('files', {}).keys())
        allowed |= set(fixture.get('dirs', {}).keys() if isinstance(fixture.get('dirs'), dict)
                       else fixture.get('dirs', []))
        allowed |= set(fixture.get('symlinks', {}).keys())
        allowed |= set(check.get('files', {}).keys())
        extra = _extra_check(allowed, sandbox)
        if not extra:
            check_results['no_extra_files'] = True
        else:
            fail('no_extra_files', extra_paths=extra)

    # Legacy: substring containment.
    if 'stdout_contains' in check:
        if check['stdout_contains'] in proc.stdout:
            check_results['stdout_contains'] = True
        else:
            fail('stdout_contains', expected_contains=check['stdout_contains'],
                 actual_stdout=proc.stdout)

    # Legacy: path existence.
    if 'file_exists' in check:
        path = safe_join(sandbox, check['file_exists'])
        if path.exists():
            check_results['file_exists'] = True
        else:
            fail('file_exists', file_missing=check['file_exists'])

    # Legacy: file content.
    if 'file_content' in check:
        for fname, expected in check['file_content'].items():
            actual_path = safe_join(sandbox, fname)
            actual = actual_path.read_text() if actual_path.exists() else None
            if actual == expected:
                check_results[f'file_content:{fname}'] = True
            else:
                fail(f'file_content:{fname}',
                     **{f'file_content:{fname}:expected': expected,
                        f'file_content:{fname}:actual': actual})

    # Unknown check keys are explicit failures.
    known_keys = {
        'stdout', 'stdout_octal', 'stdout_inode_of', 'stdout_lines_unordered',
        'stdout_stat_fields', 'files', 'no_extra_files', 'stdout_contains',
        'file_exists', 'file_content',
    }
    unknown_keys = set(check.keys()) - known_keys
    if unknown_keys:
        check_results['unknown_check_keys'] = sorted(unknown_keys)
        all_passed = False

    # Exit-code policy.
    if not check:
        if proc.returncode == 0:
            check_results['implicit_success'] = True
        else:
            check_results['implicit_success'] = False
            check_results['nonzero_exit'] = proc.returncode
            all_passed = False
    else:
        if proc.returncode != 0:
            check_results['nonzero_exit'] = proc.returncode
            all_passed = False

    return check_results, all_passed


def run_one(case, stock_env, tmp_base):
    """Run a single reference against its fixture; return a result dict."""
    fixture = case.get('fixture', {})
    result = {'id': case['id'], 'reference': case['reference'], 'passed': False}

    d = tempfile.mkdtemp(prefix=f'l64-{case["id"]}-', dir=tmp_base)
    sandbox = Path(d)
    try:
        build_fixture(sandbox, fixture)
    except FixtureError as e:
        result['error'] = f'fixture: {e}'
        _cleanup(sandbox)
        return result

    try:
        proc = subprocess.run(
            ['/bin/zsh', '-f', '-c', case['reference']],
            cwd=str(sandbox), env=stock_env,
            capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired as e:
        result['error'] = 'timeout'
        result['stdout'] = e.stdout or ''
        result['stderr'] = e.stderr or ''
        _cleanup(sandbox)
        return result
    except Exception as e:  # noqa: BLE001 - surface any runtime failure
        result['error'] = str(e)
        _cleanup(sandbox)
        return result

    result['returncode'] = proc.returncode
    result['stdout'] = proc.stdout
    result['stderr'] = proc.stderr

    try:
        check_results, all_passed = evaluate_checks(case, sandbox, proc)
    except FixtureError as e:
        result['error'] = f'check: {e}'
        _cleanup(sandbox)
        return result

    result['check_results'] = check_results
    result['passed'] = all_passed
    _cleanup(sandbox)
    return result


def _cleanup(path: Path):
    import shutil
    shutil.rmtree(path, ignore_errors=True)


def sha256_file(p: Path):
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def load_cases(cases_dir: Path):
    all_cases = []
    for name in ('eval_fit', 'eval_paraphrase', 'eval_operand', 'eval_composition'):
        path = cases_dir / f'{name}.jsonl'
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if line.strip():
                all_cases.append(json.loads(line))
    return all_cases


def dedupe(all_cases):
    """Deduplicate by (reference, fixture); many groups share one reference."""
    seen = {}
    unique = []
    for case in all_cases:
        key = (case['reference'], json.dumps(case.get('fixture', {}), sort_keys=True))
        if key not in seen:
            seen[key] = case['id']
            unique.append(case)
    return unique


def verify_manifest(cases_dir: Path):
    """Return dataset hash verification against manifest.json, if present."""
    manifest = cases_dir / 'manifest.json'
    info = {'manifest_present': manifest.exists(), 'files': {}}
    if not manifest.exists():
        return info
    data = json.loads(manifest.read_text())
    info['declared_status'] = data.get('status')
    for fname, expected in data.get('sha256', {}).items():
        p = cases_dir / fname
        if not p.exists():
            info['files'][fname] = {'match': False, 'reason': 'missing'}
            continue
        actual = sha256_file(p)
        info['files'][fname] = {'match': actual == expected,
                                'declared': expected, 'actual': actual}
    info['all_match'] = all(v.get('match') for v in info['files'].values())
    return info


def main():
    if sys.platform != 'darwin':
        print('WARNING: not on macOS; BSD reference semantics will not hold.',
              file=sys.stderr)

    cases_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('data/diagnostic-learning64')
    default_tmp = '/private/tmp' if sys.platform == 'darwin' else '/tmp'
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path('/tmp/whatisit-learning64') / 'reference-verification.json'
    tmp_base = out_path.parent if sys.platform == 'darwin' else default_tmp

    # Ensure the output directory exists before writing the report.
    out_path.parent.mkdir(parents=True, exist_ok=True)

    stock_env = dict(os.environ, PATH='/usr/bin:/bin:/usr/sbin:/sbin')
    for key in ('WHATISIT_MODEL', 'WHATISIT_LLAMA_SERVER', 'WHATISIT_DATA_DIR'):
        stock_env.pop(key, None)

    dataset_hashes = {f.name: sha256_file(f) for f in sorted(cases_dir.glob('*.jsonl'))}
    manifest_check = verify_manifest(cases_dir)

    all_cases = load_cases(cases_dir)
    unique_cases = dedupe(all_cases)

    provenance = {
        'platform': platform.platform(),
        'macver': platform.mac_ver()[0] if sys.platform == 'darwin' else None,
        'python': sys.version.split()[0],
        'machine': platform.machine(),
        'stock_PATH': stock_env['PATH'],
        'shell': '/bin/zsh -f',
        'run_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'verifier_sha256': sha256_file(Path(__file__).resolve()),
        'dataset_files_sha256': dataset_hashes,
        'manifest_check': manifest_check,
        'total_cases_loaded': len(all_cases),
        'unique_cases': len(unique_cases),
    }

    results = []
    passed = failed = 0
    for case in unique_cases:
        r = run_one(case, stock_env, str(tmp_base))
        results.append(r)
        if r['passed']:
            passed += 1
            print(f'  OK   {r["id"]}: {r["reference"]}', flush=True)
        else:
            failed += 1
            print(f'  FAIL {r["id"]}: {r["reference"]}', flush=True)
            if 'error' in r:
                print(f'       error: {r["error"]}', flush=True)
            for check_key, check_val in r.get('check_results', {}).items():
                if check_val is False or isinstance(check_val, list):
                    print(f'       {check_key}: {check_val}', flush=True)

    summary = {'total': len(results), 'passed': passed, 'failed': failed,
               'all_passed': failed == 0,
               'manifest_all_match': manifest_check.get('all_match')}
    output = {'summary': summary, 'provenance': provenance, 'results': results}
    out_path.write_text(json.dumps(output, indent=2) + '\n')
    print(f'\nSummary: {passed}/{len(results)} passed, {failed} failed')
    print(f'Manifest hashes all match: {manifest_check.get("all_match")}')
    print(f'Report written to {out_path}')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
