#!/usr/bin/env python3
"""Build data v4: v3 rows plus no-majority requests labelled by judged-correct teacher samples.

    PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH=src:tools \
        ~/.local/pipx/venvs/whatisit/bin/python tools/build_verified_dataset.py \
        <keymap.json> <verdict dir> <confirm dir> data/distill/stage2-v4

A label is used only if the strict judge pass calls it correct (rubric in
data/distill/stage2-v4/LABEL.md). A second blind judge checked a sample of selected
labels to measure precision; a label it rejected is dropped, not re-selected. Among correct candidates: largest voting_key cluster by teacher sample
count, then the most frequent exact string, then shortest, then lexicographic.
v3 command rows judged incorrect are dropped; v3 empty targets are kept unchanged.
Requests with no correct candidate are dropped, never turned into empty targets.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from build_distill_dataset import eval_leakage, read_jsonl, read_quarantine, voting_key
from repair_distill_dataset import validate_command
from score_teacher_eval import effective_command
from whatisit_macos.local_recovery_worker import MACOS_PREFIX

ROOT = Path(__file__).resolve().parents[1]


def select(correct_counts):
    """Pick the training target from {command: teacher sample count} of judged-correct commands."""
    if not correct_counts:
        return None
    clusters = {}
    for command, count in correct_counts.items():
        clusters.setdefault(voting_key(command), Counter())[command] = count
    cluster = max(clusters.values(), key=lambda c: (sum(c.values()), -min(len(x) for x in c), min(c)))
    return min(cluster, key=lambda cmd: (-cluster[cmd], len(cmd), cmd))


def load_verdicts(directory):
    verdicts = {}
    for path in sorted(Path(directory).glob('*.json')):
        for case in json.loads(path.read_text())['cases']:
            for v in case['verdicts']:
                verdicts[v['key']] = v['verdict']
    return verdicts


def build(keymap, verdicts, confirmed, out_dir):
    v3 = read_jsonl(ROOT / 'data/distill/stage2-v3/train.jsonl')
    corpus = {r['id']: r for r in read_jsonl(ROOT / 'data/corpus/requests.jsonl')}
    raw = {r['id']: r for r in read_jsonl(ROOT / 'data/teacher/roihu_full_raw_samples.jsonl')}
    system = v3[0]['messages'][0]['content']
    correct = {k for k, v in verdicts.items() if v == 'correct'}
    rejected = {k for k, v in confirmed.items() if v != 'correct'}
    missing = set(keymap) - set(verdicts)
    if missing:
        raise ValueError(f'{len(missing)} candidates have no verdict')
    by_rid = {}
    for key, item in keymap.items():
        by_rid.setdefault((item['group'], item['rid']), []).append((key, item['command']))

    rows, audit = [], []
    for row in v3:
        target = row['messages'][-1]['content']
        keys = [k for k, _ in by_rid.get(('v3_kept', row['id']), [])]
        if target and not any(k in correct and k not in rejected for k in keys):
            audit.append({'id': row['id'], 'action': 'drop_v3_judged_incorrect', 'target': target})
            continue
        rows.append(row)
        audit.append({'id': row['id'], 'action': 'keep_v3'})

    quarantine = read_quarantine(ROOT / 'data/distill/roihu_full_quarantine_ids.txt', set(corpus))
    new_rows, new_requests = [], []
    for (group, rid), cands in sorted(by_rid.items()):
        if group != 'no_majority':
            continue
        request = raw[rid]['request']
        counts = Counter(effective_command(s, request) for s in raw[rid]['samples'])
        target = select({cmd: counts[cmd] for key, cmd in cands if key in correct})
        if target is None or rid in quarantine or any(k in rejected for k, cmd in cands if cmd == target):
            why = ('drop_no_correct' if target is None else
                   'drop_quarantine' if rid in quarantine else 'drop_second_judge')
            audit.append({'id': rid, 'action': why})
            continue
        validate_command(rid, target, request)
        new_requests.append({**corpus[rid], 'id': rid})
        new_rows.append({'id': rid, 'source_id': rid, 'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': MACOS_PREFIX + request},
            {'role': 'assistant', 'content': target}]})
    hard, _ = eval_leakage(new_requests, new_rows, ROOT / 'eval')
    leaked = {rid for rid, _, _ in hard}
    for row in new_rows:
        if row['id'] in leaked:
            audit.append({'id': row['id'], 'action': 'drop_eval_leakage'})
        else:
            rows.append(row)
            audit.append({'id': row['id'], 'action': 'add_verified', 'target': row['messages'][-1]['content']})

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'train.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
    (out / 'audit.jsonl').write_text(''.join(json.dumps(a) + '\n' for a in audit))
    actions = Counter(a['action'] for a in audit)
    empty = sum(1 for r in rows if not r['messages'][-1]['content'])
    manifest = {'rows': len(rows), 'commands': len(rows) - empty, 'empty_targets': empty,
                'actions': dict(actions),
                'train_sha256': hashlib.sha256((out / 'train.jsonl').read_bytes()).hexdigest()}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    keymap = json.loads(Path(sys.argv[1]).read_text())
    print(json.dumps(build(keymap, load_verdicts(sys.argv[2]), load_verdicts(sys.argv[3]), sys.argv[4]),
                     indent=2))
