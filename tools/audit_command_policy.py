#!/usr/bin/env python3
"""Compare legacy/current acceptance on training candidates without executing commands.

Default mode requires macOS and the stock tool PATH. --structural-only disables
host probes in both policies; its results are not macOS acceptance evidence.
"""

import argparse
from collections import Counter
from contextlib import ExitStack
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import platform
import subprocess
import types
from unittest.mock import patch

from whatisit_macos import maclint

ROOT = Path(__file__).resolve().parents[1]
STOCK_PATH = '/usr/bin:/bin:/usr/sbin:/sbin'


def training_candidates(train, requests, raw):
    def rows(path):
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    by_id = {row['id']: row for row in rows(requests)}
    return {
        'v3_nonempty_targets': [(by_id[row['id']]['request'], by_id[row['id']].get('path'),
                                 row['messages'][-1]['content'])
                                for row in rows(train) if row['messages'][-1]['content']],
        'parsed_complete_teacher_samples': [(row['request'], row.get('path'), sample['command'])
                                            for row in rows(raw) for sample in row['samples']
                                            if sample.get('parsed') is True and
                                            sample.get('finish_reason') == 'stop' and sample.get('command')],
    }


def compare(candidates, before, after, example_limit=6):
    counts = Counter(dict.fromkeys(('total', 'before_accepted', 'after_accepted',
                                   'newly_rejected', 'newly_accepted'), 0))
    categories, examples = Counter(), []
    for request, path, command in candidates:
        rejected_before, findings = bool(before(command, request, path)), after(command, request, path)
        counts['total'] += 1
        counts['before_accepted'] += not rejected_before
        counts['after_accepted'] += not bool(findings)
        counts['newly_rejected'] += not rejected_before and bool(findings)
        counts['newly_accepted'] += rejected_before and not bool(findings)
        if not rejected_before and findings:
            categories.update(findings.keys())
            if len(examples) < example_limit:
                examples.append({'request': request, 'path': path, 'command': command, 'reasons': findings})
    return {'counts': dict(counts), 'new_rejection_categories': dict(sorted(categories.items())),
            'examples': examples}


def audit_policy(base='c826c03', structural_only=False):
    if not structural_only and platform.system() != 'Darwin':
        raise RuntimeError('Host-grounded acceptance requires macOS; use --structural-only for a portable comparison.')
    if not structural_only and os.environ.get('PATH') != STOCK_PATH:
        raise RuntimeError(f'Host-grounded acceptance requires PATH={STOCK_PATH}')
    from whatisit import safety
    version = importlib.metadata.version('whatisit')
    if version != '0.4.0':
        raise RuntimeError('Acceptance comparison requires whatisit==0.4.0')
    resolved_base = subprocess.run(['git', 'rev-parse', '--verify', f'{base}^{{commit}}'], cwd=ROOT,
                                   check=True, capture_output=True, text=True).stdout.strip()
    source = subprocess.run(['git', 'show', f'{resolved_base}:src/whatisit_macos/maclint.py'], cwd=ROOT,
                            check=True, capture_output=True).stdout
    old = types.ModuleType('legacy_maclint')
    exec(compile(source, f'{resolved_base}:maclint.py', 'exec'), old.__dict__)

    def before(command, request, path):
        # Legacy worker never passed its structured explicit path to the deletion guard.
        return (len(command) > 4096 or any(c in command for c in '\x00\r\n') or
                any(level == 'DANGER' for level, _ in safety.check(command)) or old.problems(command) or
                old.unrequested_deletion(command, request) or
                any(m.group(0).casefold() not in request.casefold()
                    for m in safety.PLACEHOLDER_HINT.finditer(command)))

    datasets = training_candidates(ROOT / 'data/distill/stage2-v3/train.jsonl',
                                   ROOT / 'data/distill/stage2-v3/requests.jsonl',
                                   ROOT / 'data/teacher/roihu_full_raw_samples.jsonl')
    with ExitStack() as stack:
        if structural_only:
            for policy in (old, maclint):
                stack.enter_context(patch.object(policy, '_man_text', return_value=''))
                stack.enter_context(patch.object(policy, '_ps_known', return_value=frozenset()))
            stack.enter_context(patch.object(maclint.shutil, 'which', side_effect=lambda command: command))
            stack.enter_context(patch.object(maclint.os.path, 'exists', return_value=True))
            stack.enter_context(patch.object(maclint.subprocess, 'run', return_value=
                                            types.SimpleNamespace(returncode=0, stdout='')))
        results = {name: compare(items, before, lambda command, request, path:
                                maclint.validation_findings(command, request, path, safety=safety))
                   for name, items in datasets.items()}
    sha = lambda content: hashlib.sha256(content).hexdigest()
    return {
        'scope': ('Portable structural comparison; host probes disabled identically. Not macOS acceptance evidence.'
                  if structural_only else 'macOS host-grounded acceptance with stock PATH.'),
        'candidate_scope': 'Training v3 nonempty targets and parsed complete raw teacher samples only; no eval targets or candidate execution.',
        'legacy_path_behavior': 'Legacy worker omitted structured explicit path when validating commands.',
        'baseline_commit': resolved_base, 'baseline_policy_sha256': sha(source),
        'current_policy_sha256': sha(Path(maclint.__file__).read_bytes()),
        'current_parser_sha256': sha((ROOT / 'src/whatisit_macos/shell.py').read_bytes()),
        'scanner_version': version, 'scanner_source_sha256': sha(Path(inspect.getfile(safety)).read_bytes()),
        'datasets': results,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='c826c03')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--structural-only', action='store_true')
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(f'Output already exists: {args.output}')
    report = audit_policy(args.base, args.structural_only)
    with args.output.open('x') as output:
        output.write(json.dumps(report, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
