from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
try:
    from build_verified_dataset import select
except ImportError as error:  # score_teacher_eval needs the upstream whatisit package
    raise unittest.SkipTest(str(error))


class SelectTests(unittest.TestCase):
    def test_none_correct_gives_no_label(self):
        self.assertIsNone(select({}))

    def test_largest_equivalence_cluster_wins_over_single_most_frequent_string(self):
        counts = {'ls -l -a': 1, 'ls -a -l': 1, 'ls -la .': 0, 'find . -maxdepth 1': 2}
        self.assertIn(select(counts), {'ls -l -a', 'ls -a -l'})

    def test_within_cluster_most_frequent_then_shortest(self):
        self.assertEqual(select({'stat -f %B a.txt': 2, 'stat  -f %B a.txt': 3}), 'stat  -f %B a.txt')
        self.assertEqual(select({'wc -l a': 1, 'wc -l  a': 1}), 'wc -l a')


if __name__ == '__main__':
    unittest.main()
