"""Score teacher samples on dev + everyday with the serving harness's own checks.

    PYTHONPATH=src PATH=/usr/bin:/bin:/usr/sbin:/sbin \
        ~/.local/pipx/venvs/whatisit/bin/python tools/score_teacher_eval.py \
        --samples data/teacher/eval-ceiling/raw_samples.jsonl

Applies to every parsed sample exactly the checks local_recovery_worker.suggest()
runs after generation, in the same order: reject commands longer than 4,096
characters or containing NUL/CR/LF, reject on safety.check DANGER, reject on
maclint.problems + unrequested_deletion + the safety.PLACEHOLDER_HINT rule as
written there; otherwise accept. Labels follow tools/eval_fallback.py:
pass / wrong / rejected / abstain-ok / abstain-missed (accept regex or list,
any match; null accept = the right outcome is no command). A null command,
unparsed output or a non-`stop` finish counts as no command.

Reports, per split and pooled (correct = pass + abstain-ok):
(a) majority label -- the command at least 3 of 5 valid stop samples agree on
    (exact string after strip(), before any linting; >= 3 nulls is an abstention,
    otherwise no command), mirroring how training labels were chosen;
(b) mean per-sample correctness -- the expected score of one teacher sample;
(c) best-of-5 oracle -- an upper bound only.

--references runs the sanity check: every answerable case's reference and
also_correct commands through the same lint and accept patterns.
"""

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

from whatisit import safety
from whatisit_macos import maclint

SPLITS = ('dev', 'everyday')
VALID_STOP = ('stop',)


def valid_stop(sample: dict) -> bool:
    return bool(sample.get('parsed')) and sample.get('finish_reason') in VALID_STOP


def lint_reject(command: str, request: str) -> bool:
    """True when suggest() would return unsupported for this generated command."""
    if len(command) > 4096 or any(char in command for char in '\x00\r\n'):
        return True
    if any(severity == 'DANGER' for severity, _ in safety.check(command)):
        return True
    issues = maclint.problems(command) + maclint.unrequested_deletion(command, request)
    # PLACEHOLDER_HINT only: upstream's <...> pattern also matches redirections
    # like `sort <a >b`, so the worker re-checks the match against the request.
    issues += [f'{match.group(0)!r} is a placeholder, not something you named'
               for match in safety.PLACEHOLDER_HINT.finditer(command)
               if match.group(0).casefold() not in request.casefold()]
    return bool(issues)


def effective_command(sample: dict, request: str) -> str | None:
    """The command this sample contributes, or None (no command)."""
    if not valid_stop(sample):
        return None
    command = sample.get('command')
    if not command or lint_reject(command, request):
        return None
    return command


def label_case(case: dict, command: str | None) -> str:
    """Label one command against a case, exactly as tools/eval_fallback.py does."""
    if case['accept'] is None:
        return 'abstain-missed' if command else 'abstain-ok'
    if command is None:
        return 'rejected'
    patterns = [case['accept']] if isinstance(case['accept'], str) else case['accept']
    return 'pass' if any(re.search(p, command) for p in patterns) else 'wrong'


def majority(samples: list[dict]) -> tuple[str | None, str]:
    """(command, mode): the >= 3-of-5 valid-stop vote. mode: command|abstention|none."""
    votes = [sample.get('command') for sample in samples if valid_stop(sample)]
    counts = Counter(votes)
    if not counts:
        return None, 'none'
    top, top_count = counts.most_common(1)[0]
    if top is not None and top_count >= 3:
        return top, 'command'
    if counts.get(None, 0) >= 3:
        return None, 'abstention'
    return None, 'none'


def score_case(case: dict, samples: list[dict]) -> dict:
    request = case['request']
    majority_command, mode = majority(samples)
    if mode == 'command':
        rejected_by_lint = lint_reject(majority_command, request)
        effective = None if rejected_by_lint else majority_command
        rejection_cause = 'lint/safety rejected' if rejected_by_lint else None
    else:
        effective = None
        rejection_cause = None if mode == 'abstention' else 'no command'
    majority_label = label_case(case, effective)
    sample_labels = [label_case(case, effective_command(sample, request))
                     for sample in samples]
    correct = lambda label: label in ('pass', 'abstain-ok')  # noqa: E731
    return {
        'majority': majority_label,
        'majority_command': majority_command,
        'majority_mode': mode,
        'rejection_cause': rejection_cause if majority_label == 'rejected' else None,
        'sample_labels': sample_labels,
        'sample_correct': sum(correct(label) for label in sample_labels),
        'oracle': any(correct(label) for label in sample_labels),
    }


