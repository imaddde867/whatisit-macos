#!/usr/bin/env python3
"""Rebuild pass-1 judge receipts for the stage2-v4 campaign from the OpenCode session store.

The campaign pre-registered that pass-1 judge labels are stable aliases mapped to real
agent session ids in receipts, but the committed receipts carry only inputs and prompts.
This tool closes that gap on the macOS host that ran the campaign: it locates the judge
session for a batch in the OpenCode SQLite store, audits what that session read, wrote
and ran, re-runs the campaign validator, and writes ``receipts/pass1/<batch>/receipt.json``
in the same field convention as the calibration receipt.

The audit is fail-closed: any read, grep/glob search, or shell command touching a
forbidden file or another batch voids the receipt; any shell command outside the
static-analysis allowlist (man, ls, command -v, sha256sum, json.load validation) is
flagged and also voids ``result``; network, delegation and Code-Mode tools in a judge
session are flagged. LIKE needles are escaped.

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
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path.home() / '.local/share/opencode/opencode.db'

# Reading or searching any of these makes the blind pass void.
FORBIDDEN_READS = (
    'keymap.json', 'director-map.json', 'controls-map.json', 'controls.jsonl',
    'controls-audit.json', 'config.json', 'eval-audit', 'superseded/',
    'calibration/key.json', 'audit/full-', 'audit/controls-',
)
# Shell commands consistent with the rubric's static-analysis allowance. Chaining or
# substitution characters void allowlisting (the man|col pipe is the only sanctioned one).
SAFE_SHELL = (
    re.compile(r'man( -P cat)? [^|;&`$\n]+'),
    re.compile(r'man -P cat [^|;&`$\n]+ \| col -b'),
    re.compile(r'ls( -[a-zA-Z]+)*( [^|;&`$\n]+)*'),
    re.compile(r'command -v [^\s|;&`$\n]+'),
    re.compile(r'(sha256sum|shasum)( -[a-zA-Z]+)?( [^|;&`$\n]+)+'),
)
CROSS_BATCH_RE = re.compile(r'(?:pool/batches|verdicts|receipts/pass1)/b(\d\d)')
LABEL_RE = re.compile(r'"judge":\s*"([^"]+)"')


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def iso(ms):
    return datetime.fromtimestamp(ms / 1000).astimezone().isoformat(timespec='seconds')


def die(message):
    print(f'FAIL: {message}', file=sys.stderr)
    raise SystemExit(2)


def open_db(path):
    if not Path(path).exists():
        die(f'no OpenCode database at {path}')
    return sqlite3.connect(f'file:{path}?mode=ro', uri=True)


def campaign_paths(campaign, batch):
    c = Path(campaign)
    return {
        'batch': c / 'pool/batches' / f'{batch}.json',
        'manifest': c / 'pool/manifest.json',
        'prompt': c / 'receipts/pass1' / batch / 'prompt.txt',
        'inputs': c / 'receipts/pass1' / batch / 'inputs' / f'{batch}.json',
        'verdict': c / 'verdicts' / f'{batch}.json',
        'controls': c / 'pool/controls-map.json',
        'validator': c / 'validate_verdict.py',
        'receipt': c / 'receipts/pass1' / batch / 'receipt.json',
    }


def judge_label(prompt_path):
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
    reads, writes, shells, searches, other_tools, user_texts = [], [], [], [], [], []
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
            path = str(inp.get('path') or inp.get('filePath') or '')
            if name in ('read', 'list', 'glob', 'grep'):
                reads.append(path)
                if name in ('glob', 'grep'):
                    searches.append({'tool': name, 'path': path,
                                     'pattern': str(inp.get('pattern', ''))})
            elif name in ('write', 'edit'):
                writes.append(path)
            elif name in ('shell', 'bash', 'exec', 'execute'):
                shells.append(str(inp.get('command') or inp.get('code') or ''))
            elif name in ('webfetch', 'websearch', 'subagent'):
                other_tools.append(name)
    return reads, writes, shells, searches, other_tools, user_texts


def like_escape(needle):
    return needle.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def find_sessions(db, label, batch):
    hits = {}
    for needle in (label, f'pool/batches/{batch}.json', f'verdicts/{batch}.json'):
        for sid, in db.execute(
                "select distinct session_id from session_message "
                "where data like ? escape '\\'",
                (f'%{like_escape(needle)}%',)):
            entry = hits.setdefault(sid, {'session_id': sid, 'matches': []})
            entry['matches'].append(needle)
    out = []
    for sid, entry in hits.items():
        row = session_rows(db, sid)
        reads, writes, shells, _, _, _ = session_tools(db, sid)
        out.append({
            'session_id': sid, 'title': row[2], 'agent': row[3], 'directory': row[1],
            'created': iso(row[5]), 'updated': iso(row[6]),
            'reads': len(reads), 'writes': len(writes), 'shells': len(shells),
            'matches': sorted(set(entry['matches'])),
        })
    return sorted(out, key=lambda e: e['created'])


def touches_other_batch(text, batch):
    return any(f'b{digits}' != batch for digits in CROSS_BATCH_RE.findall(text))


def safe_shell(command):
    c = command.strip()
    first = c.split()[0] if c else ''
    if first in ('python', 'python3'):
        return 'json.load' in c
    return any(rx.fullmatch(c) for rx in SAFE_SHELL)


def classify(reads, writes, shells, searches, batch, prompt_text, label):
    flags, forbidden_reads, forbidden_shell, review = [], [], [], []
    for path in reads:
        p = path.replace('\\', '/')
        if any(bad in p for bad in FORBIDDEN_READS) or touches_other_batch(p, batch):
            forbidden_reads.append(path)
    for search in searches:
        p = search['path'].replace('\\', '/')
        if (any(bad in p for bad in FORBIDDEN_READS) or touches_other_batch(p, batch)
                or not p.rsplit('/', 1)[-1].count('.')):
            forbidden_reads.append(
                f"{search['tool']} {search['pattern']!r} in {search['path']}")
    bad_writes = [p for p in writes if f'verdicts/{batch}.json' not in p.replace('\\', '/')]
    for command in shells:
        if (any(bad in command for bad in FORBIDDEN_READS)
                or touches_other_batch(command, batch)):
            forbidden_shell.append(command)
        elif not safe_shell(command):
            review.append(command)
    if review:
        flags.append(f'{len(review)} shell command(s) outside the static-analysis allowlist')
    if label not in prompt_text:
        flags.append('judge label absent from session prompt')
    return forbidden_reads, forbidden_shell, bad_writes, review, flags


def build_receipt(db_path, campaign, batch, session_id, note=None):
    campaign = Path(campaign)
    paths = campaign_paths(campaign, batch)
    for key in ('batch', 'manifest', 'prompt', 'inputs', 'verdict', 'controls', 'validator'):
        if not paths[key].exists():
            die(f'missing {key}: {paths[key]}')
    label = judge_label(paths['prompt'])
    attempt = re.search(r'-(a\d+)$', label)
    db = open_db(db_path)
    try:
        row = session_rows(db, session_id)
        reads, writes, shells, searches, other_tools, user_texts = session_tools(db, session_id)
    finally:
        db.close()

    prompt_text = paths['prompt'].read_text()
    forbidden_reads, forbidden_shell, bad_writes, review, flags = classify(
        reads, writes, shells, searches, batch, prompt_text, label)
    if not any(label in t for t in user_texts):
        flags.append('session prompt does not contain the judge label')
    if not any(paths['batch'].name in p or paths['inputs'].name in p for p in reads):
        flags.append('session never read the batch file')
    if other_tools:
        flags.append(f'judge session used network/delegation tools: '
                     f'{", ".join(sorted(set(other_tools)))}')

    verdict = json.loads(paths['verdict'].read_text())
    if verdict.get('judge') != label:
        flags.append(f"verdict judge {verdict.get('judge')!r} != prompt label {label!r}")

    check = subprocess.run(
        [sys.executable, str(paths['validator']), str(paths['batch']),
         str(paths['verdict']), str(paths['controls'])],
        capture_output=True, text=True)
    verdict_valid = check.returncode == 0

    used_by = []
    for other in campaign.rglob('receipt.json'):
        if other == paths['receipt']:
            continue
        if json.loads(other.read_text()).get('agent_session_id') == session_id:
            used_by.append(str(other))
    if used_by:
        flags.append(f'session already receipted for: {", ".join(used_by)}')

    hard = (forbidden_reads or forbidden_shell or bad_writes or used_by
            or verdict.get('judge') != label)
    result = verdict_valid and not hard and not flags
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
                         'Reads, writes and shell commands of the judge session were '
                         'audited; no candidate command was executed.'),
        'prompt_sha256': sha256_file(paths['prompt']),
        'result': result,
        'started_at': iso(row[5]),
        'verdict_sha256': sha256_file(paths['verdict']),
        'verdict_validator': check.stdout.strip() or check.stderr.strip(),
        'reconstructed': True,
        'reconstructed_at': iso(int(datetime.now().timestamp() * 1000)),
        'audit': {
            'reads': reads, 'writes': writes, 'shells': shells, 'searches': searches,
            'other_tools': other_tools,
            'forbidden_reads': forbidden_reads, 'forbidden_shell': forbidden_shell,
            'writes_outside_verdict': bad_writes, 'shell_needs_review': review,
            'flags': flags,
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
    print(f'wrote {out_path}: result={ok} '
          f'forbidden_reads={len(audit["forbidden_reads"])} '
          f'forbidden_shell={len(audit["forbidden_shell"])} '
          f'shell_review={len(audit["shell_needs_review"])} '
          f'flags={len(audit["flags"])}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
