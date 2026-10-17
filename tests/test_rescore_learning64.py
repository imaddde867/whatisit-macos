#!/usr/bin/env python3
"""Regression tests for rescore_learning64.py (unittest-discoverable).

Covers three-state scoring semantics (no false improvements/regressions from
unresolved), conservative paired comparison, strict adjudication validation and
determinism.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
import rescore_learning64 as R


def _case(cid, group, accepted):
    return {"type": "case", "case": {"id": cid, "group": group},
            "accepted": accepted, "verdict": "ok" if accepted else "needs_review"}


def _write_results(d, model, group, cases):
    (Path(d) / f'results-{model}-{group}.jsonl').write_text(
        ''.join(json.dumps(c) + '\n' for c in cases))


class Scenario:
    """Six-fit-case scenario:
      a base:accepted / adapter:accepted -> both_correct
      b base:rejected+incorrect / adapter:accepted -> improvement
      c base:accepted / adapter:rejected+incorrect -> regression
      d base:rejected+incorrect / adapter:rejected+incorrect -> both_incorrect
      e base:rejected+unresolved / adapter:accepted -> unresolved pair
    """

    def __init__(self):
        self.d = tempfile.mkdtemp()
        _write_results(self.d, 'base', 'fit', [
            _case('a', 'fit', True), _case('b', 'fit', False),
            _case('c', 'fit', True), _case('d', 'fit', False),
            _case('e', 'fit', False)])
        _write_results(self.d, 'adapter', 'fit', [
            _case('a', 'fit', True), _case('b', 'fit', True),
            _case('c', 'fit', False), _case('d', 'fit', False),
            _case('e', 'fit', True)])
        self.bp = Path(self.d) / 'base-adj.json'
        self.ap = Path(self.d) / 'adapter-adj.json'
        self.bp.write_text(json.dumps([
            {"id": "b", "model": "base", "group": "fit", "semantic_verdict": "incorrect"},
            {"id": "d", "model": "base", "group": "fit", "semantic_verdict": "incorrect"},
            {"id": "e", "model": "base", "group": "fit", "semantic_verdict": "unresolved"}]))
        self.ap.write_text(json.dumps([
            {"id": "c", "model": "adapter", "group": "fit", "semantic_verdict": "incorrect"},
            {"id": "d", "model": "adapter", "group": "fit", "semantic_verdict": "incorrect"}]))

    def run(self, out=None):
        out = out or str(Path(self.d) / 'out.json')
        rc = R.main(['r', self.d, str(self.ap), str(self.bp), out])
        data = json.loads(Path(out).read_text()) if Path(out).exists() else None
        return rc, data

    def add_base(self, entry):
        data = json.loads(self.bp.read_text()); data.append(entry)
        Path(str(self.bp) + '.mut').write_text(json.dumps(data))
        rc = R.main(['r', self.d, str(self.ap), str(self.bp) + '.mut', str(Path(self.d) / 'x.json')])
        return rc


class ThreeStateTests(unittest.TestCase):
    def test_three_state_and_paired_semantics(self):
        rc, out = Scenario().run()
        self.assertEqual(rc, 0)
        bs = out['group_summaries']['base-fit']
        ad = out['group_summaries']['adapter-fit']
        self.assertEqual((bs['confirmed_correct'], bs['confirmed_incorrect'], bs['unresolved']), (2, 2, 1))
        self.assertEqual((bs['allowlist_accepted'], bs['adjudicated_correct']), (2, 0))
        self.assertEqual((bs['correct_lower_bound'], bs['correct_upper_bound']), (2, 3))
        self.assertEqual((ad['confirmed_correct'], ad['confirmed_incorrect'], ad['unresolved']), (3, 2, 0))
        comp = out['comparisons']['fit']
        self.assertEqual(comp['improvements'], 1)
        self.assertEqual(comp['improvement_cases'], ['b'])
        self.assertEqual(comp['regressions'], 1)
        self.assertEqual(comp['regression_cases'], ['c'])
        self.assertEqual(comp['unresolved_pairs'], 1)
        self.assertTrue(any(p['case_id'] == 'e' for p in comp['unresolved_pair_detail']))
        self.assertEqual(out['paired_totals'],
                         {'improvements': 1, 'regressions': 1, 'unresolved_pairs': 1})

    def test_determinism(self):
        s = Scenario()
        o1 = Path(s.d) / 'o1.json'; o2 = Path(s.d) / 'o2.json'
        R.main(['r', s.d, str(s.ap), str(s.bp), str(o1)])
        R.main(['r', s.d, str(s.ap), str(s.bp), str(o2)])
        self.assertEqual(o1.read_text(), o2.read_text(),
                         "repeated runs must be byte-identical")


class ValidationTests(unittest.TestCase):
    def test_duplicate_adjudication_rejected(self):
        rc = Scenario().add_base({"id": "b", "model": "base", "group": "fit",
                                   "semantic_verdict": "correct"})
        self.assertEqual(rc, 3)

    def test_unknown_case_id_rejected(self):
        rc = Scenario().add_base({"id": "zzz", "model": "base", "group": "fit",
                                   "semantic_verdict": "incorrect"})
        self.assertEqual(rc, 3)

    def test_missing_source_record_rejected(self):
        # adjudicating an allowlist-ACCEPTED case (not a rejection) must fail
        rc = Scenario().add_base({"id": "a", "model": "base", "group": "fit",
                                   "semantic_verdict": "correct"})
        self.assertEqual(rc, 3)

    def test_mismatched_model_rejected(self):
        rc = Scenario().add_base({"id": "d", "model": "adapter", "group": "fit",
                                   "semantic_verdict": "incorrect"})
        self.assertEqual(rc, 3)

    def test_mismatched_group_rejected(self):
        rc = Scenario().add_base({"id": "b", "model": "base", "group": "operand",
                                   "semantic_verdict": "correct"})
        self.assertEqual(rc, 3)

    def test_contradictory_adjudication_rejected(self):
        rc = Scenario().add_base({"id": "b", "model": "base", "group": "fit",
                                   "semantic_verdict": "incorrect"})
        self.assertEqual(rc, 3)

    def test_malformed_verdict_rejected(self):
        rc = Scenario().add_base({"id": "b", "model": "base", "group": "fit",
                                   "semantic_verdict": "MAYBE"})
        self.assertEqual(rc, 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
