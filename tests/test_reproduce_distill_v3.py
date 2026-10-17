from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from reproduce_distill_v3 import restore_review_artifacts


class ReproductionTests(unittest.TestCase):
    def test_restores_fixed_review_only_after_identical_rebuild(self):
        with tempfile.TemporaryDirectory() as tmp:
            frozen, fresh = [Path(tmp) / name for name in ('frozen', 'fresh')]
            frozen.mkdir()
            fresh.mkdir()
            names = ('train.jsonl', 'requests.jsonl', 'audit.jsonl', 'cluster-provenance.jsonl',
                     'leakage-hits.jsonl', 'review-sample.jsonl')
            for name in names:
                (frozen / name).write_text(name)
                (fresh / name).write_text(name)
            for name in ('quality-report.md', 'merge-audit.md'):
                (fresh / name).write_text('rebuilt\n')
                (frozen / name).write_text('rebuilt\nfixed model review\n')
            (frozen / 'review-result.md').write_text('fixed model verdicts\n')
            manifest = {'inputs_sha256': {'raw': 'pinned', 'builder': 'original'},
                        'review': 'fixed model review',
                        'outputs_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                          for p in frozen.iterdir()}, 'rows': 60}
            (frozen / 'manifest.json').write_text(json.dumps(manifest))
            (frozen / 'SHA256SUMS').write_text(''.join(
                f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n'
                for p in sorted(frozen.iterdir()) if p.name != 'SHA256SUMS'))
            (fresh / 'manifest.json').write_text(json.dumps({**manifest,
                'review': 'model review pending',
                'inputs_sha256': {'raw': 'pinned', 'builder': 'current'}}))
            (fresh / 'train.jsonl').write_text('changed')
            with self.assertRaisesRegex(ValueError, 'train.jsonl'):
                restore_review_artifacts(fresh, frozen)
            self.assertFalse((fresh / 'review-result.md').exists())
            (fresh / 'train.jsonl').write_text('train.jsonl')
            restore_review_artifacts(fresh, frozen)
            self.assertEqual({p.name: p.read_bytes() for p in fresh.iterdir()},
                             {p.name: p.read_bytes() for p in frozen.iterdir()})
            manifest['review'] = 'tampered gate verdict'
            (frozen / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'checksum.*manifest.json'):
                restore_review_artifacts(fresh, frozen)
            manifest['review'] = 'fixed model review'
            manifest['outputs_sha256']['../outside'] = 'bad'
            (frozen / 'manifest.json').write_text(json.dumps(manifest))
            (frozen / 'SHA256SUMS').write_text(''.join(
                f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n'
                for p in sorted(frozen.iterdir()) if p.name != 'SHA256SUMS'))
            with self.assertRaisesRegex(ValueError, 'artifact name'):
                restore_review_artifacts(fresh, frozen)

    def test_cli_refuses_existing_directory_before_building(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, 'tools/reproduce_distill_v3.py', tmp],
                                    text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('fresh output directory', result.stderr)
