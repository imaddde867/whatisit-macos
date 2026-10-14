#!/usr/bin/env python3
"""Reproduce the registered runtime-LoRA statistics from recorded dev/everyday details."""
import json
from math import comb
from pathlib import Path
import random
import statistics

CORRECT = {'pass', 'abstain-ok'}


def mcnemar(candidate, baseline):
    if len(candidate) != len(baseline):
        raise ValueError('paired vectors must have equal length')
    wins = sum(a and not b for a, b in zip(candidate, baseline))
    losses = sum(b and not a for a, b in zip(candidate, baseline))
    n = wins + losses
    p = min(1.0, 2 * sum(comb(n, j) for j in range(min(wins, losses) + 1)) / 2**n)
    return {'wins': wins, 'losses': losses, 'p': p}


def bootstrap(case_deltas):
    if not case_deltas:
        raise ValueError('bootstrap needs cases')
    rng = random.Random(20261014)
    draws = sorted(sum(rng.choices(case_deltas, k=len(case_deltas))) for _ in range(10000))
    return [draws[249], draws[9749]]


def summarize(seeds, cases, baseline):
    ids = sorted(cases)
    if len(seeds) != 8 or any(set(s) != set(ids) for s in seeds) or len(baseline) != len(ids):
        raise ValueError('need eight seeds and identical paired case IDs')
    correct = [[s[i]['label'] in CORRECT for i in ids] for s in seeds]
    scores = [sum(s) for s in correct]
    counts = [sum(s[j] for s in correct) for j in range(len(ids))]
    majority = [n >= 5 for n in counts]
    per_seed = []
    for seed, vector in zip(seeds, correct):
        per_seed.append({
            'pooled': sum(vector),
            'dev': sum(ok for i, ok in zip(ids, vector) if cases[i]['split'] == 'dev'),
            'everyday': sum(ok for i, ok in zip(ids, vector) if cases[i]['split'] == 'everyday'),
            'accepted_wrong': sum(d['label'] == 'wrong' for d in seed.values()),
            'abstain_missed': sum(d['label'] == 'abstain-missed' for d in seed.values()),
            'empty_on_answerable': sum(cases[i]['accept'] is not None and seed[i]['no_command_kind'] == 'empty_output' for i in ids),
            'lint_rejected_on_answerable': sum(cases[i]['accept'] is not None and seed[i]['no_command_kind'] == 'lint' for i in ids)})
    unstable = sorted((i for i, n in zip(ids, counts) if 0 < n < 8),
                      key=lambda i: (abs(counts[ids.index(i)] - 4), i))[:10]
    return {'seed_scores': scores, 'mean': statistics.mean(scores), 'sd': statistics.stdev(scores),
            'min': min(scores), 'max': max(scores), 'per_seed': per_seed,
            'majority': majority, 'majority_score': sum(majority),
            'mcnemar': mcnemar(majority, baseline),
            **{f'mean_{key}': statistics.mean(s[key] for s in per_seed)
               for key in ('accepted_wrong', 'abstain_missed', 'empty_on_answerable', 'lint_rejected_on_answerable')},
            'agreement': {'all_eight': counts.count(8), 'none': counts.count(0),
                          'mixed': sum(0 < n < 8 for n in counts)},
            'case_correct_counts': dict(zip(ids, counts)),
            'unstable': [{'id': i, 'correct_seeds': counts[ids.index(i)],
                          'commands': [s[i]['command'] for s in seeds],
                          'labels': [s[i]['label'] for s in seeds]} for i in unstable]}


def rules(a, b, default_correct, default_wrong):
    return {'R1': a['mean'] >= default_correct + 8 and a['mcnemar']['p'] < .05
                   and a['mean_accepted_wrong'] <= default_wrong + 2,
            'R2': b['sd'] <= a['sd'] / 2 and b['mean_empty_on_answerable'] <= 5
                   and b['mean'] >= a['mean'] - 2,
            'R3': a['mean'] - default_correct < 5 and a['mcnemar']['p'] > .2}


def budget(candidate, default):
    latency = {split: round(float(candidate['eval'][split].split('p50 ')[1][:-1]) -
                            float(default['eval'][split].split('p50 ')[1][:-1]), 2)
               for split in ('dev', 'everyday')}
    delta = candidate['sampled_mean_rss_bytes'] - default['sampled_mean_rss_bytes']
    return {'mean_rss_delta_bytes': delta,
            'peak_rss_delta_bytes': candidate['sampled_peak_rss_bytes'] - default['sampled_peak_rss_bytes'],
            'p50_delta_seconds': latency,
            'fails': delta > 64 * 1024**2 or any(d > .05 for d in latency.values())}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    artifacts = root / 'docs/runtime-lora-8seed'
    cases = {}
    for split in ('dev', 'everyday'):
        for line in (root / 'eval' / f'{split}.jsonl').read_text().splitlines():
            row = json.loads(line)
            assert row['id'] not in cases
            cases[row['id']] = dict(row, split=split)
    ids = sorted(cases)
    assert len(ids) == 141
    default = {}
    for split in ('dev', 'everyday'):
        labels = json.loads((artifacts / f'default-{split}.json').read_text())
        assert labels == json.loads((root / 'docs/stage2-arm-labels.json').read_text())['arms']['default'][split]
        default.update(labels)
    baseline = [default[i] in CORRECT for i in ids]
    summaries = {}
    for arm in ('A', 'B'):
        seeds = []
        for seed in range(1, 9):
            details = {}
            for split in ('dev', 'everyday'):
                labels = json.loads((artifacts / f'{arm}-s{seed}-{split}.json').read_text())
                part = json.loads((artifacts / f'{arm}-s{seed}-{split}-detail.json').read_text())
                assert {i: d['label'] for i, d in part.items()} == labels
                assert all(d['label'] in ('pass', 'wrong', 'rejected', 'abstain-ok', 'abstain-missed') for d in part.values())
                details.update(part)
            seeds.append(details)
        summaries[arm] = summarize(seeds, cases, baseline)
        for row in summaries[arm]['unstable']:
            row['request'] = cases[row['id']]['request']
    a, b = summaries['A'], summaries['B']
    result = {'default_correct': sum(baseline), 'default_accepted_wrong': list(default.values()).count('wrong'),
              'arms': summaries, 'A_vs_B_majority': mcnemar(a['majority'], b['majority']),
              'A_minus_default_bootstrap_95ci': bootstrap([
                  a['case_correct_counts'][i] / 8 - baseline[j] for j, i in enumerate(ids)]),
              'bootstrap_resamples': 10000, 'bootstrap_seed': 20261014,
              'rules': rules(a, b, sum(baseline), list(default.values()).count('wrong'))}
    runtimes = {name: json.loads((artifacts / 'reports' / f'{name}-runtime.json').read_text())
                for name in ('default', 'A-s1', 'B-s1')}
    result['memory_latency'] = runtimes
    result['R4'] = {arm: budget(runtimes[f'{arm}-s1'], runtimes['default']) for arm in ('A', 'B')}
    (artifacts / 'analysis.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('arms', 'memory_latency')}, indent=2))
