import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RoihuFullQuarantineTests(unittest.TestCase):
    def test_request_exclusions_and_invalid_mdls_row_are_absent_from_training(self):
        quarantine = ROOT / 'data/distill/roihu_full_quarantine_ids.txt'
        excluded = {
            line.split('#', 1)[0].strip()
            for line in quarantine.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith('#')
        }
        expected = {
            'r00910', 'r01014', 'r02051', 'r00177', 'r01465', 'r01179', 'r02203',
            'r00487', 'r01311', 'r01473', 'r00849', 'r01220', 'r00617', 'r01402',
            'r01979', 'r00006',
        }
        self.assertTrue(expected <= excluded)

        train = ROOT / 'data/distill/roihu_full_train.jsonl'
        training_ids = {json.loads(line)['id'] for line in train.read_text().splitlines()}
        self.assertTrue(expected.isdisjoint(training_ids))


if __name__ == '__main__':
    unittest.main()
