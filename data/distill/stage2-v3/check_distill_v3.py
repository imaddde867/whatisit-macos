"""Prepare the registered merge/model review, then record its fixed-sample verdicts."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random

from build_distill_dataset import read_jsonl

SEED = 314159


def stratified_sample(rows, size=60):
    if not 0 < size <= len(rows):
        raise ValueError('insufficient recovered rows for the registered review')
    groups = {}
    for row in sorted(rows, key=lambda r: r['id']):
        groups.setdefault(row['category'], []).append(row)
    quotas = {c: len(rs) * size / len(rows) for c, rs in groups.items()}
    cuts = {c: int(q) for c, q in quotas.items()}
    for c in sorted(groups, key=lambda c: (-(quotas[c] - cuts[c]), c))[:size - sum(cuts.values())]:
        cuts[c] += 1
    rng = random.Random(SEED)
    return sorted([r for c in sorted(groups) for r in rng.sample(groups[c], cuts[c])], key=lambda r: r['id'])


def wilson(ok, total):
    if not 0 <= ok <= total or not total:
        raise ValueError('invalid precision counts')
    z = 1.959963984540054
    p, denominator = ok / total, 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0, center - radius), min(1, center + radius)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--verdicts', type=Path)
    args = parser.parse_args()
    root = args.directory
    rows = {r['id']: r for r in read_jsonl(root / 'train.jsonl')}
    requests = {r['id']: r for r in read_jsonl(root / 'requests.jsonl')}
    provenance = read_jsonl(root / 'cluster-provenance.jsonl')
    recovered = [{'id': p['id'], 'category': requests[p['id']]['category'],
                  'request': requests[p['id']]['request'], 'target': rows[p['id']]['messages'][-1]['content']}
                 for p in provenance if p['id'] in rows and rows[p['id']]['messages'][-1]['content']]
    sample = stratified_sample(recovered)
    if args.verdicts is None:
        if any((root / name).exists() for name in ('merge-audit.md', 'review-sample.jsonl')):
            raise FileExistsError('model review artifacts already exist')
        audit = ['# Equivalence merge audit (model review)', '',
                 'Every recovered multi-string cluster is listed below, including excluded rows.', '']
        for p in provenance:
            if len(p['strings']) > 1:
                audit += [f"## {p['id']} ({p['cluster_votes']} votes)", '',
                          requests[p['id']]['request'] if p['id'] in requests else 'Excluded by repair.', '',
                          '```json', json.dumps(p['strings'], ensure_ascii=False, indent=2), '```', '']
        (root / 'merge-audit.md').write_text('\n'.join(audit))
        (root / 'review-sample.jsonl').write_text(''.join(json.dumps(r, sort_keys=True, ensure_ascii=False) + '\n'
                                                       for r in sample))
        print(json.dumps({'population': len(recovered), 'sample': len(sample), 'seed': SEED}))
        return
    verdicts = read_jsonl(args.verdicts)
    if (len(verdicts) != 60 or {v['id'] for v in verdicts} != {s['id'] for s in sample} or
            any(v.get('verdict') not in ('OK', 'debatable', 'wrong') or not v.get('notes') for v in verdicts)):
        raise ValueError('verdicts do not match the registered sample')
    if (root / 'review-result.md').exists():
        raise FileExistsError('review result already exists')
    counts = Counter(v['verdict'] for v in verdicts)
    low, high = wilson(counts['OK'], 60)
    passed = counts['wrong'] + counts['debatable'] <= 9
    result = f'''# Data v3 model review

Model review, not human review. Seed {SEED}; 60 of {len(recovered)} recovered
command rows, proportional category strata with largest-remainder allocation.
Only OK counts as correct. OK: {counts['OK']}; debatable: {counts['debatable']};
wrong: {counts['wrong']}. Precision: {counts['OK']/60:.1%}; Wilson 95% interval:
[{low:.1%}, {high:.1%}]. This estimates synthetic recovered-label precision,
not deployment accuracy. Stratification is nearly proportional; Wilson is a
descriptive binomial interval, not a design-weighted survey interval.

Gate: **{'PASS' if passed else 'STOP — FAIL'}** (at most 9 non-OK rows).
Each row was judged for request correctness, stock-macOS flags and safety.
Local man pages and scratch-only read checks are documented in the verdict notes.
No generated writes, deletes, sudo or network changes were executed.
No evaluation scores were used to select these labels.

| id | category | verdict | model review notes |
|---|---|---|---|
'''
    by_id = {s['id']: s for s in sample}
    for v in sorted(verdicts, key=lambda r: r['id']):
        notes = v['notes'].replace('|', '\\|').replace('\n', ' ')
        result += f"| {v['id']} | {by_id[v['id']]['category']} | {v['verdict']} | {notes} |\n"
    (root / 'review-result.md').write_text(result)
    manifest = json.loads((root / 'manifest.json').read_text())
    manifest['model_review'] = {'seed': SEED, 'sample_rows': 60, 'population': len(recovered),
                               'verdicts': dict(sorted(counts.items())), 'precision': counts['OK']/60,
                               'wilson_95': [low, high], 'gate_passed': passed}
    for path in sorted(root.iterdir()):
        if path.is_file() and path.name not in ('manifest.json', 'SHA256SUMS'):
            manifest['outputs_sha256'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (root / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')
    (root / 'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n'
                                            for p in sorted(root.iterdir()) if p.is_file() and p.name != 'SHA256SUMS'))
    print(json.dumps(manifest['model_review'], sort_keys=True))


if __name__ == '__main__':
    main()
