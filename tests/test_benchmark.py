import unittest

from tools import benchmark


class BenchmarkTests(unittest.TestCase):
    def test_summary_uses_nearest_rank_p95(self):
        self.assertEqual(benchmark.summarize([9.0, 1.0, 4.0, 2.0]),
                         {'samples': 4, 'median': 3.0, 'p95': 9.0, 'max': 9.0})

    def test_empty_sample_set_is_rejected(self):
        with self.assertRaises(ValueError):
            benchmark.summarize([])