def summarize(entries: list[dict]) -> dict:
    labels = Counter(entry['majority'] for entry in entries)
    rejected = labels['rejected']
    causes = Counter(entry['rejection_cause'] for entry in entries
                     if entry['majority'] == 'rejected')
    return {
        'total': len(entries),
        'labels': dict(labels),
        'correct': labels['pass'] + labels['abstain-ok'],
        'accepted_wrong': labels['wrong'],
        'rejected': rejected,
        'rejected_no_command': causes.get('no command', 0),
        'rejected_lint_safety': causes.get('lint/safety rejected', 0),
        'abstain_missed': labels['abstain-missed'],
        'mean_per_sample_correctness': (statistics.mean(
            entry['sample_correct'] / len(entry['sample_labels']) for entry in entries)
            if entries else 0.0),
        'best_of_5': sum(entry['oracle'] for entry in entries),
        'coverage': sum(entry['majority_mode'] != 'none' for entry in entries),
    }


def reference_sanity(cases: dict) -> list[dict]:
    """Every answerable case's reference and also_correct, through lint + accept."""
    failures = []
    for case in cases.values():
        if case['accept'] is None:
            continue
        for command in [case['reference'], *(case.get('also_correct') or [])]:
            if not command:
                continue
            if lint_reject(command, case['request']):
                failures.append({'id': case['id'], 'kind': 'lint rejects',
                                 'command': command})
            elif label_case(case, command) != 'pass':
                failures.append({'id': case['id'], 'kind': 'accept misses',
                                 'command': command})
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--samples', type=Path, required=True,
                        help='raw_samples.jsonl from tools/teacher_sample.py')
    parser.add_argument('--eval-dir', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'eval')
    parser.add_argument('--out', type=Path, default=None,
                        help='write the full per-case JSON report here')
    parser.add_argument('--references', action='store_true',
                        help='sanity-check reference and also_correct commands')
    args = parser.parse_args()

    cases = {}
    for split in SPLITS:
        for line in (args.eval_dir / f'{split}.jsonl').read_text().splitlines():
            if line.strip():
                case = json.loads(line)
                cases[case['id']] = (split, case)

    entries = {'dev': {}, 'everyday': {}}
    for line in args.samples.read_text().splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        split, case = cases[record['id']]
        entries[split][record['id']] = score_case(case, record['samples'])

    report = {'per_split': {}, 'per_case': {}}
    pooled = []
    for split in SPLITS:
        split_entries = list(entries[split].values())
        report['per_split'][split] = summarize(split_entries)
        report['per_case'].update({case_id: {'split': split, **result}
                                   for case_id, result in entries[split].items()})
        pooled += split_entries
    report['pooled'] = summarize(pooled)

    if args.references:
        report['reference_sanity_failures'] = reference_sanity(
            {case_id: case for case_id, (_, case) in cases.items()})

    for scope in (*SPLITS, 'pooled'):
        summary = report['per_split'][scope] if scope != 'pooled' else report['pooled']
        print(f"{scope}: correct {summary['correct']}/{summary['total']}"
              f"  pass {summary['labels'].get('pass', 0)}"
              f"  abstain-ok {summary['labels'].get('abstain-ok', 0)}"
              f"  wrong {summary['accepted_wrong']}"
              f"  rejected {summary['rejected']}"
              f" (no command {summary['rejected_no_command']},"
              f" lint/safety {summary['rejected_lint_safety']})"
              f"  abstain-missed {summary['abstain_missed']}"
              f"  coverage {summary['coverage']}/{summary['total']}")
        print(f"    (a) majority {summary['correct']}/{summary['total']}"
              f"   (b) mean per-sample {summary['mean_per_sample_correctness']:.4f}"
              f"   (c) best-of-5 {summary['best_of_5']}/{summary['total']}")

    if args.out:
        args.out.write_text(json.dumps(report, indent=2) + '\n')
        print(f'wrote {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
