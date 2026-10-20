"""Build stage-2 data without relabeling or overwriting historical artifacts."""

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import importlib.metadata
import os
import platform
import sys
from pathlib import Path
import re

from build_distill_dataset import check_inputs, command_vote, eval_leakage, read_jsonl, read_quarantine, signature
from whatisit_macos.local_recovery_worker import MACOS_PREFIX

ROOT = Path(__file__).resolve().parents[1]
CUES = re.compile(r"\bwithout\b|\bwihtout\b|haven't|unnamed|unspecified|unidentified", re.I)


def validate_command(rid, command, request, path=None):
    if not command:
        return
    from whatisit_macos.maclint import validation_issues
    from build_distill_dataset import INTERACTIVE
    issues = validation_issues(command, request, path)
    if INTERACTIVE.fullmatch(command):
        issues.append('interactive command')
    if issues:
        raise ValueError(f'{rid}: command fails serving validation: ' + '; '.join(issues))


def validation_fingerprint():
    """Bind a campaign to the validation code and its relevant runtime environment."""
    files = ('src/whatisit_macos/shell.py', 'src/whatisit_macos/maclint.py',
             'tools/repair_distill_dataset.py', 'tools/build_distill_dataset.py')
    code = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}
    try:
        from whatisit import safety
    except ImportError:
        safety = None
    source = getattr(safety, '__file__', None)
    if source:
        source = Path(source).resolve()
        if source.is_relative_to('/home') and not source.is_relative_to(ROOT):
            code['upstream_safety'] = 'source_outside_task_workspace'
        else:
            code['upstream_safety'] = hashlib.sha256(source.read_bytes()).hexdigest()
    else:
        code['upstream_safety'] = 'unavailable'
    try:
        version = importlib.metadata.version('whatisit')
    except importlib.metadata.PackageNotFoundError:
        version = 'unavailable'
    return {'code_sha256': code, 'whatisit_version': version,
            'python': list(sys.version_info[:2]),
            'platform': [platform.system(), platform.release()],
            'path_sha256': hashlib.sha256(os.environ.get('PATH', '').encode()).hexdigest()}


