"""Rebuild v3 labels/lineage and reuse pinned model-review evidence byte-for-byte."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def restore_review_artifacts(fresh, frozen):
    checked = set()
    for line in (frozen / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        if Path(name).name != name or name in ('.', '..', 'SHA256SUMS') or name in checked:
            raise ValueError('invalid frozen checksum artifact name')
        path = frozen / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'frozen checksum differs: {name}')
        checked.add(name)
    if checked != {p.name for p in frozen.iterdir() if p.name != 'SHA256SUMS'}:
        raise ValueError('frozen checksum file set differs')
    manifest = json.loads((frozen / 'manifest.json').read_text())
    for name, digest in manifest['outputs_sha256'].items():
        if Path(name).name != name or name in ('.', '..'):
            raise ValueError('invalid frozen artifact name')
        path = frozen / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f'frozen artifact hash differs: {name}')
    for name in ('train.jsonl', 'requests.jsonl', 'audit.jsonl', 'cluster-provenance.jsonl',
                 'leakage-hits.jsonl', 'review-sample.jsonl'):
        if (fresh / name).read_bytes() != (frozen / name).read_bytes():
            raise ValueError(f'rebuilt artifact differs: {name}')
    for name in ('quality-report.md', 'merge-audit.md'):
        if not (frozen / name).read_bytes().startswith((fresh / name).read_bytes()):
            raise ValueError(f'rebuilt report differs: {name}')
    rebuilt = json.loads((fresh / 'manifest.json').read_text())
    for name, value in rebuilt.items():
        if name not in ('inputs_sha256', 'outputs_sha256', 'review') and manifest.get(name) != value:
            raise ValueError(f'rebuilt manifest differs: {name}')
    for name, digest in rebuilt['inputs_sha256'].items():
        # The post-freeze EQUALS guard changes source hash, not any label or lineage.
        if name != 'builder' and manifest['inputs_sha256'].get(name) != digest:
            raise ValueError(f'rebuild input differs: {name}')
    for path in frozen.iterdir():
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'non-file frozen artifact: {path.name}')
    for path in frozen.iterdir():
        shutil.copyfile(path, fresh / path.name)
    if {p.name: p.read_bytes() for p in fresh.iterdir()} != {p.name: p.read_bytes() for p in frozen.iterdir()}:
        raise ValueError('full frozen package differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError('choose a fresh output directory')
    with tempfile.TemporaryDirectory(prefix='whatisit-v3-rebuild-') as tmp:
        base = Path(tmp) / 'base'
        subprocess.run([sys.executable, 'tools/build_distill_dataset.py',
                        '--raw', 'data/teacher/roihu_full_raw_samples.jsonl',
                        '--manifest', 'data/teacher/roihu_full_manifest.json',
                        '--quarantine', 'data/distill/roihu_full_quarantine_ids.txt',
                        '--vote', 'equivalence', '--out', str(base / 'train.jsonl'),
                        '--report', str(base / 'quality-report.md'),
                        '--review-sample', str(base / 'review.jsonl')], cwd=ROOT, check=True)
        subprocess.run([sys.executable, 'tools/repair_distill_dataset.py',
                        '--base-labels', str(base / 'train.jsonl'), '--out-dir', str(output)],
                       cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        subprocess.run([sys.executable, 'tools/check_distill_v3.py', str(output)], cwd=ROOT, check=True)
        restore_review_artifacts(output, ROOT / 'data/distill/stage2-v3')
    print('Full frozen package is byte-identical; fixed model-review evidence reused.')


if __name__ == '__main__':
    main()
