#!/usr/bin/env python3
"""Rebuild pass-1 judge receipts for the stage2-v4 campaign from the OpenCode session store.

The campaign pre-registered that pass-1 judge labels are stable aliases mapped to real
agent session ids in receipts, but the committed receipts carry only inputs and prompts.
This tool closes that gap on the host that ran the campaign: it locates the judge session
for a batch in the OpenCode SQLite store, verifies what that session read, wrote and ran,
re-runs the campaign validator, and writes ``receipts/pass1/<batch>/receipt.json`` in the
same field convention as the calibration receipt.

The audit is fail-closed. A session may read only the rubric, its own batch/inputs/prompt
and its own verdict; it may run only the static-analysis commands the pass-1 prompt
allows; it must not use grep/glob, the network, subagents or code execution to look for
answers. Any deviation makes ``result`` false; it is recorded, never waived.

Read-only against the database (opened with mode=ro). Writes only the one receipt file.

Usage:
    make_v4_receipt.py find    --campaign DIR --batch b00 [--db PATH]
    make_v4_receipt.py receipt --campaign DIR --batch b00 --session ses_XXX [--db PATH] [--note TEXT]

Exit codes: 0 ok, 1 verification failed (receipt still written with result=false and flags),
2 usage or input error.
"""
import argparse
import hashlib
import json
import re
import shlex
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path.home() / '.local/share/opencode/opencode.db'

# A path fragment that must never appear in a judge session's inputs.
FORBIDDEN_READS = (
    'keymap.json', 'director-map.json', 'controls-map.json', 'controls.jsonl',
    'controls-audit.json', 'config.json', 'eval-audit', 'superseded/',
    'calibration/', 'audit/full-', 'audit/controls-',
)
SHELL_OPERATORS = {';', ';;', '&&', '||', '|', '&', '>', '>>', '<', '<<'}
ALLOWED_BIN_ROOTS = re.compile(r'^/(?:usr/)?s?bin(?:/[\w.+-]+)*$')
TOOL_NAME = re.compile(r'^[A-Za-z0-9_.+-]+$')
LABEL_RE = re.compile(r'"judge":\s*"([^"]+)"')
OPEN_CALL_RE = re.compile(r"open\(\s*['\"]([^'\"]+)['\"]")
UNSAFE_PYTHON = re.compile(
    r'\b(?:os|subprocess|pathlib|glob|importlib|socket|urllib|requests|shutil)\b')


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def iso(ms):
    return datetime.fromtimestamp(ms / 1000).astimezone().isoformat(timespec='seconds')


def die(message):
    """Input or usage error: exit 2, never a verification failure (which is exit 1)."""
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(2)


def open_db(path):
    if not Path(path).exists():
        die(f'no OpenCode database at {path}')
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True)


def campaign_paths(campaign, batch):
    c = Path(campaign)
    return {
        'campaign': c,
        'batch': c / 'pool/batches' / f'{batch}.json',
        'prompt': c / 'receipts/pass1' / batch / 'prompt.txt',
        'inputs': c / 'receipts/pass1' / batch / 'inputs' / f'{batch}.json',
        'verdict': c / 'verdicts' / f'{batch}.json',
        'controls': c / 'pool/controls-map.json',
        'manifest': c / 'pool/manifest.json',
        'validator': c / 'validate_verdict.py',
        'receipt': c / 'receipts/pass1' / batch / 'receipt.json',
    }


def judge_label(prompt_path):
    prompt_path = Path(prompt_path)
    if not prompt_path.exists():
        die(f'missing prompt: {prompt_path}')
    match = LABEL_RE.search(prompt_path.read_text())
    if not match:
        die(f'no judge label found in {prompt_path}')
    return match.group(1)


def session_rows(db, session_id):
    row = db.execute(
        'select id, directory, title, agent, model, time_created, time_updated '
        'from session_v2 where id=?', (session_id,)).fetchone()
    if not row:
        die(f'session {session_id} not in the session store')
    return row


