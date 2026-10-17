"""Build stage-2 data without relabeling or overwriting historical artifacts."""

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from build_distill_dataset import check_inputs, eval_leakage, read_jsonl
from whatisit_macos.local_recovery_worker import MACOS_PREFIX

ROOT = Path(__file__).resolve().parents[1]
CUES = re.compile(r"\bwithout\b|\bwihtout\b|haven't|unnamed|unspecified|unidentified", re.I)


def validate_command(rid, command, request):
    if not command:
        return
    if len(command) > 4096 or any(c in command for c in '\x00\r\n'):
        raise ValueError(f'{rid}: invalid command')
    from whatisit import safety
    from whatisit_macos.maclint import problems, unrequested_deletion
    from build_distill_dataset import INTERACTIVE
    findings = safety.check(command)
    issues = problems(command) + unrequested_deletion(command, request)
    issues += [f'{m.group(0)!r} is a placeholder' for m in safety.PLACEHOLDER_HINT.finditer(command)
               if m.group(0).casefold() not in request.casefold()]
    if any(severity == 'DANGER' for severity, _ in findings) or issues or INTERACTIVE.fullmatch(command):
        raise ValueError(f'{rid}: command fails serving validation')


def repair(requests, labels, raw, amendments):
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
        if target and votes < 3:
            raise ValueError(f'{rid}: target lacks teacher majority')
        if not target and votes < 3 and request['kind'] != 'abstain':
            raise ValueError(f'{rid}: abstention lacks provenance')
        edit = edits.get(rid)
        item = {'id': rid, 'source_id': rid, 'teacher_votes': votes,
                'action': 'keep', 'reason': 'unchanged teacher target'}
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
                validate_command(rid, target, request['request'])
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
            validate_command(rid, row['messages'][-1]['content'], new_request)
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
        validate_command(rid, item['target'], item['request'])
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir', type=Path, default=ROOT / 'data/distill/stage2-v2')
    args = parser.parse_args()
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
    requests, raw, _ = check_inputs(paths['requests'], paths['raw'], paths['teacher_manifest'])
    source = read_jsonl(paths['stage1'])
    rows, revised, audit = repair(requests, source, raw, read_jsonl(paths['amendments']))
    rows, revised, additions_audit = add_additions(
        rows, revised, read_jsonl(paths['additions']), source[0]['messages'][0]['content'])
    audit.extend(additions_audit)
    # Frozen and heldout contents are consumed only by the existing leakage gate.
    hard, review = eval_leakage(revised, rows, ROOT / 'eval')
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
    manifest = {'version': 'stage2-v2', 'review': 'reviewed amendments and targeted samples; not human-certified',
                'inputs_sha256': {k: digest(v) for k, v in paths.items()},
                'eval_gate_sha256': {s: digest(ROOT / f'eval/{s}.jsonl') for s in ('dev', 'everyday', 'frozen', 'heldout')},
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
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
