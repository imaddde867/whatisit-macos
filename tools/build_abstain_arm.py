#!/usr/bin/env python3
"""Build the unpublished 8.5% empty-target experiment arm without rewriting rows."""

import hashlib
import json
from pathlib import Path
import random
import sys


def build(source: Path, output: Path):
    raw = source.read_bytes()
    lines = raw.splitlines(keepends=True)
    rows = [json.loads(line) for line in lines]
    ids = [row['id'] for row in rows]
    if not rows or len(set(ids)) != len(ids):
        raise ValueError('source must contain nonempty unique records')
    empty = [i for i, row in enumerate(rows) if row['messages'][2]['content'] == '']
    commands = len(rows) - len(empty)
    count = commands * 85 // 915
    if count > len(empty):
        raise ValueError('not enough empty rows for the 8.5% arm')
    kept = set(random.Random(20261014).sample(empty, count))
    data = b''.join(line for i, line in enumerate(lines) if i not in empty or i in kept)
    manifest = {'source': str(source), 'source_sha256': hashlib.sha256(raw).hexdigest(),
                'seed': 20261014, 'target_empty_fraction': 0.085,
                'kept_empty_ids': [ids[i] for i in empty if i in kept],
                'dropped_empty_ids': [ids[i] for i in empty if i not in kept],
                'counts': {'command': commands, 'empty': count,
                           'dropped_empty': len(empty) - count, 'total': commands + count},
                'output_sha256': hashlib.sha256(data).hexdigest()}
    output.mkdir(parents=True, exist_ok=False)
    (output / 'train.jsonl').write_bytes(data)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (output / 'README.md').write_text(
        '# Empty-target experiment arm B\n\n'
        'Experiment arm, not a published dataset. Keeps every v3 command row and a\n'
        'random.Random(20261014) subsample of empty targets, in original order and\n'
        'byte-identical. Empty count is floor(command_count * 85 / 915), so the\n'
        'result is at most 8.5% empty. The manifest records every kept/dropped ID.\n')


if __name__ == '__main__':
    build(Path(sys.argv[1]), Path(sys.argv[2]))
