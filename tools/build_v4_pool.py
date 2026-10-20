#!/usr/bin/env python3
"""Build the blind judge pool for the v4 verified-dataset campaign.

    PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH=src:tools \
        ~/.local/pipx/venvs/whatisit/bin/python tools/build_v4_pool.py \
        data/corpus/requests.jsonl data/teacher/roihu_full_raw_samples.jsonl \
        data/distill/stage2-v3 data/distill/stage2-v4/judge/pool \
        --batch-size 90 --controls data/distill/stage2-v4/judge/controls.jsonl \
        --controls-per-batch 3

Items: every v3 train row with a non-empty target (one candidate, its target; a v3
request carrying a `path` gets the explicit-inputs line appended, byte-identical to
the training prompt) and every corpus id outside v3 whose samples yield at least one
lint-accepted command (candidates: sorted distinct effective_command values;
zero-candidate requests are skipped with a manifest warning). All non-empty v3 targets and no-majority candidates
are re-checked with repair_distill_dataset.validate_command (serving validation); a
failing candidate is excluded with its reason in the manifest, and a request whose
candidates are all excluded is skipped like a zero-candidate one. A v3 row missing
from v3 requests.jsonl or a non-v3 corpus id missing from the raw file raises
ValueError; batch_size and controls_per_batch must be >= 1.

Judge-visible identifiers are opaque and uniform: every case is ``c`` + 12 hex
digits and every candidate key is ``k`` + 12 hex digits, derived deterministically
from the control seed. Real items and controls use the same format. Items are sorted
by rid and sliced into consecutive b00, b01, ... batches before controls are
allocated.

Controls are mandatory when ``--controls`` is supplied. Each batch must receive at
least one expected-correct and one expected-incorrect control. The allocation is
stratified and seeded: one control of each polarity per batch, then the remaining
controls are shuffled into the remaining per-batch slots. Total control count must
fit ``batches * controls_per_batch``; insufficiency is an error, never a warning.
Controls are shuffled with the real items of their batch using a per-batch seeded
RNG, so their placement carries no marker. The keymap assigns each control key to
its true identity; ``controls-map.json`` and ``director-map.json`` are director-only
and contain expected verdicts and provenance. Quarantine filtering happens in the
builder, not here.

Writes keymap.json, batches/bXX.json, manifest.json, director-map.json and (when
controls are supplied) controls-map.json into out_dir. The manifest records SHA-256
digests of every input and every generated artifact.
"""
import argparse
import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

from build_distill_dataset import read_jsonl

CONTROL_FIELDS = {'case', 'command', 'expected', 'key', 'request', 'source'}
CONTROL_OPTIONAL = {'provenance'}
EXPECTED_VALUES = {'correct', 'incorrect'}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def opaque_id(prefix, seed, *parts):
    """Deterministic opaque identifier; the same (prefix, seed, parts) gives the same id."""
    material = '\x1f'.join([str(seed), prefix, *[str(part) for part in parts]])
    return prefix + hashlib.sha256(material.encode()).hexdigest()[:12]


def load_controls(path):
    rows = read_jsonl(Path(path))
    if not rows:
        raise ValueError(f'controls file {path} is empty')
    keys, cases, sources, pairs = set(), set(), set(), set()
    for line, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f'{path}:{line}: control is not an object')
        missing = CONTROL_FIELDS - set(row)
        extra = set(row) - CONTROL_FIELDS - CONTROL_OPTIONAL
        if missing or extra:
            raise ValueError(f'{path}:{line}: control fields missing={sorted(missing)} '
                             f'unexpected={sorted(extra)}')
        for field in ('key', 'case', 'request', 'command', 'source'):
            if not isinstance(row[field], str) or not row[field].strip():
                raise ValueError(f'{path}:{line}: control {field} must be a non-empty string')
        if row['expected'] not in EXPECTED_VALUES:
            raise ValueError(f'{path}:{line}: control expected must be one of '
                             f'{sorted(EXPECTED_VALUES)}')
        if 'provenance' in row and (not isinstance(row['provenance'], str) or
                                    not row['provenance'].strip()):
            raise ValueError(f'{path}:{line}: control provenance must be a non-empty string')
        if row['key'] in keys:
            raise ValueError(f'{path}:{line}: duplicate control key {row["key"]}')
        if row['case'] in cases:
            raise ValueError(f'{path}:{line}: duplicate control case {row["case"]}')
        if row['source'] in sources:
            raise ValueError(f'{path}:{line}: duplicate control source {row["source"]}; '
                             'controls must be independent')
        pair = (row['request'], row['command'])
        if pair in pairs:
            raise ValueError(f'{path}:{line}: duplicate control request/command pair')
        keys.add(row['key'])
        cases.add(row['case'])
        sources.add(row['source'])
        pairs.add(pair)
    return rows


