#!/usr/bin/env python3
"""Compare model-generated commands against their references on macOS fixtures.

This tool exists to produce *evidence* for semantic adjudication without ever
trusting a model-generated command blindly. For each candidate it recreates the
case's frozen fixture inside a disposable sandbox under ``/private/tmp``, runs
the reference and then the candidate in a fresh sandbox, and reports stdout,
exit status, stderr, and resulting file state for both.

SAFETY: only candidates that pass a strict allowlist scan are executed; every
scanned/model output is run with cwd=sandbox and stdin=/dev/null. Candidates that
reference absolute/system paths, a wrong tool (shortcuts/man/history), or any
dangerous construct are marked ``executable: false`` and reported for static
adjudication only -- nothing destructive is ever run.

This tool does NOT feed results back into training or scoring automatically; a
human/inspector reads the evidence and assigns a verdict.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_references import build_fixture, FixtureError

# Tools that are safe to run for read/report or in-place edit on a fixture.
ALLOWED_TOOLS = {
    'grep', 'egrep', 'fgrep', 'sort', 'cut', 'find', 'stat', 'head', 'tail',
    'sed', 'awk', 'gawk', 'uniq', 'wc', 'tr', 'readlink', 'shasum',
    'sha256sum', 'date', 'printf', 'echo', 'cat', 'column', 'nl', 'rev',
    'od', 'ls', 'tac', 'comm', 'join', 'tee',
}

# Substrings that indicate escape, destructive, privileged, or wrong-tool ops.
# Compared case-insensitively.
DENIED_SUBSTRINGS_RAW = [
    '~', '$home', '$histfile', '$ifs', '$path', '/etc', '/var', '/system',
    '/users', '/library', '/private', '/dev', '/tmp', '/opt', 'sudo', 'curl',
    'wget', 'ssh', 'scp', 'sftp', 'nc ', 'launchctl', 'osascript', 'defaults',
    'reboot', 'shutdown', 'fdisk', 'dd ', 'mkfs', 'mkfile', 'truncate', 'shred',
    'rm ', 'rmdir', 'chmod', 'chown', 'chgrp', 'kill', 'killall', 'eval',
    '| sh', '|sh', '| bash', '|bash', '| zsh', '|zsh', 'tee/', '> /',
    'shortcuts', 'history', ':(){',
]
DENIED_SUBSTRINGS = [s.lower() for s in DENIED_SUBSTRINGS_RAW]

# Words we refuse to run as a leading command (wrong tool / interactive).
DENIED_FIRST_WORDS = {'shortcuts', 'man', 'history', 'sudo'}


def _pipeline_stages(cmd):
    """Split a command into pipeline/statement stages, respecting quotes,
    $(...), <(...), and `...` so separators inside them are not split points."""
    stages, cur = [], []
    i, n = 0, len(cmd)
    in_s = in_d = in_bt = False
    depth = 0
    while i < n:
        c = cmd[i]
        if in_s:
            cur.append(c)
            if c == "'":
                in_s = False
            i += 1
            continue
        if in_d:
            cur.append(c)
            if c == '\\' and i + 1 < n:
                cur.append(cmd[i + 1]); i += 2; continue
            if c == '"':
                in_d = False
            i += 1
            continue
        if in_bt:
            cur.append(c)
            if c == '`':
                in_bt = False
            i += 1
            continue
        if c == "'":
            in_s = True; cur.append(c); i += 1; continue
        if c == '"':
            in_d = True; cur.append(c); i += 1; continue
        if c == '`':
            in_bt = True; cur.append(c); i += 1; continue
        if c == '(':
            depth += 1; cur.append(c); i += 1; continue
        if c == ')':
            depth = max(0, depth - 1); cur.append(c); i += 1; continue
        if depth == 0 and (c in '|;\n' or (c == '&')):
            # flush current stage (collapses && and ||)
            stages.append(''.join(cur).strip()); cur = []
            i += 1; continue
        cur.append(c); i += 1
    if ''.join(cur).strip():
        stages.append(''.join(cur).strip())
    return [s for s in stages if s]


def is_executable(cmd: str):
    """Return (ok, reason). Conservative: any doubt -> not executable."""
    if not cmd or not cmd.strip():
        return False, 'empty command'
    low = ' ' + cmd.lower() + ' '
    for bad in DENIED_SUBSTRINGS:
        if bad in low:
            return False, f'denied substring: {bad.strip()!r}'
    for seg in _pipeline_stages(cmd):
        tokens = seg.split()
        first = tokens[0]
        if first in DENIED_FIRST_WORDS:
            return False, f'denied tool: {first!r}'
        if first not in ALLOWED_TOOLS:
            return False, f'non-allowlisted tool: {first!r}'
        # A bare "/" operand (e.g. `find /`) would scan the whole filesystem.
        if any(tok == '/' or tok.startswith('../') for tok in tokens):
            return False, 'root/parent path operand'
    return True, 'ok'


def _s(val):
    """Coerce captured output to str (TimeoutExpired may carry bytes)."""
    if val is None:
        return ''
    if isinstance(val, bytes):
        return val.decode('utf-8', 'replace')
    return val


def run_cmd(cmd, sandbox: Path):
    """Run cmd in sandbox with zsh -f and stock PATH; capture everything."""
    env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'HOME': str(sandbox)}
    try:
        proc = subprocess.run(['/bin/zsh', '-f', '-c', cmd], cwd=str(sandbox),
                              env=env, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=10)
        return {'stdout': proc.stdout, 'stderr': proc.stderr, 'rc': proc.returncode}
    except subprocess.TimeoutExpired as e:
        return {'stdout': _s(e.stdout), 'stderr': _s(e.stderr) + '\n<timeout>',
                'rc': 'timeout'}


def file_state(sandbox: Path):
    state = {}
    for p in sorted(sandbox.rglob('*')):
        if p.is_file() and not p.is_symlink():
            try:
                state[str(p.relative_to(sandbox))] = p.read_text()
            except Exception as e:  # noqa: BLE001
                state[str(p.relative_to(sandbox))] = f'<unreadable: {e}>'
    return state


def compare_one(dataset_by_id, item, tmp_base):
    cid = item['id']
    case = dataset_by_id.get(cid)
    if case is None:
        return {'id': cid, 'error': 'unknown id'}
    ref = case['reference']
    cand = item['candidate']
    fixture = case.get('fixture', {})

    out = {'id': cid, 'group': case['group'], 'reference': ref,
           'candidate': cand, 'fixture_files': list(fixture.get('files', {}).keys())}

    ok, reason = is_executable(cand)
    out['executable'] = ok
    out['safety_reason'] = reason
    if not ok:
        return out

    # Reference run.
    d_ref = Path(tempfile.mkdtemp(prefix=f'ref-{cid}-', dir=tmp_base))
    try:
        build_fixture(d_ref, fixture)
        rr = run_cmd(ref, d_ref)
        rs = file_state(d_ref)
    except FixtureError as e:
        out['error'] = f'reference fixture error: {e}'
        shutil.rmtree(d_ref, ignore_errors=True)
        return out
    finally:
        shutil.rmtree(d_ref, ignore_errors=True)

    # Candidate run.
    d_cand = Path(tempfile.mkdtemp(prefix=f'cand-{cid}-', dir=tmp_base))
    try:
        build_fixture(d_cand, fixture)
        rc_run = run_cmd(cand, d_cand)
        cs = file_state(d_cand)
    finally:
        shutil.rmtree(d_cand, ignore_errors=True)

    out['ref'] = rr
    out['cand'] = rc_run
    out['stdout_equal'] = rr['stdout'] == rc_run.get('stdout') and rr['rc'] == rc_run.get('rc')
    out['rc_ref'] = rr['rc']
    out['rc_cand'] = rc_run.get('rc')
    # File effects (diff only keys that differ).
    changed_files = {}
    for fname, expected in rs.items():
        got = cs.get(fname)
        if got != expected:
            changed_files[fname] = {'ref_result': expected, 'cand_result': got}
    out['file_state_differs'] = bool(changed_files)
    out['file_state_changes'] = changed_files
    return out


def load_dataset(cases_dir: Path):
    by_id = {}
    for name in ('eval_fit', 'eval_paraphrase', 'eval_operand', 'eval_composition'):
        p = cases_dir / f'{name}.jsonl'
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            if line.strip():
                c = json.loads(line)
                by_id[c['id']] = c
    return by_id


def main():
    if len(sys.argv) < 4:
        print('usage: compare_candidates.py <cases_dir> <candidates.json> <out.json>')
        return 2
    cases_dir = Path(sys.argv[1])
    candidates = json.loads(Path(sys.argv[2]).read_text())
    out_path = Path(sys.argv[3])
    tmp_base = '/private/tmp' if sys.platform == 'darwin' else '/tmp'

    dataset_by_id = load_dataset(cases_dir)
    results = [compare_one(dataset_by_id, item, tmp_base) for item in candidates]
    out_path.write_text(json.dumps({'results': results}, indent=2) + '\n')

    exec_ok = [r for r in results if r.get('executable')]
    stdout_match = [r for r in exec_ok if r.get('stdout_equal')]
    print(f'Evaluated {len(results)} candidates: {len(exec_ok)} executable, '
          f'{len(stdout_match)} produced reference-identical (stdout+rc).')
    print(f'Report written to {out_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
