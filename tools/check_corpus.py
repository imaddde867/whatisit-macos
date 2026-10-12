#!/usr/bin/env python3
"""Validate a training-request corpus: schema, duplicates, and overlap with the eval sets.

    python3 tools/check_corpus.py data/corpus/requests.jsonl

Exit code 0 means the file is usable. Run from the repository root (eval sets are read from eval/).
"""

import collections
import json
import re
import sys
from pathlib import Path

KEYS = {'id', 'request', 'category', 'kind', 'style', 'source'}
KINDS = {'answer', 'abstain'}
STYLES = {'terse', 'chatty', 'formal', 'typo'}
CATEGORIES = {'files-and-folders', 'text-processing', 'search', 'processes-and-ports', 'network',
              'disk-and-storage', 'system-info', 'git-and-dev', 'archives-and-media',
              'macos-tools', 'power-and-hardware', 'security-and-apps', 'abstain'}


def words(text):
    return set(re.findall(r'[a-z0-9_.~/-]+', text.casefold()))


def jaccard(a, b):
    return len(a & b) / len(a | b) if a | b else 0.0


def main(path):
    rows, errors = [], []
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            errors.append(f'line {number}: invalid JSON ({error})')
            continue
        if set(row) != KEYS:
            errors.append(f'line {number}: keys must be exactly {sorted(KEYS)}')
            continue
        if not isinstance(row['request'], str) or not 3 <= len(row['request']) <= 300 or '\n' in row['request']:
            errors.append(f'line {number}: request must be 3-300 chars on one line')
        if row['kind'] not in KINDS:
            errors.append(f'line {number}: kind must be one of {sorted(KINDS)}')
        if row['style'] not in STYLES:
            errors.append(f'line {number}: style must be one of {sorted(STYLES)}')
        if row['category'] not in CATEGORIES:
            errors.append(f'line {number}: unknown category {row["category"]!r}')
        if (row['kind'] == 'abstain') != (row['category'] == 'abstain'):
            errors.append(f'line {number}: kind abstain and category abstain must go together')
        rows.append(row)
    ids = collections.Counter(r['id'] for r in rows)
    errors += [f'duplicate id {i}' for i, c in ids.items() if c > 1]

    eval_requests = []
    for name in ('dev', 'everyday', 'frozen'):
        for line in Path(f'eval/{name}.jsonl').read_text().splitlines():
            eval_requests.append((name, json.loads(line)['request']))
    eval_words = [(n, r.casefold().strip(), words(r)) for n, r in eval_requests]

    seen, near_dupes, eval_hits = {}, [], []
    token_sets = [(r['id'], words(r['request'])) for r in rows]
    for row, (rid, ws) in zip(rows, token_sets):
        key = re.sub(r'\W+', ' ', row['request'].casefold()).strip()
        if key in seen:
            errors.append(f'{rid}: exact duplicate of {seen[key]}')
        seen[key] = rid
        for name, text, ews in eval_words:
            if key == re.sub(r'\W+', ' ', text).strip() or jaccard(ws, ews) >= 0.7:
                eval_hits.append((rid, name, row['request']))
    for i in range(len(token_sets)):          # O(n^2) is fine for a few thousand requests
        for j in range(i + 1, len(token_sets)):
            if jaccard(token_sets[i][1], token_sets[j][1]) >= 0.85:
                near_dupes.append((token_sets[i][0], token_sets[j][0]))

    abstain = sum(r['kind'] == 'abstain' for r in rows)
    print(f'requests: {len(rows)}   abstain: {abstain} ({100 * abstain / max(len(rows), 1):.1f}%)')
    print('by category:', dict(sorted(collections.Counter(r['category'] for r in rows).items())))
    print('by style:   ', dict(sorted(collections.Counter(r['style'] for r in rows).items())))
    print(f'near-duplicate pairs within corpus (jaccard >= 0.85): {len(near_dupes)}')
    print(f'overlap with eval sets (exact or jaccard >= 0.7): {len(eval_hits)}')
    for item in eval_hits[:10]:
        print('  ', item)
    if len(rows) < 2000:
        errors.append(f'need at least 2000 requests, found {len(rows)}')
    if not 8 <= 100 * abstain / max(len(rows), 1) <= 14:
        errors.append('abstain share must be between 8% and 14%')
    if eval_hits:
        errors.append(f'{len(eval_hits)} requests overlap the eval sets')
    if len(near_dupes) > 0.01 * len(rows):
        errors.append('too many near-duplicates (>1% of rows)')
    for error in errors[:40]:
        print('ERROR', error)
    print('OK' if not errors else f'FAILED: {len(errors)} problem(s)')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
