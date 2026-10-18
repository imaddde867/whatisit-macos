#!/usr/bin/env python3
"""Select the v4 confirm sample and write blind pass-2 judge batches.

    PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH=src:tools \
        ~/.local/pipx/venvs/whatisit/bin/python tools/make_v4_confirm.py \
        data/distill/stage2-v4/judge/pool/keymap.json \
        data/teacher/roihu_full_raw_samples.jsonl data/distill/stage2-v3/requests.jsonl \
        data/distill/stage2-v4/judge/verdicts data/distill/stage2-v4/judge/confirm \
        --sample 0.2 --seed 13 --batch-size 90

Selection reuses build_verified_dataset.load_verdicts and .select (the same rules
the builder applies): a v3_kept key is selected when its key was judged correct; a
no_majority key is selected when select() over the fresh effective_command counts
of its judged-correct candidates is not None. Pass-2 verdicts do not exist yet and
are not read; the builder drops confirm-rejected labels later. The rid-sorted
selected list is sampled with random.Random(seed), sorted again by rid, and sliced
into b00, b01, ... batches whose items carry the same keys and requests as the
pool. Writes bXX.json and manifest.json into out_dir.
"""
import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

from build_distill_dataset import read_jsonl


def build_confirm(keymap_path, raw_path, v3_requests_path, verdict_dir, out_dir,
                  sample=0.2, seed=13, batch_size=90, effective=None):
    if effective is None:
        from score_teacher_eval import effective_command as effective
    from build_verified_dataset import load_verdicts, select
    keymap = json.loads(Path(keymap_path).read_text())
    raw = {row['id']: row for row in read_jsonl(Path(raw_path))}
    v3_requests = {row['id']: row for row in read_jsonl(Path(v3_requests_path))}
    correct = {key for key, verdict in load_verdicts(verdict_dir).items()
               if verdict == 'correct'}

    by_rid = {}
    for key, entry in keymap.items():
        by_rid.setdefault((entry['group'], entry['rid']), []).append((key, entry['command']))
    items = []
    for (group, rid), candidates in sorted(by_rid.items(), key=lambda kv: kv[0][1]):
        if group == 'v3_kept':
            chosen = any(key in correct for key, _ in candidates)
            request = v3_requests[rid]['request']
        else:
            request = raw[rid]['request']
            counts = Counter(effective(s, request) for s in raw[rid]['samples'])
            chosen = select({command: counts[command]
                             for key, command in candidates if key in correct}) is not None
        if chosen:
            items.append({'case': rid, 'request': request,
                          'candidates': [{'key': key, 'command': command}
                                         for key, command in candidates]})

    picked = sorted(random.Random(seed).sample(items, round(len(items) * sample)),
                    key=lambda item: item['case'])
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for index in range(0, len(picked), batch_size):
        batch = {'batch': f'b{index // batch_size:02d}',
                 'items': picked[index:index + batch_size]}
        (out / f"{batch['batch']}.json").write_text(json.dumps(batch, indent=2) + '\n')
    manifest = {'selected_total': len(items), 'sampled': len(picked), 'sample': sample,
                'seed': seed, 'batch_size': batch_size}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
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
    args = parser.parse_args()
    manifest = build_confirm(args.keymap, args.raw_samples, args.v3_requests,
                             args.verdict_dir, args.out_dir, sample=args.sample,
                             seed=args.seed, batch_size=args.batch_size)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
