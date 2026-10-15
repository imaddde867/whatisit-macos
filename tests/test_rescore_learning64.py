#!/usr/bin/env python3
"""Regression tests for rescore_learning64.py.

Covers the three-state scoring semantics (no false improvements/regressions
from unresolved), conservative paired comparison, strict adjudication
validation (duplicates, unknown ids, missing source records, mismatched
model/group, contradictions, malformed verdicts) and determinism.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'tools'))
import rescore_learning64 as R


def _case(cid, group, accepted):
    return {"type": "case", "case": {"id": cid, "group": group},
            "accepted": accepted, "verdict": "ok" if accepted else "needs_review"}


def _write_results(d, model, group, cases):
    (Path(d) / f'results-{model}-{group}.jsonl').write_text(
        ''.join(json.dumps(c) + '\n' for c in cases))


def _scenario():
    """A temp dir with base+adapter fit results and a few adjudications.

    Layout (fit, 6 cases):
      a: base accepted(correct) / adapter accepted(correct) -> both_correct
      b: base rejected+correct / adapter accepted(correct)    -> improvement
      c: base accepted(correct) / adapter rejected+incorrect -> regression
      d: base rejected+incorrect / adapter rejected+incorrect -> both_incorrect
      e: base rejected+unresolved / adapter accepted(correct) -> unresolved pair
    """
    d = tempfile.mkdtemp()
    _write_results(d, 'base', 'fit', [
        _case('a', 'fit', True), _case('b', 'fit', False),
        _case('c', 'fit', True), _case('d', 'fit', False),
        _case('e', 'fit', False),
    ])
    _write_results(d, 'adapter', 'fit', [
        _case('a', 'fit', True), _case('b', 'fit', True),
        _case('c', 'fit', False), _case('d', 'fit', False),
        _case('e', 'fit', True),
    ])
    base_adj = [
        {"id": "b", "model": "base", "group": "fit", "semantic_verdict": "incorrect"},
        {"id": "d", "model": "base", "group": "fit", "semantic_verdict": "incorrect"},
        {"id": "e", "model": "base", "group": "fit", "semantic_verdict": "unresolved"},
    ]
    adapter_adj = [
        {"id": "c", "model": "adapter", "group": "fit", "semantic_verdict": "incorrect"},
        {"id": "d", "model": "adapter", "group": "fit", "semantic_verdict": "incorrect"},
    ]
    bp = Path(d) / 'base-adj.json'
    ap = Path(d) / 'adapter-adj.json'
    bp.write_text(json.dumps(base_adj))
    ap.write_text(json.dumps(adapter_adj))
    return d, bp, ap


def _run(d, bp, ap):
    out = Path(d) / 'out.json'
    rc = R.main(['rescore', d, str(ap), str(bp), str(out)])
    return rc, json.loads(out.read_text()) if out.exists() else None


def test_three_state_and_paired_semantics():
    d, bp, ap = _scenario()
    rc, out = _run(d, bp, ap)
    assert rc == 0, "valid scenario should succeed"
    bs = out['group_summaries']['base-fit']
    ad = out['group_summaries']['adapter-fit']
    # base: a correct(allowlist), b incorrect(adj), c correct(allowlist),
    #       d incorrect(adj), e unresolved(adj)
    assert bs['confirmed_correct'] == 2 and bs['confirmed_incorrect'] == 2 and bs['unresolved'] == 1
    assert bs['allowlist_accepted'] == 2 and bs['adjudicated_correct'] == 0
    assert bs['correct_lower_bound'] == 2 and bs['correct_upper_bound'] == 3
    # adapter: a correct(allow), b correct(allow), c incorrect(adj),
    #          d incorrect(adj), e correct(allow)
    assert ad['confirmed_correct'] == 3 and ad['confirmed_incorrect'] == 2 and ad['unresolved'] == 0
    comp = out['comparisons']['fit']
    assert comp['improvements'] == 1 and comp['improvement_cases'] == ['b']
    assert comp['regressions'] == 1 and comp['regression_cases'] == ['c']
    # e is an unresolved pair, never an improvement even though adapter is correct
    assert comp['unresolved_pairs'] == 1
    assert any(p['case_id'] == 'e' for p in comp['unresolved_pair_detail'])
    assert out['paired_totals'] == {'improvements': 1, 'regressions': 1, 'unresolved_pairs': 1}
    print("✓ test_three_state_and_paired_semantics")


def test_determinism():
    d, bp, ap = _scenario()
    o1 = Path(d) / 'o1.json'; o2 = Path(d) / 'o2.json'
    R.main(['r', d, str(ap), str(bp), str(o1)])
    R.main(['r', d, str(ap), str(bp), str(o2)])
    assert o1.read_text() == o2.read_text(), "repeated runs must be byte-identical"
    print("✓ test_determinism")


def test_duplicate_adjudication_rejected():
    d, bp, ap = _scenario()
    data = json.loads(bp.read_text())
    data.append({"id": "b", "model": "base", "group": "fit", "semantic_verdict": "correct"})
    bp.write_text(json.dumps(data))
    rc = R.main(['r', d, str(ap), str(bp), str(Path(d) / 'x.json')])
    assert rc == 3, "duplicate adjudication must fail"
    print("✓ test_duplicate_adjudication_rejected")


def test_unknown_case_id_rejected():
    d, bp, ap = _scenario()
    data = json.loads(bp.read_text())
    data.append({"id": "zzz", "model": "base", "group": "fit", "semantic_verdict": "incorrect"})
    bp.write_text(json.dumps(data))
    assert R.main(['r', d, str(ap), str(bp), str(Path(d) / 'x.json')]) == 3
    print("✓ test_unknown_case_id_rejected")


def test_missing_source_record_rejected():
    # Adjudicating an allowlist-ACCEPTED case (not a rejection) must fail.
    d, bp, ap = _scenario()
    data = json.loads(bp.read_text())
    data.append({"id": "a", "model": "base", "group": "fit", "semantic_verdict": "correct"})
    bp.write_text(json.dumps(data))
    assert R.main(['r', d, str(ap), str(bp), str(Path(d) / 'x.json')]) == 3
    print("✓ test_missing_source_record_rejected")


def test_mismatched_model_rejected():
    d, bp, ap = _scenario()
    data = json.loads(bp.read_text())
    data.append({"id": "d", "model": "adapter", "group": "fit", "semantic_verdict": "incorrect"})
    bp.write_text(json.dumps(data))
    assert R.main(['r', d, str(ap), str(bp), str(Path(d) / 'x.json')]) == 3
    print("✓ test_mismatched_model_rejected")


def test_mismatched_group_rejected():
    d, bp, ap = _scenario()
    data = json.loads(bp.read_text())
    data.append({"id": "b", "model": "base", "group": "operand", "semantic_verdict": "correct"})
    bp.write_text(json.dumps(data))
    assert R.main(['r', d, str(ap), str(bp), str(Path(d) / 'x.json')]) == 3
    print("✓ test_mismatched_group_rejected")


def test_contradictory_adjudication_rejected():
    d, bp, ap = _scenario()
    data = json.loads(bp.read_text())
    data.append({"id": "b", "model": "base", "group": "fit", "semantic_verdict": "incorrect"})
    bp.write_text(json.dumps(data))
    assert R.main(['r', d, str(ap), str(bp), str(Path(d) / 'x.json')]) == 3
    print("✓ test_contradictory_adjudication_rejected")


def test_malformed_verdict_rejected():
    d, bp, ap = _scenario()
    data = json.loads(bp.read_text())
    data.append({"id": "b", "model": "base", "group": "fit", "semantic_verdict": "MAYBE"})
    bp.write_text(json.dumps(data))
    assert R.main(['r', d, str(ap), str(bp), str(Path(d) / 'x.json')]) == 3
    print("✓ test_malformed_verdict_rejected")


def main():
    print("Running rescore regression tests...")
    test_three_state_and_paired_semantics()
    test_determinism()
    test_duplicate_adjudication_rejected()
    test_unknown_case_id_rejected()
    test_missing_source_record_rejected()
    test_mismatched_model_rejected()
    test_mismatched_group_rejected()
    test_contradictory_adjudication_rejected()
    test_malformed_verdict_rejected()
    print("\nAll rescore regression tests passed.")


if __name__ == '__main__':
    main()
