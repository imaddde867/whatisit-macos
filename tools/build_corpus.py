#!/usr/bin/env python3
"""Merge authored batch files into data/corpus/requests.jsonl (ids, shuffle, balanced pilot block).

    python3 tools/build_corpus.py 'data/corpus/batches/*.jsonl' data/corpus/requests.jsonl

Batch lines need: request, category, kind, style, source. The first 100 output rows are a stratified pilot;
the rest are shuffled with a fixed seed. Exact duplicates (case/punctuation-insensitive) are dropped.
"""

import collections
import glob
import json
import random
import re
import sys
from pathlib import Path


def main(pattern, out):
    rows, seen = [], set()
    for path in sorted(glob.glob(pattern)):
        for line in Path(path).read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            key = re.sub(r'\W+', ' ', row['request'].casefold()).strip()
            if key in seen:
                continue
            seen.add(key)
            rows.append({k: row[k] for k in ('request', 'category', 'kind', 'style', 'source')})
    rng = random.Random(7)
    rng.shuffle(rows)
    by_cat = collections.defaultdict(list)
    for row in rows:
        by_cat[row['category']].append(row)
    quotas = {c: 100 * len(v) / len(rows) for c, v in by_cat.items()}
    take = {c: int(q) for c, q in quotas.items()}
    for c in sorted(quotas, key=lambda c: quotas[c] - take[c], reverse=True)[:100 - sum(take.values())]:
        take[c] += 1
    pilot = [r for c, v in by_cat.items() for r in v[:take[c]]]
    rng.shuffle(pilot)
    ids = {id(r) for r in pilot}
    ordered = pilot + [r for r in rows if id(r) not in ids]
    with open(out, 'w') as f:
        for number, row in enumerate(ordered, 1):
            f.write(json.dumps({'id': f'r{number:05d}', **row}, ensure_ascii=False) + '\n')
    print(f'{len(ordered)} requests written to {out}; pilot = first 100 '
          f'({sum(r["kind"] == "abstain" for r in pilot)} abstain)')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
