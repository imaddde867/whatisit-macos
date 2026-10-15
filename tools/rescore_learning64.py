#!/usr/bin/env python3
"""Rescore Learning64 results with three-state semantic adjudications.

Combines the original (immutable) evaluation results with manual semantic
adjudications to produce a corrected score that keeps three states per case:

- correct    : accepted by the original allowlist, OR adjudicated correct.
- incorrect  : adjudicated incorrect.
- unresolved : adjudicated unresolved, or a rejected case with no adjudication.

Pairwise base-vs-adapter comparisons are *conservative*: a change is only
counted as an improvement or regression when both sides are confirmed. Any pair
in which either side is unresolved is reported separately and never inflated
into a confirmed outcome. Everything is deterministic (fixed iteration order,
no timestamps in the machine output).

The adjudication inputs are validated strictly. The scorer aborts if it sees:
  - duplicate adjudications (same id twice),
  - unknown case ids (not present in the results),
  - missing source records (an id that is not a rejected case of that model),
  - mismatched model/group identifiers,
  - contradictory adjudications (same id, conflicting verdicts),
  - malformed verdicts (anything outside correct/incorrect/unresolved).
"""
import json
import sys
from collections import Counter
from pathlib import Path

VALID_VERDICTS = {'correct', 'incorrect', 'unresolved'}
GROUPS = ['fit', 'paraphrase', 'operand', 'composition']
MODELS = ['base', 'adapter']


class AdjudicationError(ValueError):
    """Raised when adjudication inputs are malformed or inconsistent."""


def load_results(results_dir):
    """Load results-{model}-{group}.jsonl into {(model, group): [case, ...]}."""
    out = {}
    for path in sorted(Path(results_dir).glob('results-*.jsonl')):
        parts = path.stem.split('-')
        if len(parts) != 3:
            continue
        _, model, group = parts
        if model not in MODELS or group not in GROUPS:
            continue
        records = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
        cases = [r for r in records if r.get('type') == 'case']
        out[(model, group)] = cases
    return out


def load_adjudications(path, model):
    """Load one adjudications file, validating structure. Returns {id: entry}."""
    if not Path(path).exists():
        return {}
    data = json.loads(Path(path).read_text())
    if not isinstance(data, list):
        raise AdjudicationError(f"{path}: expected a JSON list")
    by_id = {}
    for entry in data:
        if not isinstance(entry, dict) or 'id' not in entry:
            raise AdjudicationError(f"{path}: entry missing 'id'")
        cid = entry['id']
        verdict = entry.get('semantic_verdict')
        if verdict not in VALID_VERDICTS:
            raise AdjudicationError(f"{path}:{cid}: malformed verdict {verdict!r}")
        # The file must describe its own model, with a known group.
        entry_model = entry.get('model')
        entry_group = entry.get('group')
        if entry_model != model:
            raise AdjudicationError(
                f"{path}:{cid}: model {entry_model!r} != expected {model!r}")
        if entry_group not in GROUPS:
            raise AdjudicationError(f"{path}:{cid}: unknown group {entry_group!r}")
        if cid in by_id:
            # Duplicate or contradictory (different verdict for same id).
            if by_id[cid].get('semantic_verdict') != verdict or \
                    by_id[cid].get('group') != entry_group:
                raise AdjudicationError(
                    f"{path}:{cid}: contradictory duplicate adjudication")
            raise AdjudicationError(f"{path}:{cid}: duplicate adjudication")
        by_id[cid] = entry
    return by_id


def build_index(results):
    """Return lookup tables:
    - records[(model, group)][case_id] = record
    - rejected_ids[model] = set of case_ids that were rejected (accepted False)
    - id_group[(model, case_id)] = group
    """
    records, rejected, id_group = {}, {m: set() for m in MODELS}, {}
    for (model, group), cases in results.items():
        records.setdefault((model, group), {})
        for rec in cases:
            cid = rec['case']['id']
            records[(model, group)][cid] = rec
            id_group[(model, cid)] = group
            if not rec.get('accepted'):
                rejected[model].add(cid)
    return records, rejected, id_group


