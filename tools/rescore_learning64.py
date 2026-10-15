#!/usr/bin/env python3
"""Rescore Learning64 results with semantic adjudications.

Combines original evaluation results with manual semantic adjudications
to produce corrected scores that distinguish between:
- Exact/allowlist acceptance
- Confirmed semantic correctness
- Confirmed semantic failures
- Unresolved cases
"""
import json
import sys
from collections import Counter
from pathlib import Path


def load_results(results_dir):
    """Load all saved result files."""
    results = {}
    for result_file in Path(results_dir).glob('results-*.jsonl'):
        model = result_file.stem.split('-')[1]
        group = result_file.stem.split('-')[2]
        key = f"{model}-{group}"
        records = []
        for line in result_file.read_text().splitlines():
            if line.strip():
                record = json.loads(line)
                records.append(record)
        results[key] = records
    return results


def load_adjudications(adjudications_file):
    """Load semantic adjudications."""
    if not Path(adjudications_file).exists():
        return {}
    data = json.loads(Path(adjudications_file).read_text())
    # Index by id for easy lookup
    return {item['id']: item for item in data}


def rescore_record(record, adjudications):
    """Apply semantic adjudication to a single record."""
    case_id = record['case']['id']
    adjudication = adjudications.get(case_id)

    result = {
        'case_id': case_id,
        'original_accepted': record.get('accepted', False),
        'original_verdict': record.get('verdict', 'needs_review'),
        'semantic_verdict': adjudication.get('semantic_verdict') if adjudication else None,
        'semantic_justification': adjudication.get('justification') if adjudication else None,
    }

    # Determine final semantic status
    if record.get('accepted'):
        result['final_semantic_status'] = 'accepted_by_allowlist'
    elif adjudication:
        if adjudication.get('semantic_verdict') == 'correct':
            result['final_semantic_status'] = 'semantically_correct'
        elif adjudication.get('semantic_verdict') == 'incorrect':
            result['final_semantic_status'] = 'semantically_incorrect'
        else:
            result['final_semantic_status'] = 'unresolved'
    else:
        result['final_semantic_status'] = 'unresolved'

    return result


def summarize_group(records, group_name):
    """Summarize scoring for a group."""
    counts = Counter(r['final_semantic_status'] for r in records)

    # Calculate metrics
    total = len(records)
    allowlist_accepted = counts['accepted_by_allowlist']
    semantically_correct = counts['semantically_correct']
    confirmed_correct = allowlist_accepted + semantically_correct
    semantically_incorrect = counts['semantically_incorrect']
    unresolved = counts['unresolved']

    return {
        'group': group_name,
        'total': total,
        'allowlist_accepted': allowlist_accepted,
        'semantically_correct': semantically_correct,
        'confirmed_correct': confirmed_correct,
        'semantically_incorrect': semantically_incorrect,
        'unresolved': unresolved,
        'correct_lower_bound': confirmed_correct,
        'correct_upper_bound': confirmed_correct + unresolved,
    }


def compare_models(base_records, adapter_records, group_name):
    """Compare base vs adapter performance."""
    # Create lookup by case ID
    base_by_id = {r['case_id']: r for r in base_records}
    adapter_by_id = {r['case_id']: r for r in adapter_records}

    paired = []
    for case_id in set(base_by_id.keys()) | set(adapter_by_id.keys()):
        base = base_by_id.get(case_id)
        adapter = adapter_by_id.get(case_id)

        if base and adapter:
            # Determine status
            base_correct = base['final_semantic_status'] in ['accepted_by_allowlist', 'semantically_correct']
            adapter_correct = adapter['final_semantic_status'] in ['accepted_by_allowlist', 'semantically_correct']

            if base_correct and not adapter_correct:
                paired.append({'case_id': case_id, 'type': 'regression'})
            elif not base_correct and adapter_correct:
                paired.append({'case_id': case_id, 'type': 'improvement'})
            elif base_correct and adapter_correct:
                paired.append({'case_id': case_id, 'type': 'both_correct'})
            else:
                paired.append({'case_id': case_id, 'type': 'both_incorrect_or_unresolved'})

    improvements = [p for p in paired if p['type'] == 'improvement']
    regressions = [p for p in paired if p['type'] == 'regression']

    return {
        'group': group_name,
        'paired_cases': len(paired),
        'improvements': len(improvements),
        'regressions': len(regressions),
        'improvement_cases': [p['case_id'] for p in improvements],
        'regression_cases': [p['case_id'] for p in regressions],
    }