def session_tools(db, session_id):
    reads, writes, shells, searches, network, other = [], [], [], [], [], []
    user_texts = []
    for mtype, data in db.execute(
            'select type, data from session_message where session_id=? order by seq',
            (session_id,)):
        j = json.loads(data)
        if mtype == 'user':
            user_texts.append(j.get('text', ''))
            continue
        for item in j.get('content') or []:
            if item.get('type') != 'tool':
                continue
            name = item.get('name') or ''
            inp = (item.get('state') or {}).get('input') or {}
            if name in ('read', 'list'):
                reads.append(str(inp.get('path', '')))
            elif name in ('glob', 'grep'):
                path = str(inp.get('path', ''))
                reads.append(path)
                searches.append({'tool': name, 'path': path,
                                 'pattern': str(inp.get('pattern', ''))})
            elif name in ('write', 'edit'):
                writes.append(str(inp.get('path') or inp.get('filePath') or ''))
            elif name in ('shell', 'bash', 'exec', 'execute'):
                command = inp.get('command') or inp.get('code') or ''
                shells.append({'tool': name, 'command': str(command)})
            elif name in ('webfetch', 'websearch', 'subagent', 'task'):
                network.append({'tool': name, 'input': str(inp)[:300]})
            else:
                other.append(name)
    return reads, writes, shells, searches, network, other, user_texts


def like_escape(needle):
    return needle.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def find_sessions(db, label, batch):
    hits = {}
    for needle in (label, f'pool/batches/{batch}.json', f'verdicts/{batch}.json'):
        pattern = f'%{like_escape(needle)}%'
        for sid, in db.execute(
                "select distinct session_id from session_message "
                "where data like ? escape '\\'", (pattern,)):
            hits.setdefault(sid, {'matches': []})['matches'].append(needle)
        for sid, in db.execute(
                "select id from session_v2 where title like ? escape '\\'", (pattern,)):
            hits.setdefault(sid, {'matches': []})['matches'].append(needle)
    out = []
    for sid, entry in hits.items():
        row = session_rows(db, sid)
        reads, writes, shells, searches, _, _, _ = session_tools(db, sid)
        out.append({
            'session_id': sid, 'title': row[2], 'agent': row[3], 'directory': row[1],
            'created': iso(row[5]), 'updated': iso(row[6]),
            'reads': len(reads), 'writes': len(writes), 'shells': len(shells),
            'searches': len(searches),
            'matches': sorted(set(entry['matches'])),
        })
    return sorted(out, key=lambda e: e['created'])


def _parts(path):
    return [part for part in str(path).replace('\\', '/').split('/') if part]


def allowed_read(path, batch):
    """Only the rubric, this batch's own inputs/prompt and this batch's own verdict."""
    if any(bad in str(path).replace('\\', '/') for bad in FORBIDDEN_READS):
        return False
    parts = _parts(path)
    if parts[-2:] == ['stage2-v4', 'LABEL.md']:
        return True
    if not parts:
        return False
    name = parts[-1]
    if name == f'{batch}.json':
        if len(parts) >= 2 and parts[-2] == 'batches' and 'pool' in parts:
            return True
        if len(parts) >= 2 and parts[-2] == 'verdicts':
            return True
        if (len(parts) >= 4 and parts[-2] == 'inputs'
                and parts[-3] == batch and parts[-4] == 'pass1'):
            return True
    if name == 'prompt.txt' and len(parts) >= 4 and parts[-2] == batch and parts[-3] == 'pass1':
        return True
    return False


def _pipe_split(tokens):
    if '|' not in tokens:
        return tokens, None
    if tokens.count('|') != 1:
        return None, None
    index = tokens.index('|')
    return tokens[:index], tokens[index + 1:]


def _ls_ok(tokens):
    operands = [t.rstrip('/') for t in tokens[1:] if not t.startswith('-')]
    flags = [t for t in tokens[1:] if t.startswith('-')]
    if not operands or not all(re.fullmatch(r'-[A-Za-z]+', f) for f in flags):
        return False
    return all(ALLOWED_BIN_ROOTS.match(op) for op in operands)


def _python_ok(tokens, batch):
    if len(tokens) != 3 or tokens[1] != '-c':
        return False
    script = tokens[2]
    if 'json.load' not in script or UNSAFE_PYTHON.search(script):
        return False
    return all(allowed_read(match, batch) for match in OPEN_CALL_RE.findall(script))