def repair(requests, labels, raw, amendments, provenance=None):
    def unique(records, name):
        ids = [r.get('id') for r in records if isinstance(r, dict)]
        if len(ids) != len(records) or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
            raise ValueError(f'invalid or duplicate {name} id')
        return {r['id']: r for r in records}

    by_id = unique(requests, 'request')
    teacher = unique(raw, 'teacher')
    label_by_id = unique(labels, 'label')
    edits = unique(amendments, 'amendment')
    if (set(edits) - set(label_by_id) or set(label_by_id) - set(by_id) or
            set(teacher) - set(by_id) or set(label_by_id) - set(teacher)):
        raise ValueError('unknown or missing source id')
    for rid, request in by_id.items():
        if (not isinstance(request.get('request'), str) or not request['request'].strip() or len(request['request']) > 2000 or
                any(c in request['request'] for c in '\x00\r\n') or request.get('kind') not in ('answer', 'abstain')):
            raise ValueError(f'{rid}: invalid request schema')
    for rid, row in label_by_id.items():
        msgs = row.get('messages')
        if (not isinstance(msgs, list) or len(msgs) != 3 or
                [m.get('role') for m in msgs if isinstance(m, dict)] != ['system', 'user', 'assistant'] or
                len([m for m in msgs if isinstance(m, dict)]) != 3 or
                any(not isinstance(m.get('content'), str) for m in msgs)):
            raise ValueError(f'{rid}: invalid label schema')
    for rid, record in teacher.items():
        if (not isinstance(record.get('request'), str) or not isinstance(record.get('samples'), list) or
                any(not isinstance(s, dict) or not isinstance(s.get('parsed'), bool) or
                    s.get('command') is not None and not isinstance(s.get('command'), str)
                    for s in record['samples'])):
            raise ValueError(f'{rid}: invalid teacher schema')
    for rid, edit in edits.items():
        if not isinstance(edit.get('reason'), str) or not edit['reason'].strip():
            raise ValueError(f'{rid}: amendment reason is required')
        for field in ('original_request', 'original_target'):
            if field not in edit or not isinstance(edit[field], str):
                raise ValueError(f'{rid}: invalid amendment {field}')
        for field, limit in (('request', 2000), ('target', 4096), ('path', 8192),
                             ('provenance', 200), ('verification', 1000)):
            if field in edit and (not isinstance(edit[field], str) or len(edit[field]) > limit or
                                  any(c in edit[field] for c in '\x00\r\n')):
                raise ValueError(f'{rid}: invalid amendment {field}')
    kept, repaired_requests, audit, seen = [], [], [], {}
    for source in labels:
        rid = source['id']
        request, row = deepcopy(by_id[rid]), deepcopy(source)
        request['source_id'] = rid
        row['source_id'] = rid
        target = row['messages'][-1]['content']
        if teacher[rid]['request'] != request['request'] or row['messages'][1]['content'] != MACOS_PREFIX + request['request']:
            raise ValueError(f'{rid}: source prompt mismatch')
        votes = sum(s.get('parsed') is True and s.get('finish_reason') == 'stop' and
                    s.get('command') == (target or None) for s in teacher[rid]['samples'])
        cluster = (provenance or {}).get(rid)
        if cluster:
            valid = Counter()
            for sample in teacher[rid]['samples']:
                command = sample.get('command')
                if sample.get('parsed') is True and sample.get('finish_reason') == 'stop' and command:
                    try:
                        validate_command(rid, command, request['request'], request.get('path'))
                    except ValueError:
                        continue
                    valid[command] += 1
            winner, size, strings = command_vote(valid, 'equivalence')
            if (cluster.get('vote_mode') != 'equivalence' or winner != target or size < 3 or
                    size != cluster.get('cluster_votes') or strings != cluster.get('strings')):
                raise ValueError(f'{rid}: invalid cluster provenance')
        if target and votes < 3 and not cluster:
            raise ValueError(f'{rid}: target lacks teacher majority')
        if not target and votes < 3 and request['kind'] != 'abstain':
            raise ValueError(f'{rid}: abstention lacks provenance')
        edit = edits.get(rid)
        item = {'id': rid, 'source_id': rid, 'teacher_votes': votes,
                'action': 'keep', 'reason': 'unchanged teacher target'}
        if provenance is not None:
            item.update(vote_mode='equivalence' if cluster else 'exact',
                        cluster_votes=cluster['cluster_votes'] if cluster else votes)
        if edit:
            if edit['original_request'] != request['request'] or edit['original_target'] != target:
                raise ValueError(f'{rid}: stale amendment')
            item['reason'] = edit['reason']
            if 'target' in edit:
                if not edit.get('provenance') or not edit.get('verification'):
                    raise ValueError(f'{rid}: corrected target requires provenance and verification')
                target = edit['target']
                item['original_target_votes'] = votes
                votes = sum(s.get('parsed') is True and s.get('finish_reason') == 'stop' and
                            s.get('command') == (target or None) for s in teacher[rid]['samples'])
                validate_command(rid, target, request['request'], request.get('path'))
                row['messages'][-1]['content'] = target
                request['kind'] = 'answer' if target else 'abstain'
                if not target:
                    request['category'] = 'abstain'
                item.update(action='corrected_target', correction_provenance=edit['provenance'],
                            verification=edit['verification'], teacher_votes=votes)
            if edit.get('exclude'):
                item['action'] = 'exclude'
                audit.append(item)
                continue
            new_request = edit.get('request', request['request'])
            if not isinstance(new_request, str) or not new_request.strip() or len(new_request) > 2000 or any(c in new_request for c in '\x00\r\n'):
                raise ValueError(f'{rid}: invalid rewritten request')
            original_request = request['request']
            request['request'] = new_request
            prompt = MACOS_PREFIX + new_request
            if 'path' in edit:
                path = edit['path']
                if not isinstance(path, str) or not path or path not in edit['original_request'] or path not in target:
                    raise ValueError(f'{rid}: explicit path is not a named teacher operand')
                request['path'] = path
                prompt += '\nExplicit inputs: ' + json.dumps({'path': path}, ensure_ascii=False)
            elif target and 'target' not in edit and original_request != new_request and not edit.get('provenance'):
                raise ValueError(f'{rid}: command rewrite requires reviewed provenance')
            row['messages'][1]['content'] = prompt
            validate_command(rid, row['messages'][-1]['content'], new_request, request.get('path'))
            if item['action'] == 'keep':
                item['action'] = ('explicit_path' if 'path' in edit else
                                  'clarified_request' if target else 'natural_abstain')
            if 'target' in edit:
                item['action'] = 'corrected_target'
        key = ' '.join(request['request'].casefold().split()), request.get('path')
        if key in seen:
            item.update(action='exclude', reason=f'duplicate request of {seen[key]}')
        else:
            seen[key] = rid
            kept.append(row)
            repaired_requests.append(request)
        audit.append(item)
    return kept, repaired_requests, audit


