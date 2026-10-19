#!/usr/bin/env python3
"""Build the blind judge pool for the v4 verified-dataset campaign.

    PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH=src:tools \
        ~/.local/pipx/venvs/whatisit/bin/python tools/build_v4_pool.py \
        data/corpus/requests.jsonl data/teacher/roihu_full_raw_samples.jsonl \
        data/distill/stage2-v3 data/distill/stage2-v4/judge/pool \
        --batch-size 90 --controls data/distill/stage2-v4/judge/controls.jsonl \
        --controls-per-batch 3

Items: every v3 train row with a non-empty target (one candidate, its target) and
every corpus id outside v3 whose samples yield at least one lint-accepted command
(candidates: sorted distinct effective_command values; zero-candidate requests are
skipped with a manifest warning). No-majority candidates are re-checked with
repair_distill_dataset.validate_command (serving validation); a failing candidate
is excluded and listed in the manifest, and a request whose candidates are all
excluded is skipped like a zero-candidate one. A v3 row missing from v3
requests.jsonl or a non-v3 corpus id missing from the raw file raises ValueError;
batch_size and controls_per_batch must be >= 1. Items are sorted by rid, keys
x0000+ assigned in that order, then sliced into consecutive b00, b01, ... batches. Controls are
appended in file order, up to --controls-per-batch per batch, keys verbatim;
surplus controls are only warned about. Quarantine filtering happens in the
builder, not here. Writes keymap.json, batches/bXX.json, manifest.json and
controls-map.json (only when controls were injected) into out_dir.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from build_distill_dataset import read_jsonl


def build_pool(corpus_path, raw_path, v3_dir, out_dir, batch_size=90,
               controls_path=None, controls_per_batch=3, effective=None, validate=None):
    if effective is None:
        from score_teacher_eval import effective_command as effective
    if validate is None:
        from repair_distill_dataset import validate_command as validate
    if batch_size < 1:
        raise ValueError('batch_size must be >= 1')
    if controls_per_batch < 1:
        raise ValueError('controls_per_batch must be >= 1')
    v3_dir = Path(v3_dir)
    corpus = {row['id']: row for row in read_jsonl(Path(corpus_path))}
    raw = {row['id']: row for row in read_jsonl(Path(raw_path))}
    v3_rows = read_jsonl(v3_dir / 'train.jsonl')
    v3_requests = {row['id']: row for row in read_jsonl(v3_dir / 'requests.jsonl')}
    missing = [row['id'] for row in v3_rows if row['id'] not in v3_requests]
    if missing:
        raise ValueError(f'{len(missing)} v3 rows have no request in '
                         f'{v3_dir}/requests.jsonl: {", ".join(missing[:5])}')

    items, warnings = [], []
    for row in v3_rows:
        target = row['messages'][-1]['content']
        if target:
            items.append({'group': 'v3_kept', 'rid': row['id'],
                          'request': v3_requests[row['id']]['request'],
                          'candidates': [target]})
    v3_count = len(items)
    v3_ids = {row['id'] for row in v3_rows}
    considered = sorted(rid for rid in corpus if rid not in v3_ids)
    missing_raw = [rid for rid in considered if rid not in raw]
    if missing_raw:
        raise ValueError(f'{len(missing_raw)} corpus ids missing from {raw_path}: '
                         f'{", ".join(missing_raw[:5])}')
    excluded = []
    for rid in considered:
        request = raw[rid]['request']
        commands, had_candidates = [], False
        for command in sorted({effective(s, request) for s in raw[rid]['samples']} - {None}):
            had_candidates = True
            try:
                validate(rid, command, request)
            except ValueError:
                excluded.append({'rid': rid, 'command': command})
                continue
            commands.append(command)
        if commands:
            items.append({'group': 'no_majority', 'rid': rid, 'request': request,
                          'candidates': commands})
        elif had_candidates:
            warnings.append({'rid': rid, 'reason': 'all_candidates_excluded'})
        else:
            warnings.append({'rid': rid, 'reason': 'no_candidates'})
    items.sort(key=lambda item: item['rid'])

    keymap, keyed = {}, []
    for item in items:
        candidates = []
        for command in item['candidates']:
            key = f'x{len(keymap):04d}'
            keymap[key] = {'group': item['group'], 'rid': item['rid'], 'command': command}
            candidates.append({'key': key, 'command': command})
        keyed.append({'case': item['rid'], 'request': item['request'],
                      'candidates': candidates})
    batches = [{'batch': f'b{index // batch_size:02d}',
                'items': keyed[index:index + batch_size]}
               for index in range(0, len(keyed), batch_size)]

    controls_map = {}
    controls = read_jsonl(Path(controls_path)) if controls_path is not None else []
    for index, control in enumerate(controls):
        if index // controls_per_batch >= len(batches):
            warnings.append({'reason': 'controls_not_injected',
                             'keys': [c['key'] for c in controls[index:]]})
            break
        batches[index // controls_per_batch]['items'].append({
            'case': control['case'], 'request': control['request'],
            'candidates': [{'key': control['key'], 'command': control['command']}]})
        controls_map[control['key']] = {'expected': control['expected'],
                                        'source': control['source']}

    out = Path(out_dir)
    (out / 'batches').mkdir(parents=True, exist_ok=True)
    (out / 'keymap.json').write_text(json.dumps(keymap, indent=2) + '\n')
    for batch in batches:
        (out / 'batches' / f"{batch['batch']}.json").write_text(
            json.dumps(batch, indent=2) + '\n')
    if controls_map:
        (out / 'controls-map.json').write_text(json.dumps(controls_map, indent=2) + '\n')

    inputs = {'corpus': sha256(corpus_path), 'raw_samples': sha256(raw_path),
              'v3_train': sha256(v3_dir / 'train.jsonl'),
              'v3_requests': sha256(v3_dir / 'requests.jsonl')}
    if controls_path is not None:
        inputs['controls'] = sha256(controls_path)
    counts = {'v3_rows': len(v3_rows), 'v3_items': v3_count, 'v3_candidates': v3_count,
              'no_majority_considered': len(considered),
              'no_majority_with_candidates': len(items) - v3_count,
              'excluded_candidates': len(excluded),
              'items': len(keyed), 'candidates': len(keymap), 'batches': len(batches),
              'controls_injected': len(controls_map), 'controls_total': len(controls)}
    manifest = {'inputs_sha256': inputs, 'counts': counts, 'batch_size': batch_size,
                'excluded_candidates': excluded, 'warnings': warnings}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


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
    args = parser.parse_args()
    manifest = build_pool(args.corpus, args.raw_samples, args.v3_dir, args.out_dir,
                          batch_size=args.batch_size, controls_path=args.controls,
                          controls_per_batch=args.controls_per_batch)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