def _sha_ok(tokens, batch):
    operands = [t for t in tokens[1:] if not t.startswith('-')]
    if not operands:
        return False
    modes = [t for t in tokens[1:] if t.startswith('-')]
    if not all(re.fullmatch(r'-[aA]', m) for m in modes):
        return False
    return all(allowed_read(op, batch) for op in operands)


def shell_violation(command, batch):
    """Return why a shell command is outside the static-analysis allowlist, or None."""
    raw = (command or '').strip()
    if not raw:
        return 'empty shell command'
    try:
        tokens = shlex.split(raw)
    except ValueError:
        return 'unparsable shell command'
    if not tokens:
        return 'empty shell command'
    head, tail = _pipe_split(tokens)
    if head is None:
        return 'multiple pipes'
    if any(t in SHELL_OPERATORS for t in tokens if t != '|'):
        return 'shell operator or redirection'
    if any('`' in t or '$(' in t or '${' in t for t in tokens):
        return 'shell substitution'
    low = raw.lower()
    for bad in FORBIDDEN_READS:
        if bad in low:
            return f'mentions forbidden path {bad!r}'
    program = Path(head[0]).name
    if program == 'man':
        args = head[1:]
        if args[:2] == ['-P', 'cat']:
            args = args[2:]
        if len(args) != 1 or not TOOL_NAME.fullmatch(args[0]):
            return 'man must target exactly one page (optionally -P cat)'
        if tail is not None and tail != ['col', '-b']:
            return 'man may only be piped through col -b'
        return None
    if tail is not None:
        return 'pipeline only allowed for man | col -b'
    if program == 'ls':
        return None if _ls_ok(head) else 'ls may only list stock tool directories'
    if program == 'command':
        if len(head) == 3 and head[1] == '-v' and TOOL_NAME.fullmatch(head[2]):
            return None
        return 'command is only allowed as command -v <tool>'
    if program in ('python3', 'python'):
        return None if _python_ok(head, batch) else 'python -c may only json.load allowed files'
    if program in ('sha256sum', 'shasum'):
        return None if _sha_ok(head, batch) else 'checksum may only hash allowed files'
    return f'not on the static-analysis allowlist: {head[0]}'


def _writes_verdict(path, batch):
    parts = _parts(path)
    return len(parts) >= 2 and parts[-1] == f'{batch}.json' and parts[-2] == 'verdicts'


def classify(reads, writes, shells, searches, network, batch, prompt_text, label, verdict):
    disallowed, forbidden, bad_writes = [], [], []
    shell_violations, search_violations, flags = [], [], []
    for path in reads:
        normalized = path.replace('\\', '/')
        if any(bad in normalized for bad in FORBIDDEN_READS):
            forbidden.append(path)
        if not allowed_read(path, batch):
            disallowed.append(path)
    for path in writes:
        if not _writes_verdict(path, batch):
            bad_writes.append(path)
    for item in shells:
        reason = shell_violation(item['command'], batch)
        if reason:
            shell_violations.append({**item, 'reason': reason})
    for item in searches:
        if not allowed_read(item['path'], batch):
            search_violations.append({**item, 'reason': 'search outside this batch'})
    if label not in prompt_text:
        flags.append('judge label absent from session prompt')
    if verdict.get('judge') != label:
        flags.append(f"verdict judge {verdict.get('judge')!r} != prompt label {label!r}")
    return {
        'forbidden_reads': sorted(set(forbidden)),
        'disallowed_reads': sorted(set(disallowed)),
        'writes_outside_verdict': bad_writes,
        'shell_violations': shell_violations,
        'search_violations': search_violations,
        'network_or_subagent': network,
        'flags': flags,
    }