def leakage_blocked(hard, rows):
    """Ids of every row sharing a source family with a hard leakage hit."""
    family = {r['id']: r.get('source_id') or r['id'] for r in rows}
    hit = {family[rid] for rid, _, _ in hard}
    return {rid for rid, source in family.items() if source in hit}


def add_additions(rows, requests, additions, system_prompt):
    existing = {r['id'] for r in rows} | {r['id'] for r in requests}
    seen = set(existing)
    added_rows, added_requests, audit = [], [], []
    for item in additions:
        if not isinstance(item, dict):
            raise ValueError('invalid addition schema')
        rid = item.get('id')
        if not isinstance(rid, str) or not re.fullmatch(r's2add\d{3,}', rid) or rid in seen:
            raise ValueError(f'{rid}: invalid or duplicate addition id')
        seen.add(rid)
        for field, limit in (('source_id', 80), ('request', 2000), ('target', 4096), ('category', 100),
                             ('kind', 20), ('provenance', 200), ('reason', 1000), ('verification', 1000)):
            value = item.get(field)
            if not isinstance(value, str) or (field not in ('target',) and not value.strip()) or len(value) > limit or any(c in value for c in '\x00\r\n'):
                raise ValueError(f'{rid}: invalid addition {field}')
        if item['kind'] != ('answer' if item['target'] else 'abstain'):
            raise ValueError(f'{rid}: addition kind does not match target')
        path = item.get('path')
        if path is not None and (not isinstance(path, str) or not path or len(path) > 8192 or any(c in path for c in '\x00\r\n')):
            raise ValueError(f'{rid}: invalid addition path')
        validate_command(rid, item['target'], item['request'], path)
        prompt = MACOS_PREFIX + item['request']
        if path is not None:
            prompt += '\nExplicit inputs: ' + json.dumps({'path': path}, ensure_ascii=False)
        added_rows.append({'id': rid, 'source_id': item['source_id'], 'messages': [
            {'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': prompt},
            {'role': 'assistant', 'content': item['target']}]})
        request = {'id': rid, 'source_id': item['source_id'], 'request': item['request'],
                   'category': item['category'], 'kind': item['kind']}
        if path is not None:
            request['path'] = path
        added_requests.append(request)
        audit.append({'id': rid, 'source_id': item['source_id'], 'action': 'model_authored_addition',
                      'provenance': item['provenance'], 'reason': item['reason'],
                      'verification': item['verification'], 'teacher_votes': 0})
    return rows + added_rows, requests + added_requests, audit


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def v3_summary(rows, requests, provenance, baseline):
    """Coverage and recovery counts after all repair/family exclusions."""
    kept = {r['id'] for r in rows}
    recovered = {rid: p for rid, p in provenance.items() if rid in kept}
    categories = {r['id']: r['category'] for r in requests}
    commands = Counter(r['messages'][-1]['content'] for r in rows if r['messages'][-1]['content'])
    old = Counter(r['messages'][-1]['content'] for r in baseline if r['messages'][-1]['content'])
    new_signatures = {s for c in commands for s in signature(c)}
    old_signatures = {s for c in old for s in signature(c)}
    return {'recovered_rows': len(recovered),
            'recovered_base_rows': len(provenance),
            'recovered_excluded_by_repair': len(provenance) - len(recovered),
            'recovered_by_category': dict(sorted(Counter(categories[rid] for rid in recovered).items())),
            'recovered_by_agreement': dict(sorted(Counter(str(p['cluster_votes']) for p in recovered.values()).items())),
            'recovered_multistring_rows': sum(len(p['strings']) > 1 for p in recovered.values()),
            'abstention_share_before': (len(baseline) - sum(old.values())) / len(baseline) if baseline else 0,
            'abstention_share_after': (len(rows) - sum(commands.values())) / len(rows) if rows else 0,
            'new_repeated_exact_command_rows': sum(max(0, n - max(1, old[c])) for c, n in commands.items()),
            'tool_flag_signatures': len(new_signatures), 'v2_tool_flag_signatures': len(old_signatures),
            'overlapping_tool_flag_signatures': len(new_signatures & old_signatures),
            'new_tool_flag_signatures': len(new_signatures - old_signatures)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, default=ROOT / 'data/distill/stage2-v3')
    parser.add_argument('--base-labels', type=Path, default=ROOT / 'data/distill/v3-base/train.jsonl')
    parser.add_argument('--votes', type=Path)
    args = parser.parse_args()
    if args.votes is None and args.base_labels != ROOT / 'data/distill/roihu_full_train.jsonl':
        args.votes = args.base_labels.with_suffix('.votes.jsonl')
    out = args.out_dir
    if out.exists():
        raise FileExistsError('choose a fresh output directory')
    paths = {name: ROOT / path for name, path in {
        'requests': 'data/corpus/requests.jsonl',
        'raw': 'data/teacher/roihu_full_raw_samples.jsonl',
        'teacher_manifest': 'data/teacher/roihu_full_manifest.json',
        'stage1': 'data/distill/roihu_full_train.jsonl',
        'amendments': 'data/distill/stage2-v1-amendments.jsonl',
        'additions': 'data/distill/stage2-additions.jsonl',
        'historical_quarantine': 'data/distill/roihu_full_quarantine_ids.txt',
        'builder': 'tools/build_distill_dataset.py',
        'repair_script': 'tools/repair_distill_dataset.py',
    }.items()}
    paths['stage1'] = args.base_labels
    if args.votes:
        paths['votes'] = args.votes
        paths['corpus_quarantine'] = ROOT / 'data/distill/quarantine_ids.txt'
        paths['v2_baseline'] = ROOT / 'data/distill/stage2-v2/train.jsonl'
    requests, raw, _ = check_inputs(paths['requests'], paths['raw'], paths['teacher_manifest'])
    source = read_jsonl(paths['stage1'])
    provenance = {r['id']: r for r in read_jsonl(args.votes)} if args.votes else None
    rows, revised, audit = repair(requests, source, raw, read_jsonl(paths['amendments']), provenance)
    rows, revised, additions_audit = add_additions(
        rows, revised, read_jsonl(paths['additions']), source[0]['messages'][0]['content'])
    audit.extend(additions_audit)
    # Frozen and heldout contents are consumed only by the existing leakage gate.
    hard, review = eval_leakage(revised, rows, ROOT / 'eval')
    if args.votes:
        known = {r['id'] for r in requests}
        listed = read_quarantine(paths['historical_quarantine'], known)
        listed.update(read_quarantine(ROOT / 'data/distill/quarantine_ids.txt', known))
        # Include historical hits only when the row or a derivative is present.
        hard = sorted(set(hard) | {(r['id'], 'historical quarantine (source family)', 'historical')
                                  for r in rows if r['id'] in listed or r.get('source_id') in listed})
    blocked = leakage_blocked(hard, rows)
    for item in audit:
        if item['id'] in blocked:
            item.update(action='exclude', reason='existing evaluation leakage gate (source family)')
    rows = [r for r in rows if r['id'] not in blocked]
    revised = [r for r in revised if r['id'] not in blocked]
    commands = sum(bool(r['messages'][-1]['content']) for r in rows)
    actions = dict(sorted(Counter(r['action'] for r in audit).items()))
    original = {r['id']: r for r in requests}
    old_cues = sum(not r['messages'][-1]['content'] and bool(CUES.search(original[r['id']]['request'])) for r in source)
    new_cues = sum(r['kind'] == 'abstain' and bool(CUES.search(r['request'])) for r in revised)
    command_counts = Counter(r['messages'][-1]['content'] for r in rows if r['messages'][-1]['content'])
    out.mkdir(parents=True)
    for filename, records in [('train.jsonl', rows), ('requests.jsonl', revised), ('audit.jsonl', audit)]:
        (out / filename).write_text(''.join(json.dumps(r, ensure_ascii=False, sort_keys=True) + '\n' for r in records))
    manifest = {'version': 'stage2-v3' if args.votes else 'stage2-v2', 'review': 'model review; not human-certified',
                'inputs_sha256': {k: digest(v) for k, v in paths.items()},
                'eval_gate_sha256': json.loads((ROOT / 'data/distill/stage2-v2/manifest.json').read_text())['eval_gate_sha256'],
                'outputs_sha256': {s: digest(out / s) for s in ('train.jsonl', 'requests.jsonl', 'audit.jsonl')},
                'source_rows': len(source), 'rows': len(rows),
                'unchanged_teacher_rows': sum(a['action'] == 'keep' for a in audit),
                'rewritten_request_rows': sum(a['action'] in ('explicit_path', 'natural_abstain', 'clarified_request')
                                              for a in audit),
                'corrected_target_rows': sum(a['action'] == 'corrected_target' for a in audit),
                'model_authored_additions': sum(a['action'] == 'model_authored_addition' for a in audit),
                'rows_by_category': dict(sorted(Counter(r['category'] for r in revised).items())),
                'commands': commands, 'abstains': len(rows)-commands,
                'actions': actions, 'hard_leakage_hits': len({rid for rid, _, _ in hard}), 'hard_leakage_rows': len(blocked),
                'report_only_overlap_pairs': len(review), 'cue_abstains_before': old_cues,
                'cue_abstains_after': new_cues, 'repeated_exact_command_rows': sum(n-1 for n in command_counts.values())}
    if args.votes:
        from train_distill_cuda import split_validation
        manifest.update(v3_summary(rows, revised, provenance, read_jsonl(paths['v2_baseline'])))
        train, val = split_validation(rows, 0.05)
        train_commands = {rows[i]['messages'][-1]['content'] for i in train} - {''}
        manifest['grouped_split'] = {'fraction': 0.05, 'train_rows': len(train), 'val_rows': len(val),
                                    'val_ids': [rows[i]['id'] for i in val],
                                    'validation_commands_in_training': sum(rows[i]['messages'][-1]['content']
                                                                         in train_commands for i in val)}
        (out / 'cluster-provenance.jsonl').write_bytes(args.votes.read_bytes())
        manifest['outputs_sha256']['cluster-provenance.jsonl'] = digest(out / 'cluster-provenance.jsonl')
        (out / 'leakage-hits.jsonl').write_text(''.join(json.dumps({'id': rid, 'reason': reason, 'split': split},
                                                  sort_keys=True) + '\n' for rid, reason, split in hard))
        manifest['outputs_sha256']['leakage-hits.jsonl'] = digest(out / 'leakage-hits.jsonl')
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    (out / 'quality-report.md').write_text(f'''# Stage-2 dataset repair v2

Source: {len(source)} historical rows plus {len(additions_audit)} authored additions; retained: {len(rows)} ({commands} commands, {len(rows)-commands} abstentions, {(len(rows)-commands)/len(rows):.1%}).
Actions: `{json.dumps(actions, sort_keys=True)}`. Only `keep` rows are unchanged teacher evidence. `explicit_path`, `natural_abstain` and `clarified_request` keep the teacher target for a rewritten request the teacher never saw; `clarified_request` rows are command requests reworded to state the scope of the existing command. Corrected targets record votes for the new target (`teacher_votes`) and the old one (`original_target_votes`). Every training and request row carries `source_id` so family derivatives remain grouped when the trainer reads `train.jsonl` alone.

Training SHA-256: `{digest(out / 'train.jsonl')}`.
All input, output and evaluation-gate hashes are in `manifest.json`; per-source actions, reasons and valid stopped teacher vote counts are in `audit.jsonl`. The amendments pin the exact old request and target. Historical stage-1 files are unchanged.

Review method: amendments were reviewed individually and additions were targeted samples with recorded provenance, reason and verification. This does not certify every retained row or provide a measured precision estimate. No command was executed against user data. Unresolved semantics remain excluded or abstained.

v2 supersedes the published stage2-v1: v1 dropped leaked rows but kept their family's abstention siblings and labeled command clarifications as abstentions.

Missing-input abstentions were rewritten individually to ordinary underspecified requests while preserving the missing slot. Safety and impossible-task examples were retained. The diagnostic lexical-cue count (without/wihtout/haven't/unnamed/unspecified/unidentified) changed from {old_cues} to {new_cues}; this regex is a report, not a label rule. Remaining cues include legitimate permission/safety language. No class proportion was chosen from evaluation scores.

Explicit-path examples move a named operand into the serving `path` field and retain the teacher command. Original corpus rows had no path field: their prompts already matched serving with path=None. This repairs coverage, not a universal prompt mismatch. `requests.jsonl` is stage-2 lineage metadata (includes optional path), not an input to the original exact-schema corpus checker.

The existing evaluation leakage gate hit {len({rid for rid, _, _ in hard})} rows; their whole source families ({len(blocked)} rows) are excluded. Frozen and heldout were used only for leakage detection, never scored or used to tune repairs. {len(review)} report-only overlap pairs remain. Exact duplicate requests are excluded; {sum(n-1 for n in command_counts.values())} extra rows share an exact command across distinct requests. These are retained paraphrases; the trainer's grouped split also joins rows that share a command or a near-duplicate request. Validation loss is still not evidence of task improvement.

Limitations: synthetic phrasing, one teacher, small corpus, majority-vote selection bias and incomplete semantic verification remain. New sampling should collect natural missing-input requests paired with answerable counterparts, varied explicit paths, and realistic usage weighting. Repairs alone cannot establish deployment frequency or model gain. No training, evaluation scoring, or publication was performed.

Reproduce into a fresh directory from repository root:

```sh
PYTHONPATH=src .venv/bin/python tools/repair_distill_dataset.py --out-dir /tmp/whatisit-stage2-repro
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```

Compare `train.jsonl`, `requests.jsonl`, `audit.jsonl`, and `manifest.json` byte-for-byte. No network, teacher sampling or GPU is required.
''')
    if args.votes:
        (out / 'quality-report.md').write_text(f'''# Stage-2 data v3 equivalence re-label

Model review; not human-certified. Uses the registered voting rule, unchanged
serving filters, pinned v2 amendments, 36 authored additions and source families.
Original exact-majority strings are preserved; recovered labels record exact
`teacher_votes`, `vote_mode` and `cluster_votes` in the audit.

Retained: {len(rows)} rows ({commands} commands, {len(rows)-commands} abstentions).
Recovery/coverage counts and grouped split:

```json
{json.dumps({**v3_summary(rows, revised, provenance, read_jsonl(paths['v2_baseline'])), 'grouped_split': manifest['grouped_split']}, indent=2, sort_keys=True)}
```

Leakage: {manifest['hard_leakage_hits']} hard-hit ids, {len(blocked)} whole-family
rows excluded. Historical quarantine lists apply to all families. Hard-hit details
are in `leakage-hits.jsonl`; {len(review)} report-only overlap pairs remain.
Frozen/heldout contents are read only by the existing leakage gate. Their hashes
are the historical v2 manifest values, not fresh reads. Development scores are
not consulted. Repeated commands remain grouped in validation.

Actions: `{json.dumps(actions, sort_keys=True)}`. Model-authored additions retained:
{len([a for a in audit if a['action'] == 'model_authored_addition'])} after exclusions.
Model review and pinned-tokenizer preflight must pass before publication/training.
No generated command was executed against user data. No teacher sampling.

Reproduce with the same PATH as historical builders into a fresh directory:

```sh
PYTHONPATH=src .venv/bin/python tools/repair_distill_dataset.py --base-labels data/distill/v3-base/train.jsonl --out-dir /tmp/whatisit-v3-repro
```

Training SHA-256: `{digest(out / 'train.jsonl')}`. Every artifact is hashed in the
manifest; the manifest itself has an external checksum. A fresh build must match
byte-for-byte. Model review is recorded separately and has no human certification.
''')
    manifest['outputs_sha256']['quality-report.md'] = digest(out / 'quality-report.md')
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