def allocate_controls(controls, batch_count, controls_per_batch, seed):
    """Return per-batch control indices with one of each polarity in every batch."""
    if not controls:
        return [[] for _ in range(batch_count)]
    if batch_count < 1:
        raise ValueError('cannot allocate controls without batches')
    if controls_per_batch < 2:
        raise ValueError('controls_per_batch must be >= 2 when controls are supplied; '
                         'each batch needs one correct and one incorrect control')
    capacity = batch_count * controls_per_batch
    if len(controls) > capacity:
        raise ValueError(f'insufficient control capacity: {len(controls)} controls for '
                         f'{batch_count} batches at {controls_per_batch}/batch '
                         f'(capacity {capacity}); refusing to leave controls unused')
    positives = [index for index, control in enumerate(controls)
                 if control['expected'] == 'correct']
    negatives = [index for index, control in enumerate(controls)
                 if control['expected'] == 'incorrect']
    if len(positives) < batch_count:
        raise ValueError(f'insufficient correct controls: {len(positives)} for '
                         f'{batch_count} batches; every batch needs one')
    if len(negatives) < batch_count:
        raise ValueError(f'insufficient incorrect controls: {len(negatives)} for '
                         f'{batch_count} batches; every batch needs one')
    rng = random.Random(seed)
    rng.shuffle(positives)
    rng.shuffle(negatives)
    assigned = [[] for _ in range(batch_count)]
    for batch in range(batch_count):
        assigned[batch].extend((positives[batch], negatives[batch]))
    remaining = positives[batch_count:] + negatives[batch_count:]
    slots = [batch for batch in range(batch_count)
             for _ in range(controls_per_batch - 2)]
    rng.shuffle(remaining)
    rng.shuffle(slots)
    if len(remaining) > len(slots):
        raise ValueError('control capacity accounting failed')
    for slot, index in zip(slots, remaining):
        assigned[slot].append(index)
    if sorted(index for batch in assigned for index in batch) != list(range(len(controls))):
        raise ValueError('control allocation did not account for every control')
    for batch, indices in enumerate(assigned):
        if {controls[index]['expected'] for index in indices} != EXPECTED_VALUES:
            raise ValueError(f'batch b{batch:02d} control allocation is not mixed-polarity')
    return assigned


def exclusion(rid, command, error):
    return {'rid': rid, 'command': command,
            'reason': str(error).encode('unicode_escape').decode()[:1000]}


def pool_population(corpus, raw, v3_rows, v3_requests, effective, validate):
    """Use the serving boundary for every non-empty training candidate."""
    missing = [row['id'] for row in v3_rows if row['id'] not in v3_requests]
    if missing:
        raise ValueError(f'{len(missing)} v3 rows have no request in '
                         f'v3 requests: {", ".join(missing[:5])}')

    items, warnings, excluded = [], [], []
    for row in v3_rows:
        target = row['messages'][-1]['content']
        if target:
            request = v3_requests[row['id']]['request']
            path = v3_requests[row['id']].get('path')
            try:
                validate(row['id'], target, request, path)
            except ValueError as exc:
                excluded.append(exclusion(row['id'], target, exc))
                continue
            if path is not None:
                request += '\nExplicit inputs: ' + json.dumps({'path': path}, ensure_ascii=False)
            items.append({'group': 'v3_kept', 'rid': row['id'], 'request': request,
                          'candidates': [(target, 1)]})
    v3_ids = {row['id'] for row in v3_rows}
    considered = sorted(rid for rid in corpus if rid not in v3_ids)
    missing_raw = [rid for rid in considered if rid not in raw]
    if missing_raw:
        raise ValueError(f'{len(missing_raw)} corpus ids missing from raw samples: '
                         f'{", ".join(missing_raw[:5])}')
    for rid in considered:
        request = raw[rid]['request']
        complete = {sample['command'] for sample in raw[rid]['samples']
                    if sample.get('parsed') is True and sample.get('finish_reason') == 'stop'
                    and isinstance(sample.get('command'), str) and sample['command']}
        rejected = set()
        # Audit complete teacher commands before effective() hides policy failures as None.
        for command in sorted(complete):
            try:
                validate(rid, command, request, raw[rid].get('path'))
            except ValueError as exc:
                rejected.add(command)
                excluded.append(exclusion(rid, command, exc))
        counts = Counter(effective(sample, request, raw[rid].get('path')) for sample in raw[rid]['samples'])
        commands, had_candidates = [], bool(complete)
        for command in sorted(set(counts) - {None}):
            had_candidates = True
            if command in rejected:
                continue
            if command not in complete:
                try:
                    validate(rid, command, request, raw[rid].get('path'))
                except ValueError as exc:
                    excluded.append(exclusion(rid, command, exc))
                    continue
            commands.append((command, counts[command]))
        if commands:
            if raw[rid].get('path') is not None:
                request += '\nExplicit inputs: ' + json.dumps({'path': raw[rid]['path']}, ensure_ascii=False)
            items.append({'group': 'no_majority', 'rid': rid, 'request': request,
                          'candidates': commands})
        elif had_candidates:
            warnings.append({'rid': rid, 'reason': 'all_candidates_excluded'})
        else:
            warnings.append({'rid': rid, 'reason': 'no_candidates'})
    items.sort(key=lambda item: item['rid'])

    return items, warnings, excluded