def validate_adjudications(adj, results, rejected, id_group, model):
    """Ensure every adjudication targets a real, rejected case of this model."""
    all_case_ids = {cid for (m, cid) in id_group if m == model}
    for cid, entry in adj.items():
        if cid not in all_case_ids:
            raise AdjudicationError(f"{model}: adjudication for unknown case {cid}")
        if cid not in rejected[model]:
            raise AdjudicationError(
                f"{model}: adjudication for {cid} which was NOT rejected "
                f"(allowlist-accepted cases must not be double-counted)")
        if id_group[(model, cid)] != entry['group']:
            raise AdjudicationError(
                f"{model}:{cid}: group {entry['group']!r} != source group "
                f"{id_group[(model, cid)]!r}")


def case_state(rec, adj):
    """Return the three-state classification for one case record."""
    if rec.get('accepted'):
        return 'correct'  # original allowlist acceptance
    cid = rec['case']['id']
    entry = adj.get(cid)
    if entry is None:
        return 'unresolved'  # rejected but not adjudicated
    return entry['semantic_verdict']


def summarize_group(model, group, records, adj):
    states = {}
    for cid in sorted(records):
        states[cid] = case_state(records[cid], adj)
    counts = Counter(states.values())
    total = len(states)
    correct = counts['correct']
    incorrect = counts['incorrect']
    unresolved = counts['unresolved']
    allowlist = sum(1 for cid in records if records[cid].get('accepted'))
    return {
        'group': group, 'model': model, 'total': total,
        'allowlist_accepted': allowlist,
        'adjudicated_correct': correct - allowlist,
        'confirmed_correct': correct,
        'confirmed_incorrect': incorrect,
        'unresolved': unresolved,
        'correct_lower_bound': correct,
        'correct_upper_bound': correct + unresolved,
        'states': states,
    }


def compare_group(base_sum, adapter_sum):
    """Conservative paired comparison. Unresolved pairs are never counted."""
    base_states, adapter_states = base_sum['states'], adapter_sum['states']
    ids = sorted(set(base_states) | set(adapter_states))
    improvements, regressions, unresolved_pairs = [], [], []
    both_correct = both_incorrect = 0
    for cid in ids:
        b = base_states.get(cid)
        a = adapter_states.get(cid)
        if b is None or a is None:
            unresolved_pairs.append({'case_id': cid, 'detail': 'missing side'})
            continue
        if b == 'unresolved' or a == 'unresolved':
            unresolved_pairs.append({'case_id': cid, 'base': b, 'adapter': a})
            continue
        if b == 'incorrect' and a == 'correct':
            improvements.append(cid)
        elif b == 'correct' and a == 'incorrect':
            regressions.append(cid)
        elif b == 'correct' and a == 'correct':
            both_correct += 1
        else:
            both_incorrect += 1
    return {
        'group': base_sum['group'],
        'paired_cases': len(ids),
        'improvements': len(improvements), 'improvement_cases': improvements,
        'regressions': len(regressions), 'regression_cases': regressions,
        'both_correct': both_correct, 'both_incorrect': both_incorrect,
        'unresolved_pairs': len(unresolved_pairs),
        'unresolved_pair_detail': unresolved_pairs,
    }