def build_receipt(db_path, campaign, batch, session_id, note=None):
    paths = campaign_paths(campaign, batch)
    for key in ('batch', 'prompt', 'inputs', 'verdict', 'controls', 'manifest', 'validator'):
        if not paths[key].exists():
            die(f'missing {key}: {paths[key]}')
    label = judge_label(paths['prompt'])
    attempt = re.search(r'-(a\d+)$', label)
    db = open_db(db_path)
    try:
        row = session_rows(db, session_id)
        reads, writes, shells, searches, network, _, user_texts = session_tools(db, session_id)
    finally:
        db.close()

    prompt_text = paths['prompt'].read_text()
    verdict = json.loads(paths['verdict'].read_text())
    audit = classify(reads, writes, shells, searches, network, batch,
                     prompt_text, label, verdict)
    if not any(label in text for text in user_texts):
        audit['flags'].append('session prompt does not contain the judge label')
    batch_read = any(allowed_read(path, batch) and 'batches' in _parts(path)
                     and _parts(path)[-1] == f'{batch}.json' for path in reads)
    if not batch_read:
        audit['flags'].append('session never read the batch file')

    check = subprocess.run(
        [sys.executable, str(paths['validator']), str(paths['batch']),
         str(paths['verdict']), str(paths['controls'])],
        capture_output=True, text=True)
    verdict_valid = check.returncode == 0

    used_by = []
    for other in Path(campaign).glob('**/receipt.json'):
        if other.resolve() == paths['receipt'].resolve():
            continue
        try:
            other_session = json.loads(other.read_text()).get('agent_session_id')
        except (OSError, json.JSONDecodeError):
            continue
        if other_session == session_id:
            used_by.append(str(other))
    if used_by:
        audit['flags'].append(f'session already receipted for: {", ".join(used_by)}')

    hard = (
        audit['forbidden_reads'] or audit['disallowed_reads']
        or audit['writes_outside_verdict'] or audit['shell_violations']
        or audit['search_violations'] or audit['network_or_subagent']
        or used_by or verdict.get('judge') != label or not verdict_valid
    )
    result = not hard and not audit['flags']
    receipt = {
        'agent_session_id': session_id,
        'attempt': attempt.group(1) if attempt else None,
        'batch_sha256': sha256_file(paths['batch']),
        'inputs_sha256': sha256_file(paths['inputs']),
        'completed_at': iso(row[6]),
        'judge_label': label,
        'judge_model': row[4],
        'judge_directory': row[1],
        'key_sha256': sha256_file(paths['controls']),
        'manifest_sha256': sha256_file(paths['manifest']),
        'note': note or ('Reconstructed from the OpenCode session store. '
                         'Reads, writes, searches and shell commands of the judge session '
                         'were audited; no candidate command was executed.'),
        'prompt_sha256': sha256_file(paths['prompt']),
        'result': result,
        'started_at': iso(row[5]),
        'verdict_sha256': sha256_file(paths['verdict']),
        'verdict_validator': check.stdout.strip() or check.stderr.strip(),
        'reconstructed': True,
        'reconstructed_at': iso(int(datetime.now().timestamp() * 1000)),
        'audit': {
            'reads': reads,
            'writes': writes,
            'shell_commands': shells,
            'searches': searches,
            'network_or_subagent': network,
            **audit,
        },
    }
    return receipt, paths['receipt'], result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('mode', choices=['find', 'receipt'])
    parser.add_argument('--campaign', required=True, type=Path)
    parser.add_argument('--batch', required=True)
    parser.add_argument('--db', type=Path, default=DEFAULT_DB)
    parser.add_argument('--session')
    parser.add_argument('--note')
    args = parser.parse_args(argv)

    if args.mode == 'find':
        paths = campaign_paths(args.campaign, args.batch)
        if not paths['prompt'].exists():
            die(f'missing prompt: {paths["prompt"]}')
        label = judge_label(paths['prompt'])
        db = open_db(args.db)
        try:
            print(json.dumps(find_sessions(db, label, args.batch), indent=1))
        finally:
            db.close()
        return 0

    if not args.session:
        parser.error('receipt mode needs --session (run find first)')
    receipt, out_path, ok = build_receipt(args.db, args.campaign, args.batch,
                                          args.session, args.note)
    out_path.write_text(json.dumps(receipt, indent=1) + '\n')
    audit = receipt['audit']
    violations = sum(len(audit[key]) for key in (
        'forbidden_reads', 'disallowed_reads', 'writes_outside_verdict',
        'shell_violations', 'search_violations', 'network_or_subagent'))
    print(f'wrote {out_path}: result={ok} reads={len(audit["reads"])} '
          f'shells={len(audit["shell_commands"])} violations={violations} '
          f'flags={len(audit["flags"])}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
