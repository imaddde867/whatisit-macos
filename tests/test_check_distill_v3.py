import sys
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import check_distill_v3 as check


class V3ReviewTests(unittest.TestCase):
    def test_stratified_sample_is_reproducible_and_respects_population(self):
        rows = [{'id': str(i), 'category': 'a' if i < 8 else 'b'} for i in range(10)]
        sample = check.stratified_sample(rows, 5)
        self.assertEqual(len(sample), 5)
        self.assertEqual(sum(r['category'] == 'a' for r in sample), 4)
        self.assertEqual(sample, check.stratified_sample(list(reversed(rows)), 5))
        self.assertEqual(check.stratified_sample(rows, 10), sorted(rows, key=lambda r: r['id']))
        with self.assertRaises(ValueError):
            check.stratified_sample(rows, 11)

    def test_wilson_interval_is_not_a_wald_interval(self):
        low, high = check.wilson(60, 60)
        self.assertAlmostEqual(low, 0.939828, places=5)
        self.assertAlmostEqual(high, 1)
        low, high = check.wilson(30, 60)
        self.assertAlmostEqual(low, 0.37735, places=4)
        self.assertAlmostEqual(high, 0.62265, places=4)
        with self.assertRaises(ValueError):
            check.wilson(61, 60)

    def test_review_cli_validates_sample_and_records_failed_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = [{'id': str(i), 'messages': [{'content': 'x'}]} for i in range(64)]
            requests = [{'id': str(i), 'category': 'c', 'request': 'Read x.'} for i in range(64)]
            provenance = [{'id': str(i), 'cluster_votes': 3, 'strings': ['x', '"x"']} for i in range(64)]
            for name, records in [('train.jsonl', rows), ('requests.jsonl', requests),
                                  ('cluster-provenance.jsonl', provenance)]:
                (root / name).write_text(''.join(json.dumps(r) + '\n' for r in records))
            (root / 'manifest.json').write_text('{"outputs_sha256": {}}')
            with patch.object(sys, 'argv', ['check', str(root)]), contextlib.redirect_stdout(io.StringIO()):
                check.main()
            self.assertEqual(len(check.read_jsonl(root / 'review-sample.jsonl')), 60)
            self.assertIn('## 63 (3 votes)', (root / 'merge-audit.md').read_text())
            sample = check.read_jsonl(root / 'review-sample.jsonl')
            changed = [{'id': r['id'], 'messages': [{'content': 'changed'}]} for r in rows]
            (root / 'train.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in changed))
            early = root / 'early.jsonl'
            early.write_text(''.join(json.dumps({'id': r['id'], 'verdict': 'OK', 'notes': 'Old verdict.'}) + '\n'
                                      for r in sample))
            with patch.object(sys, 'argv', ['check', str(root), '--verdicts', str(early)]):
                with self.assertRaisesRegex(ValueError, 'changed'):
                    check.main()
            (root / 'train.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in rows))
            verdicts = [{'id': r['id'], 'verdict': 'wrong' if i < 10 else 'OK', 'notes': 'Fixture verdict.'}
                        for i, r in enumerate(sample)]
            path = root / 'review-verdicts.jsonl'
            path.write_text(''.join(json.dumps(r) + '\n' for r in verdicts))
            with patch.object(sys, 'argv', ['check', str(root), '--verdicts', str(path)]), \
                    contextlib.redirect_stdout(io.StringIO()):
                check.main()
            manifest = json.loads((root / 'manifest.json').read_text())
            self.assertFalse(manifest['model_review']['gate_passed'])
            self.assertEqual(manifest['model_review']['verdicts'], {'OK': 50, 'wrong': 10})
            self.assertIn('STOP — FAIL', (root / 'review-result.md').read_text())
            self.assertIn('review-verdicts.jsonl', manifest['outputs_sha256'])
            with patch.object(sys, 'argv', ['check', str(root)]):
                with self.assertRaises(FileExistsError):
                    check.main()


if __name__ == '__main__':
    unittest.main()