def main(argv):
    results_dir = Path(argv[1]) if len(argv) > 1 else Path('docs/learning64/results')
    adapter_adj_file = Path(argv[2]) if len(argv) > 2 else Path('docs/learning64/semantic-adjudications.json')
    base_adj_file = Path(argv[3]) if len(argv) > 3 else Path('docs/learning64/base-adjudications.json')
    out_path = Path(argv[4]) if len(argv) > 4 else Path('docs/learning64/rescored-detailed.json')

    results = load_results(results_dir)
    records, rejected, id_group = build_index(results)

    try:
        base_adj = load_adjudications(base_adj_file, 'base')
        validate_adjudications(base_adj, results, rejected, id_group, 'base')
        adapter_adj = load_adjudications(adapter_adj_file, 'adapter')
        validate_adjudications(adapter_adj, results, rejected, id_group, 'adapter')
    except AdjudicationError as e:
        print(f"ERROR: invalid adjudications: {e}", file=sys.stderr)
        return 3

    model_adjs = {'base': base_adj, 'adapter': adapter_adj}

    # Per-group summaries.
    group_summaries = {}
    for group in GROUPS:
        for model in MODELS:
            recs = results.get((model, group), {})
            rec_map = {r['case']['id']: r for r in recs}
            if rec_map:
                group_summaries[f'{model}-{group}'] = summarize_group(
                    model, group, rec_map, model_adjs[model])

    # Pairwise comparisons.
    comparisons = {}
    for group in GROUPS:
        b = group_summaries.get(f'base-{group}')
        a = group_summaries.get(f'adapter-{group}')
        if b and a:
            comparisons[group] = compare_group(b, a)

    # Overall per-model totals.
    totals = {}
    for model in MODELS:
        agg = Counter()
        allow = 0
        total = 0
        for group in GROUPS:
            s = group_summaries.get(f'{model}-{group}')
            if s:
                agg['confirmed_correct'] += s['confirmed_correct']
                agg['confirmed_incorrect'] += s['confirmed_incorrect']
                agg['unresolved'] += s['unresolved']
                allow += s['allowlist_accepted']
                total += s['total']
        totals[model] = {
            'total': total, 'allowlist_accepted': allow,
            'confirmed_correct': agg['confirmed_correct'],
            'confirmed_incorrect': agg['confirmed_incorrect'],
            'unresolved': agg['unresolved'],
            'correct_lower_bound': agg['confirmed_correct'],
            'correct_upper_bound': agg['confirmed_correct'] + agg['unresolved'],
        }

    # Totals for paired changes.
    total_improvements = sum(c['improvements'] for c in comparisons.values())
    total_regressions = sum(c['regressions'] for c in comparisons.values())
    total_unresolved_pairs = sum(c['unresolved_pairs'] for c in comparisons.values())

    output = {
        'notes': (
            'Three-state scoring. correct = allowlist-accepted or adjudicated '
            'correct; incorrect = adjudicated incorrect; unresolved = adjudicated '
            'unresolved or rejected-without-adjudication. Paired changes count '
            'only confirmed sides; any unresolved side is reported separately.'),
        'totals': totals,
        'paired_totals': {
            'improvements': total_improvements,
            'regressions': total_regressions,
            'unresolved_pairs': total_unresolved_pairs,
        },
        'group_summaries': {k: {kk: vv for kk, vv in v.items() if kk != 'states'}
                            for k, v in group_summaries.items()},
        'comparisons': comparisons,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2, sort_keys=True) + '\n')

    # Human-readable report.
    print("=" * 70)
    print("CORRECTED Learning64 SCORING (three-state)")
    print("=" * 70)
    for model in MODELS:
        t = totals[model]
        print(f"\n{model.upper()} overall: {t['confirmed_correct']}/{t['total']} confirmed correct "
              f"(range {t['correct_lower_bound']}-{t['correct_upper_bound']}), "
              f"incorrect {t['confirmed_incorrect']}, unresolved {t['unresolved']}, "
              f"allowlist {t['allowlist_accepted']}")
        for group in GROUPS:
            s = group_summaries.get(f'{model}-{group}')
            if not s:
                continue
            print(f"  {group:11}: correct={s['confirmed_correct']:3}/{s['total']:<3} "
                  f"(allowlist {s['allowlist_accepted']}, +adjud {s['adjudicated_correct']}) "
                  f"incorrect={s['confirmed_incorrect']}, unresolved={s['unresolved']}, "
                  f"range [{s['correct_lower_bound']},{s['correct_upper_bound']}]")
    print("\nPaired comparisons (confirmed only):")
    for group in GROUPS:
        c = comparisons.get(group)
        if not c:
            continue
        print(f"  {group:11}: +{c['improvements']} improve, -{c['regressions']} regress, "
              f"{c['unresolved_pairs']} unresolved pairs, "
              f"improve={','.join(c['improvement_cases']) or '-'} "
              f"regress={','.join(c['regression_cases']) or '-'}")
    print(f"\nTotals: improvements={total_improvements} regressions={total_regressions} "
          f"unresolved_pairs={total_unresolved_pairs}")
    print(f"Detailed results saved to {out_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