def main():
    if len(sys.argv) > 1:
        results_dir = Path(sys.argv[1])
    else:
        results_dir = Path('docs/learning64/results')

    if len(sys.argv) > 2:
        adapter_adjudications_file = Path(sys.argv[2])
    else:
        adapter_adjudications_file = Path('docs/learning64/semantic-adjudications.json')

    if len(sys.argv) > 3:
        base_adjudications_file = Path(sys.argv[3])
    else:
        base_adjudications_file = Path('docs/learning64/base-adjudications.json')

    print(f"Loading results from {results_dir}...")
    results = load_results(results_dir)

    print(f"Loading adapter adjudications from {adapter_adjudications_file}...")
    adapter_adjudications = load_adjudications(adapter_adjudications_file)

    print(f"Loading base adjudications from {base_adjudications_file}...")
    base_adjudications = load_adjudications(base_adjudications_file)

    # Rescore all records
    all_rescored = {}
    for key, records in results.items():
        model, group = key.split('-')
        adjudications = adapter_adjudications if model == 'adapter' else base_adjudications
        rescored = [rescore_record(r, adjudications) for r in records if r.get('type') == 'case']
        all_rescored[key] = rescored

    # Summarize by group
    summaries = {}
    for group in ['fit', 'paraphrase', 'operand', 'composition']:
        base_key = f'base-{group}'
        adapter_key = f'adapter-{group}'

        if base_key in all_rescored:
            summaries[f'base-{group}'] = summarize_group(all_rescored[base_key], f'base-{group}')
        if adapter_key in all_rescored:
            summaries[f'adapter-{group}'] = summarize_group(all_rescored[adapter_key], f'adapter-{group}')

        # Compare models
        if base_key in all_rescored and adapter_key in all_rescored:
            summaries[f'comparison-{group}'] = compare_models(
                all_rescored[base_key], all_rescored[adapter_key], group)

    # Print report
    print("\n" + "="*70)
    print("CORRECTED SCORING REPORT")
    print("="*70)

    for group in ['fit', 'paraphrase', 'operand', 'composition']:
        print(f"\n{group.upper()}:")
        print(f"  Base:")
        if f'base-{group}' in summaries:
            s = summaries[f'base-{group}']
            print(f"    Allowlist accepted: {s['allowlist_accepted']}/{s['total']}")
            print(f"    Semantically correct (adjudicated): {s['semantically_correct']}")
            print(f"    Confirmed correct (lower bound): {s['confirmed_correct']}/{s['total']}")
            print(f"    Semantically incorrect: {s['semantically_incorrect']}")
            print(f"    Unresolved: {s['unresolved']}")
            print(f"    Correct range: [{s['correct_lower_bound']}, {s['correct_upper_bound']}]")

        print(f"  Adapter:")
        if f'adapter-{group}' in summaries:
            s = summaries[f'adapter-{group}']
            print(f"    Allowlist accepted: {s['allowlist_accepted']}/{s['total']}")
            print(f"    Semantically correct (adjudicated): {s['semantically_correct']}")
            print(f"    Confirmed correct (lower bound): {s['confirmed_correct']}/{s['total']}")
            print(f"    Semantically incorrect: {s['semantically_incorrect']}")
            print(f"    Unresolved: {s['unresolved']}")
            print(f"    Correct range: [{s['correct_lower_bound']}, {s['correct_upper_bound']}]")

        if f'comparison-{group}' in summaries:
            c = summaries[f'comparison-{group}']
            print(f"  Paired comparison:")
            print(f"    Improvements: {c['improvements']} ({', '.join(c['improvement_cases'])})")
            print(f"    Regressions: {c['regressions']} ({', '.join(c['regression_cases'])})")

    # Save detailed results
    out_path = Path('docs/learning64/rescored-detailed.json')
    output = {
        'summaries': summaries,
        'all_rescored': all_rescored,
    }
    out_path.write_text(json.dumps(output, indent=2) + '\n')
    print(f"\nDetailed results saved to {out_path}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