def build_pool(corpus_path, raw_path, v3_dir, out_dir, batch_size=90,
               controls_path=None, controls_per_batch=3, effective=None, validate=None,
               control_seed=13):
    if effective is None:
        from score_teacher_eval import effective_command as effective
    if validate is None:
        from repair_distill_dataset import validate_command as validate
    if batch_size < 1:
        raise ValueError('batch_size must be >= 1')
    if controls_per_batch < 1:
        raise ValueError('controls_per_batch must be >= 1')
    controls = load_controls(controls_path) if controls_path is not None else []
    if controls and controls_per_batch < 2:
        raise ValueError('controls_per_batch must be >= 2 when controls are supplied')
    v3_dir = Path(v3_dir)
    corpus = {row['id']: row for row in read_jsonl(Path(corpus_path))}
    raw = {row['id']: row for row in read_jsonl(Path(raw_path))}
    v3_rows = read_jsonl(v3_dir / 'train.jsonl')
    v3_requests = {row['id']: row for row in read_jsonl(v3_dir / 'requests.jsonl')}
    items, warnings, excluded = pool_population(corpus, raw, v3_rows, v3_requests,
                                                effective, validate)
    v3_count = sum(item['group'] == 'v3_kept' for item in items)
    v3_ids = {row['id'] for row in v3_rows}
    considered = sorted(set(corpus) - v3_ids)

    real_cases, real_keys = set(), set()
    keymap, keyed = {}, []
    for item in items:
        case = opaque_id('c', control_seed, item['group'], item['rid'])
        if case in real_cases:
            raise ValueError(f'opaque case collision for {item["rid"]}: {case}')
        real_cases.add(case)
        candidates = []
        for command, count in item['candidates']:
            key = opaque_id('k', control_seed, item['group'], item['rid'], command)
            if key in real_keys:
                raise ValueError(f'opaque key collision for {item["rid"]}: {key}')
            real_keys.add(key)
            keymap[key] = {'case': case, 'group': item['group'], 'rid': item['rid'],
                           'command': command, 'count': count}
            candidates.append({'key': key, 'command': command})
        candidates.sort(key=lambda candidate: candidate['key'])
        keyed.append({'case': case, 'request': item['request'], 'candidates': candidates})
    keymap = {key: keymap[key] for key in sorted(keymap)}

    batches = [{'batch': f'b{index // batch_size:02d}',
                'items': keyed[index:index + batch_size]}
               for index in range(0, len(keyed), batch_size)]

    controls_map, controls_summary = {}, {}
    if controls:
        if not batches:
            raise ValueError('cannot inject controls: the pool has no batches')
        assigned = allocate_controls(controls, len(batches), controls_per_batch,
                                     control_seed)
        control_cases, control_keys = set(), set()
        entries = []
        for index, control in enumerate(controls):
            case = opaque_id('c', control_seed, 'control', control['source'], control['key'])
            key = opaque_id('k', control_seed, 'control', control['source'], control['key'])
            if case in real_cases or case in control_cases:
                raise ValueError(f'control case collision: {case}')
            if key in real_keys or key in control_keys:
                raise ValueError(f'control key collision: {key}')
            control_cases.add(case)
            control_keys.add(key)
            entry = {'case': case, 'expected': control['expected'],
                     'source': control['source'], 'request': control['request'],
                     'command': control['command'], 'origin_case': control['case'],
                     'origin_key': control['key']}
            if 'provenance' in control:
                entry['provenance'] = control['provenance']
            entries.append((case, key, entry))
        for batch_index, (batch, indices) in enumerate(zip(batches, assigned)):
            summary = Counter()
            for index in indices:
                case, key, entry = entries[index]
                batch['items'].append({'case': case, 'request': entry['request'],
                                       'candidates': [{'key': key,
                                                       'command': entry['command']}]})
                controls_map[key] = entry
                summary[entry['expected']] += 1
            controls_summary[batch['batch']] = {
                'correct': summary['correct'], 'incorrect': summary['incorrect']}
            if set(summary) != EXPECTED_VALUES:
                raise ValueError(f'{batch["batch"]}: control allocation lacks mixed polarity')
            # Shuffle controls with real items so placement is not a marker.
            random.Random(f'{control_seed}:{batch["batch"]}').shuffle(batch['items'])
        controls_map = {key: controls_map[key] for key in sorted(controls_map)}

    out = Path(out_dir)
    if out.exists() and any(out.iterdir()):
        raise ValueError(f'output directory {out} is not empty; move it aside or delete it '
                         'before re-running')
    (out / 'batches').mkdir(parents=True, exist_ok=True)
    (out / 'keymap.json').write_text(json.dumps(keymap, indent=2) + '\n')
    for batch in batches:
        (out / 'batches' / f"{batch['batch']}.json").write_text(
            json.dumps(batch, indent=2) + '\n')
    if controls_map:
        (out / 'controls-map.json').write_text(json.dumps(controls_map, indent=2) + '\n')

    director = {}
    for key, entry in keymap.items():
        case_entry = director.setdefault(entry['case'], {
            'kind': 'real', 'group': entry['group'], 'rid': entry['rid'], 'candidates': []})
        case_entry['candidates'].append({'key': key, 'command': entry['command']})
    for key, entry in controls_map.items():
        director[entry['case']] = {
            'kind': 'control', 'candidates': [{'key': key, 'command': entry['command']}],
            'expected': entry['expected'], 'source': entry['source'],
            'request': entry['request'], 'origin_case': entry['origin_case'],
            'origin_key': entry['origin_key']}
        if 'provenance' in entry:
            director[entry['case']]['provenance'] = entry['provenance']
    for entry in director.values():
        entry['candidates'].sort(key=lambda candidate: candidate['key'])
    director = {case: director[case] for case in sorted(director)}
    (out / 'director-map.json').write_text(json.dumps(director, indent=2) + '\n')

    inputs = {'corpus': sha256(corpus_path), 'raw_samples': sha256(raw_path),
              'v3_train': sha256(v3_dir / 'train.jsonl'),
              'v3_requests': sha256(v3_dir / 'requests.jsonl')}
    if controls_path is not None:
        inputs['controls'] = sha256(controls_path)
    artifacts = {'keymap': sha256(out / 'keymap.json'),
                 'director_map': sha256(out / 'director-map.json'),
                 'batches': {batch['batch']: sha256(out / 'batches' /
                                                    f"{batch['batch']}.json")
                             for batch in batches}}
    if controls_map:
        artifacts['controls_map'] = sha256(out / 'controls-map.json')
    counts = {'v3_rows': len(v3_rows), 'v3_items': v3_count, 'v3_candidates': v3_count,
              'v3_policy_rejected': sum(entry['rid'] in v3_ids for entry in excluded),
              'no_majority_considered': len(considered),
              'no_majority_with_candidates': len(items) - v3_count,
              'excluded_candidates': len(excluded),
              'items': len(keyed), 'candidates': len(keymap), 'batches': len(batches),
              'controls_injected': len(controls_map), 'controls_total': len(controls),
              'controls_correct': sum(1 for control in controls
                                      if control['expected'] == 'correct'),
              'controls_incorrect': sum(1 for control in controls
                                        if control['expected'] == 'incorrect')}
    from repair_distill_dataset import validation_fingerprint
    manifest = {'validation': validation_fingerprint(), 'inputs_sha256': inputs, 'artifacts_sha256': artifacts,
                'counts': counts, 'batch_size': batch_size,
                'control_seed': control_seed, 'controls_per_batch': controls_per_batch,
                'controls_by_batch': controls_summary,
                'excluded_candidates': excluded, 'warnings': warnings}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('corpus', type=Path)
    parser.add_argument('raw_samples', type=Path)
    parser.add_argument('v3_dir', type=Path)
    parser.add_argument('out_dir', type=Path)
    parser.add_argument('--batch-size', type=int, default=90)
    parser.add_argument('--controls', type=Path, default=None)
    parser.add_argument('--controls-per-batch', type=int, default=3)
    parser.add_argument('--control-seed', type=int, default=13)
    args = parser.parse_args()
    manifest = build_pool(args.corpus, args.raw_samples, args.v3_dir, args.out_dir,
                          batch_size=args.batch_size, controls_path=args.controls,
                          controls_per_batch=args.controls_per_batch,
                          control_seed=args.control_seed)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
