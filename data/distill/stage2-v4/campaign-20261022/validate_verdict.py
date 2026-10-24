#!/usr/bin/env python3
"""Validate one pass-1 verdict file against its blind batch and the control map.

Campaign-local gate used by the director before a batch is accepted. It is deliberately
stricter than the builder's later checks: every schema field, key, case and control is
checked here so a malformed batch never reaches the final build.

Usage:
    validate_verdict.py <batch.json> <verdict.json> <controls-map.json>
"""
import json
import sys
from collections import Counter
from pathlib import Path

VERDICTS = {'correct', 'incorrect', 'unsure'}
CATEGORIES = {'linux_syntax', 'hallucinated_flag', 'wrong_tool', 'missed_constraint',
              'wrong_operand', 'wrong_output', 'unsafe', 'should_abstain',
              'not_a_command', 'other'}


def load(path):
    return json.loads(Path(path).read_text())


def fail(message):
    raise SystemExit(f'FAIL: {message}')


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__.strip().splitlines()[-1])
    batch_path, verdict_path, controls_path = map(Path, sys.argv[1:])
    batch = load(batch_path)
    verdict = load(verdict_path)
    controls = load(controls_path)

    if batch.get('batch') != batch_path.stem:
        fail(f'batch field {batch.get("batch")!r} does not match {batch_path.stem}')
    if set(verdict) != {'batch', 'judge', 'cases'}:
        fail('verdict must contain exactly batch, judge, cases')
    if verdict['batch'] != batch['batch']:
        fail('verdict batch does not match input batch')
    if not isinstance(verdict['judge'], str) or not verdict['judge'].strip():
        fail('judge identity must be a non-empty string')
    if not isinstance(verdict['cases'], list):
        fail('cases must be a list')

    batch_cases = {item['case']: item for item in batch['items']}
    batch_keys = {candidate['key'] for item in batch['items'] for candidate in item['candidates']}
    seen_cases, seen_keys = set(), set()
    counts = Counter()
    mismatched_controls = []
    for case in verdict['cases']:
        if not isinstance(case, dict) or set(case) != {'case', 'verdicts'}:
            fail('each case must contain exactly case, verdicts')
        if case['case'] not in batch_cases:
            fail(f'unknown case {case["case"]!r}')
        if case['case'] in seen_cases:
            fail(f'duplicate case {case["case"]!r}')
        seen_cases.add(case['case'])
        expected_keys = {c['key'] for c in batch_cases[case['case']]['candidates']}
        got_keys = set()
        for entry in case['verdicts']:
            if not isinstance(entry, dict) or set(entry) != {'key', 'verdict', 'category', 'evidence'}:
                fail('each verdict must contain exactly key, verdict, category, evidence')
            key, value = entry['key'], entry['verdict']
            if key not in batch_keys:
                fail(f'unknown key {key!r}')
            if key in seen_keys:
                fail(f'duplicate key {key!r}')
            seen_keys.add(key)
            got_keys.add(key)
            if value not in VERDICTS:
                fail(f'{key}: bad verdict {value!r}')
            if value == 'incorrect':
                if entry['category'] not in CATEGORIES:
                    fail(f'{key}: incorrect needs a rubric category, got {entry["category"]!r}')
            elif entry['category'] is not None:
                fail(f'{key}: category must be null for {value}')
            if not isinstance(entry['evidence'], str) or not entry['evidence'].strip():
                fail(f'{key}: evidence must be non-empty')
            counts[value] += 1
            if key in controls and value != controls[key]['expected']:
                mismatched_controls.append({'key': key, 'expected': controls[key]['expected'],
                                            'observed': value})
        if got_keys != expected_keys:
            fail(f'case {case["case"]}: key coverage mismatch')
    if seen_cases != set(batch_cases):
        fail('case coverage mismatch')
    if seen_keys != batch_keys:
        fail('key coverage mismatch')
    if mismatched_controls:
        fail(f'control mismatch: {mismatched_controls}')

    injected = [key for key in batch_keys if key in controls]
    print(json.dumps({'batch': batch['batch'], 'judge': verdict['judge'],
                      'cases': len(seen_cases), 'keys': len(seen_keys),
                      'verdicts': dict(counts), 'controls': len(injected),
                      'controls_matched': len(injected), 'pass': True}, sort_keys=True))


if __name__ == '__main__':
    main()
