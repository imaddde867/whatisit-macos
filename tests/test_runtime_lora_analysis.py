from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from analyze_runtime_lora import mcnemar


class AnalysisTests(unittest.TestCase):
    def test_exact_mcnemar_counts_both_discordant_directions(self):
        self.assertEqual(mcnemar([True]*6+[False]*2, [False]*6+[True]*2),
                         {'wins': 6, 'losses': 2, 'p': 0.2890625})
        self.assertEqual(mcnemar([True], [True]), {'wins': 0, 'losses': 0, 'p': 1.0})
        self.assertEqual(mcnemar([True]*6, [False]*6)['p'], 0.03125)

    def test_case_bootstrap_preserves_seed_means_and_fixed_rng(self):
        from analyze_runtime_lora import bootstrap
        self.assertEqual(bootstrap([1.0]*141), [141.0, 141.0])
        self.assertEqual(bootstrap([0.0]*141), [0.0, 0.0])
        interval = bootstrap([1.0, -1.0])
        self.assertEqual(interval, [-2.0, 2.0])
        self.assertEqual(interval, bootstrap([1.0, -1.0]))

    def test_summary_uses_five_of_eight_and_answerable_rejection_kinds(self):
        from analyze_runtime_lora import summarize
        cases = {'x': {'accept': 'pwd', 'split': 'dev'},
                 'y': {'accept': 'pwd', 'split': 'dev'},
                 'z': {'accept': None, 'split': 'everyday'}}
        seeds = []
        for s in range(8):
            seeds.append({'x': {'label': 'pass' if s < 5 else 'rejected',
                                'command': 'pwd' if s < 5 else None,
                                'no_command_kind': 'other' if s < 5 else 'empty_output'},
                          'y': {'label': 'pass' if s < 4 else 'rejected',
                                'command': 'pwd' if s < 4 else None,
                                'no_command_kind': 'other' if s < 4 else 'empty_output'},
                          'z': {'label': 'abstain-missed', 'command': 'ls',
                                'no_command_kind': 'other'}})
        result = summarize(seeds, cases, [False, True, False])
        self.assertEqual(result['seed_scores'], [2, 2, 2, 2, 1, 0, 0, 0])
        self.assertEqual(result['mean'], 1.125)
        self.assertAlmostEqual(result['sd'], (55/56)**.5)
        self.assertEqual(result['majority'], [True, False, False])
        self.assertEqual(result['majority_score'], 1)
        self.assertEqual(result['mcnemar'], {'wins': 1, 'losses': 1, 'p': 1.0})
        self.assertEqual(result['mean_empty_on_answerable'], .875)
        self.assertEqual(result['mean_lint_rejected_on_answerable'], 0)
        self.assertEqual(result['mean_abstain_missed'], 1)
        self.assertEqual(result['agreement'], {'all_eight': 0, 'none': 1, 'mixed': 2})
        with self.assertRaises(ValueError):
            summarize(seeds[:7], cases, [False, True, False])

    def test_rules_keep_registered_inclusive_and_strict_thresholds(self):
        from analyze_runtime_lora import rules
        a = {'mean': 76, 'sd': 4, 'mcnemar': {'p': .049}, 'mean_accepted_wrong': 42}
        b = {'mean': 74, 'sd': 2, 'mean_empty_on_answerable': 5}
        self.assertEqual(rules(a, b, 68, 40), {'R1': True, 'R2': True, 'R3': False})
        a['mcnemar']['p'] = .05
        b['mean_empty_on_answerable'] = 5.01
        self.assertEqual(rules(a, b, 68, 40), {'R1': False, 'R2': False, 'R3': False})
        a.update(mean=72.99, mcnemar={'p': .2001})
        self.assertTrue(rules(a, b, 68, 40)['R3'])
        a['mean'] = 73
        self.assertFalse(rules(a, b, 68, 40)['R3'])

    def test_budget_fails_only_above_registered_limits(self):
        from analyze_runtime_lora import budget
        default = {'sampled_mean_rss_bytes': 1000, 'sampled_peak_rss_bytes': 2000,
                   'eval': {'dev': 'p50 0.20s', 'everyday': 'p50 0.22s'}}
        candidate = {'sampled_mean_rss_bytes': 1000+64*1024**2,
                     'sampled_peak_rss_bytes': 2000+64*1024**2,
                     'eval': {'dev': 'p50 0.25s', 'everyday': 'p50 0.27s'}}
        self.assertFalse(budget(candidate, default)['fails'])
        candidate['sampled_mean_rss_bytes'] += 1
        self.assertTrue(budget(candidate, default)['fails'])
        candidate['sampled_mean_rss_bytes'] -= 1
        candidate['eval']['dev'] = 'p50 0.26s'
        self.assertTrue(budget(candidate, default)['fails'])
