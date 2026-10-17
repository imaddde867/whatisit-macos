#!/usr/bin/env python3
"""Audit semantic correctness of previously rejected model outputs.

This script reads saved evaluation results and helps adjudicate whether
rejected commands are actually semantically correct.
"""
import json
import sys
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


def extract_needs_review(results):
    """Extract all cases marked as needs_review."""
    review_cases = []
    for key, records in results.items():
        model, group = key.split('-')
        for record in records:
            if record.get('type') == 'case' and record.get('verdict') == 'needs_review':
                review_cases.append({
                    'key': key,
                    'model': model,
                    'group': group,
                    'id': record['case']['id'],
                    'request': record['case']['request'],
                    'reference': record['case']['reference'],
                    'semantic_criterion': record['case'].get('semantic_criterion', ''),
                    'generated': record.get('extracted_command'),
                    'generation': record.get('generation'),
                    'finish_reason': record.get('finish_reason'),
                })
    return review_cases


def adjudicate_case(case):
    """Interactive adjudication of a single case."""
    print(f"\n{'='*70}")
    print(f"ID: {case['id']} ({case['model']} {case['group']})")
    print(f"Request: {case['request']}")
    print(f"Reference: {case['reference']}")
    print(f"Semantic criterion: {case['semantic_criterion']}")
    print(f"Generated: {case['generated']}")
    print(f"Generation: {case['generation']}")
    print(f"Finish reason: {case['finish_reason']}")
    print(f"{'='*70}")

    while True:
        print("\nAdjudication options:")
        print("  1. correct - Generated command is semantically correct")
        print("  2. incorrect - Generated command is semantically incorrect")
        print("  3. unresolved - Cannot determine without execution")
        print("  4. skip - Skip this case for now")
        choice = input("Your verdict [1/2/3/4]: ").strip()

        if choice == '1':
            verdict = 'correct'
            justification = input("Justification: ").strip()
            return verdict, justification
        elif choice == '2':
            verdict = 'incorrect'
            justification = input("Justification: ").strip()
            return verdict, justification
        elif choice == '3':
            verdict = 'unresolved'
            justification = input("Justification: ").strip()
            return verdict, justification
        elif choice == '4':
            return None, None
        else:
            print("Invalid choice, try again")


def main():
    if len(sys.argv) > 1:
        results_dir = Path(sys.argv[1])
    else:
        results_dir = Path('docs/learning64/results')

    print(f"Loading results from {results_dir}...")
    results = load_results(results_dir)

    print(f"\nExtracting needs_review cases...")
    review_cases = extract_needs_review(results)
    print(f"Found {len(review_cases)} cases marked as needs_review")

    adjudications = []
    for case in review_cases:
        verdict, justification = adjudicate_case(case)
        if verdict:
            adjudications.append({
                **case,
                'original_verdict': 'needs_review',
                'semantic_verdict': verdict,
                'justification': justification
            })

    # Save adjudications
    out_path = Path('docs/learning64/semantic-adjudications.json')
    if adjudications:
        out_path.write_text(json.dumps(adjudications, indent=2) + '\n')
        print(f"\nSaved {len(adjudications)} adjudications to {out_path}")
    else:
        print("\nNo adjudications saved")


if __name__ == '__main__':
    main()
