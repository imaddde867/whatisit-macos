#!/usr/bin/env python3
"""Select the v4 confirm sample and write blind pass-2 judge batches.

    PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH=src:tools \
        ~/.local/pipx/venvs/whatisit/bin/python tools/make_v4_confirm.py \
        data/distill/stage2-v4/judge/pool/keymap.json \
        data/teacher/roihu_full_raw_samples.jsonl data/distill/stage2-v3/requests.jsonl \
        data/distill/stage2-v4/judge/verdicts data/distill/stage2-v4/judge/confirm \
        --sample 0.2 --seed 13 --batch-size 90

The director stage is bound to the exact pool and pass-1 judgments. It verifies the
pool manifest, keymap, controls map and batch digests; strictly re-loads every
pass-1 verdict against its immutable batch; and re-derives the selected labels with
the same rules as the builder (`v3_kept`: any correct key; `no_majority`: the
judged-correct candidates still `select()` a target). The rid-sorted selected list
is sampled with `random.Random(seed)`; the picked items are sorted by their opaque
case id and sliced into b00, b01, ... batches. Confirm batches carry the same opaque
case ids, candidate keys, requests and commands as the pool.

The manifest records the pool/keymap/raw/v3-request/pass-1 digests, the exact
selected and sampled identities, and the digests of the generated batches. It refuses
to write into a non-empty directory, so stale batch files can never be read as
current. A keymap candidate whose fresh teacher frequency differs from its recorded
count raises ValueError (candidate-string drift is not enough to hide frequency
drift).
"""
import argparse
import json
import sys
from pathlib import Path

from build_distill_dataset import read_jsonl


def _load_json(path, label):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f'{label} file {path} does not exist')
    return json.loads(path.read_text())


def _prepare_out(path):
    path = Path(path)
    if path.exists() and any(path.iterdir()):
        raise ValueError(f'output directory {path} is not empty; move it aside or delete it '
                         'before re-running')
    path.mkdir(parents=True, exist_ok=True)


def build_confirm(keymap_path, raw_path, v3_requests_path, verdict_dir, out_dir,
                  sample=0.2, seed=13, batch_size=90, effective=None, pool_dir=None):
    if effective is None:
        from score_teacher_eval import effective_command as effective
    from build_verified_dataset import (canonical_sha256, expected_confirm_batches,
                                        hash_json_files, load_batches, load_verdicts,
                                        sample_record, selected_items, sha256_file)
    keymap_path = Path(keymap_path)
    pool_dir = Path(pool_dir) if pool_dir is not None else keymap_path.parent
    keymap = _load_json(keymap_path, 'keymap')
    pool_keymap = _load_json(pool_dir / 'keymap.json', 'pool keymap')
    if pool_keymap != keymap:
        raise ValueError('keymap does not match the pool keymap')
    pool_manifest = _load_json(pool_dir / 'manifest.json', 'pool manifest')
    controls_map = _load_json(pool_dir / 'controls-map.json', 'pool controls map')
    _load_json(pool_dir / 'director-map.json', 'pool director map')
    pool_batches = load_batches(pool_dir / 'batches', 'pool batches')
    artifacts = pool_manifest.get('artifacts_sha256', {})
    expected_artifacts = {
        'keymap': sha256_file(pool_dir / 'keymap.json'),
        'controls_map': sha256_file(pool_dir / 'controls-map.json'),
        'director_map': sha256_file(pool_dir / 'director-map.json'),
        'batches': hash_json_files(pool_dir / 'batches', pool_batches),
    }
    if artifacts != expected_artifacts:
        raise ValueError('pool artifacts do not match the pool manifest; rebuild the pool')
    inputs = pool_manifest.get('inputs_sha256', {})
    for name, path in (('raw_samples', raw_path), ('v3_requests', v3_requests_path)):
        if inputs.get(name) != sha256_file(path):
            raise ValueError(f'{name} changed since the pool was built; refusing to confirm')
    if pool_manifest.get('counts', {}).get('controls_total', 0) < 1:
        raise ValueError('pool has no controls; refusing to build a confirmation sample')

    raw = {row['id']: row for row in read_jsonl(Path(raw_path))}
    v3_requests = {row['id']: row for row in read_jsonl(Path(v3_requests_path))}
    verdicts = load_verdicts(verdict_dir, pool_batches, keymap=keymap,
                             controls=controls_map,
                             require_keys=set(keymap) | set(controls_map))
    selected = selected_items(keymap, verdicts, raw, v3_requests, effective)
    expected_batches, picked = expected_confirm_batches(selected, sample, seed, batch_size)
    _prepare_out(out_dir)
    out = Path(out_dir)
    for name, batch in expected_batches.items():
        (out / f'{name}.json').write_text(json.dumps(batch, indent=2) + '\n')
    manifest = {
        'selected_total': len(selected), 'sampled': len(picked),
        'sample': sample, 'seed': seed, 'batch_size': batch_size,
        'selected': sample_record(selected), 'sample_cases': sample_record(picked),
        'inputs_sha256': {
            'pool_manifest': sha256_file(pool_dir / 'manifest.json'),
            'keymap': sha256_file(pool_dir / 'keymap.json'),
            'raw_samples': sha256_file(raw_path),
            'v3_requests': sha256_file(v3_requests_path),
            'pass1_verdicts': canonical_sha256(verdicts),
            'pass1_verdict_files': hash_json_files(verdict_dir, pool_batches),
        },
        'artifacts_sha256': hash_json_files(out, expected_batches),
    }
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('keymap', type=Path)
    parser.add_argument('raw_samples', type=Path)
    parser.add_argument('v3_requests', type=Path)
    parser.add_argument('verdict_dir', type=Path)
    parser.add_argument('out_dir', type=Path)
    parser.add_argument('--sample', type=float, default=0.2)
    parser.add_argument('--seed', type=int, default=13)
    parser.add_argument('--batch-size', type=int, default=90)
    parser.add_argument('--pool-dir', type=Path, default=None)
    args = parser.parse_args()
    manifest = build_confirm(args.keymap, args.raw_samples, args.v3_requests,
                             args.verdict_dir, args.out_dir, sample=args.sample,
                             seed=args.seed, batch_size=args.batch_size,
                             pool_dir=args.pool_dir)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
