from pathlib import Path
import hashlib
import json
import random
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from build_abstain_arm import build


class AbstainArmTests(unittest.TestCase):
    def test_seeded_subsample_preserves_bytes_order_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / 'source.jsonl', Path(tmp) / 'arm'
            rows = [{'id': str(i), 'source_id': f'family{i}',
                     'messages': [None, None, {'content': '' if i % 2 == 0 else 'pwd'}]}
                    for i in range(200)]
            lines = [(json.dumps(r, indent=None) + ' \n').encode() for r in rows]
            source.write_bytes(b''.join(lines))
            build(source, output)
            keep = set(random.Random(20261014).sample(list(range(0, 200, 2)), 9))
            expected = b''.join(line for i, line in enumerate(lines) if i % 2 or i in keep)
            self.assertEqual((output / 'train.jsonl').read_bytes(), expected)
            manifest = json.loads((output / 'manifest.json').read_text())
            self.assertEqual(manifest['output_sha256'], hashlib.sha256(expected).hexdigest())
            self.assertEqual(manifest['counts'], {'command': 100, 'empty': 9, 'dropped_empty': 91, 'total': 109})
            self.assertEqual(manifest['kept_empty_ids'], [str(i) for i in sorted(keep)])
            self.assertEqual(manifest['dropped_empty_ids'], [str(i) for i in range(0, 200, 2) if i not in keep])
            with self.assertRaises(FileExistsError):
                build(source, output)
            self.assertEqual((output / 'train.jsonl').read_bytes(), expected)
