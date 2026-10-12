#!/usr/bin/env python3
"""Verify raw teacher samples on macOS and build a prompt-matched chat dataset."""

import argparse
from collections import Counter
import hashlib
import json
import platform
import random
import re
import shlex
import statistics
from pathlib import Path

from check_corpus import jaccard, words
from teacher_sample import TEACHER_SYSTEM_PROMPT
from whatisit_macos.local_recovery_worker import MACOS_PREFIX
from whatisit_macos.maclint import problems, unrequested_deletion

SUBCOMMANDS = {'git', 'brew', 'defaults', 'hdiutil', 'diskutil', 'launchctl', 'npm', 'pip', 'plutil', 'xcrun'}
WRAPPERS = {'sudo', 'env', 'command', 'time', 'nohup'}
SHORT_OPTION_TOOLS = {'ls', 'cp', 'mv', 'rm', 'df', 'du', 'ps', 'grep', 'sort', 'tar', 'chmod'}


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def signature(command):
    """Conservative command signature for leakage: tool/subcommand and option names."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=';&|')
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError as error:
        raise ValueError(f'cannot tokenize command for leakage check: {error}') from error
    segments, current = [], []
    for token in tokens + [';']:
        if token in ('|', '|&', '&&', '||', ';', '&'):
            if current:
                segments.append(current)
            current = []
        else:
            current.append(token)
    result = []
    for segment in segments:
        while segment and (segment[0] in WRAPPERS or re.fullmatch(r'\w+=.*', segment[0])):
            segment.pop(0)
        if not segment:
            continue
        tool = Path(segment[0]).name
        args = segment[1:]
        if tool in SUBCOMMANDS and args and not args[0].startswith('-'):
            tool += ' ' + args.pop(0)
        flags = set()
        for arg in args:
            option = arg.split('=')[0]
            if tool in SHORT_OPTION_TOOLS and re.fullmatch(r'-[A-Za-z]{2,4}', option):
                flags.update('-' + char for char in option[1:])
            elif re.fullmatch(r'-[0-9]', option):
                flags.add(option)
            elif re.match(r'^-{1,2}[A-Za-z]', option):
                flags.add(option if re.fullmatch(r'-{1,2}[A-Za-z][\w-]*', option) else option[:2])
        flags = tuple(sorted(flags))
        result.append((tool, flags))
    if not result:
        raise ValueError('empty command signature in leakage check')
    return tuple(result)


def check_inputs(requests_path, raw_path, manifest_path):
    requests = read_jsonl(requests_path)
    raw = read_jsonl(raw_path)
    manifest = json.loads(manifest_path.read_text())
    if not requests or not raw or len(raw) > len(requests):
        raise ValueError('corpus/raw counts are invalid')
    if len({r['id'] for r in requests}) != len(requests):
        raise ValueError('duplicate corpus id')
    for i, record in enumerate(raw):
        request = requests[i]
        if record.get('id') != request['id'] or record.get('request') != request['request']:
            raise ValueError(f'raw row {i + 1} does not match corpus prefix')
        if (request['kind'] not in ('answer', 'abstain') or
                not isinstance(record.get('samples'), list) or len(record['samples']) != 5):
            raise ValueError(f'invalid kind or sample count for {request["id"]}')
        for sample in record['samples']:
            if (not isinstance(sample, dict) or 'command' not in sample or
                    not isinstance(sample.get('parsed'), bool) or
                    sample.get('command') is not None and not isinstance(sample['command'], str)):
                raise ValueError(f'invalid sample schema for {request["id"]}')
    required = ('model', 'quant', 'server', 'host', 'seed_base', 'temperature', 'top_p',
                'max_tokens', 'wall_seconds_this_run', 'requests_file_sha256', 'system_prompt_sha256')
    if any(manifest.get(k) in (None, '') for k in required):
        raise ValueError('teacher manifest is incomplete')
    if manifest.get('requests_total') != len(raw) or manifest.get('samples_per_request') != 5:
        raise ValueError('teacher manifest counts do not match raw samples')
    if manifest['requests_file_sha256'] != hashlib.sha256(requests_path.read_bytes()).hexdigest():
        raise ValueError('teacher manifest request hash mismatch')
    if manifest['system_prompt_sha256'] != hashlib.sha256(TEACHER_SYSTEM_PROMPT.encode()).hexdigest():
        raise ValueError('teacher system prompt hash mismatch')
    return requests, raw, manifest


def eval_leakage(requests, labels, eval_dir):
    eval_requests, eval_commands = [], {}
    for split in ('dev', 'everyday', 'frozen'):
        for case in read_jsonl(eval_dir / f'{split}.jsonl'):
            eval_requests.append((split, words(case['request'])))
            for command in [case.get('reference'), *(case.get('also_correct') or [])]:
                if isinstance(command, str) and command.strip():
                    for part in signature(command):
                        eval_commands.setdefault(part, set()).add(split)
    hits = set()
    for row in requests:
        for split, target in eval_requests:
            if jaccard(words(row['request']), target) >= 0.7:
                hits.add((row['id'], 'request', split))
    for row in labels:
        command = row['messages'][-1]['content']
        if command:
            for part in signature(command):
                for split in eval_commands.get(part, ()):
                    hits.add((row['id'], 'command signature', split))
    return sorted(hits)


def build(requests_path, raw_path, manifest_path, eval_dir, output_path, report_path, review_path):
    if platform.system() != 'Darwin':
        raise RuntimeError('host-grounded verification must run on macOS')
    from whatisit import config, safety

    paths = (output_path, report_path, review_path)
    if any(path.exists() for path in paths):
        raise FileExistsError('output already exists; choose fresh paths')
    requests, raw, manifest = check_inputs(requests_path, raw_path, manifest_path)
    labels, decisions, abstain_reasons, dropped = [], Counter(), Counter(), []
    request_by_id = {r['id']: r for r in requests}
    agreement, rejects = Counter(), Counter()
    candidates = rejected_candidates = 0
    tokens = []
    for record in raw:
        valid = Counter()
        nulls = 0
        for sample in record['samples']:
            token_count = sample.get('completion_tokens')
            if isinstance(token_count, int):
                tokens.append(token_count)
            if sample['parsed'] is not True or sample.get('finish_reason') != 'stop':
                rejects['unparsed_or_incomplete'] += 1
                continue
            command = sample['command']
            if command is None:
                nulls += 1
                continue
            candidates += 1
            if not command.strip() or len(command) > 4096 or any(c in command for c in '\x00\r\n'):
                rejects['invalid_command'] += 1
                rejected_candidates += 1
                continue
            findings = safety.check(command)
            lint_issues = problems(command)
            deletion_issues = unrequested_deletion(command, record['request'])
            placeholders = [m.group(0) for m in safety.PLACEHOLDER_HINT.finditer(command)
                            if m.group(0).casefold() not in record['request'].casefold()]
            if any(severity == 'DANGER' for severity, _ in findings):
                rejects['danger'] += 1
            if lint_issues:
                rejects['macos_lint'] += 1
            if deletion_issues:
                rejects['deletion_guard'] += 1
            if placeholders:
                rejects['placeholder'] += 1
            if any(severity == 'DANGER' for severity, _ in findings) or lint_issues or deletion_issues or placeholders:
                rejected_candidates += 1
                continue
            valid[command] += 1
        best = max(valid.values(), default=0)
        agreement[best] += 1
        if best >= 3:
            target = min((cmd for cmd, n in valid.items() if n == best), key=lambda cmd: (len(cmd), cmd))
            decision = 'kept'
        elif nulls >= 3 or request_by_id[record['id']]['kind'] == 'abstain':
            target = ''
            decision = 'abstain'
            abstain_reasons['teacher_null_majority' if nulls >= 3 else 'author_abstain_no_majority'] += 1
        else:
            reason = 'no_valid_command' if not valid else 'no_majority'
            decisions['dropped_' + reason] += 1
            dropped.append((record['id'], reason, best))
            continue
        decisions[decision] += 1
        labels.append({'id': record['id'], 'messages': [
            {'role': 'system', 'content': config.SYSTEM_PROMPT},
            {'role': 'user', 'content': MACOS_PREFIX + record['request']},
            {'role': 'assistant', 'content': target}]})

    leakage = eval_leakage(requests, labels, eval_dir)
    if leakage:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(f'# Evaluation leakage gate failed\n\nTeacher: {manifest["model"]}; '
                               f'raw requests: {len(raw)}; overlaps: {len(leakage)}. '
                               'No training dataset was written. Overlaps identify corpus rows and '
                               'evaluation split only.\n\n' +
                               ''.join(f'- {rid}: {kind} overlaps {split}\n'
                                       for rid, kind, split in leakage))
        raise ValueError(f'evaluation leakage: {len(leakage)} overlaps; see {report_path}')
    commands = [r for r in labels if r['messages'][-1]['content']]
    sample = random.Random(7).sample(commands, min(30, len(commands)))
    drop_details = ''.join(f'- {rid}: {reason} (maximum agreement {best})\n'
                           for rid, reason, best in dropped) or 'None.\n'
    wall = manifest['wall_seconds_this_run']
    token_rate = (f'{sum(tokens) / wall:.1f} tokens/s' if wall and
                  manifest.get('requests_written_this_run') == len(raw) else 'unavailable for resumed run')
    report = f'''# Distillation quality report

Host: {platform.platform()} (macOS verification)

Teacher: {manifest['model']}
Quant: {manifest['quant']}
Server: {manifest['server']}
Teacher host: {manifest['host']}
Request SHA-256: {manifest['requests_file_sha256']}
Teacher prompt SHA-256: {manifest['system_prompt_sha256']}
Sampling: n=5, temperature={manifest['temperature']}, top-p={manifest['top_p']}, max tokens={manifest['max_tokens']}, seed base={manifest['seed_base']}.

Requests: {len(raw)}; kept commands: {decisions['kept']}; abstain: {decisions['abstain']}; dropped: {decisions['dropped_no_valid_command'] + decisions['dropped_no_majority']} ({decisions['dropped_no_valid_command']} no valid command, {decisions['dropped_no_majority']} no majority).
Agreement histogram (maximum identical verified commands): {dict(sorted(agreement.items()))}.
Teacher command candidates: {candidates}; rejected candidates: {rejected_candidates} ({rejected_candidates / candidates if candidates else 0:.1%}). Rejection findings (categories can overlap): {dict(sorted(rejects.items()))}.
Abstain reasons: {dict(sorted(abstain_reasons.items()))}.

Dropped rows:
{drop_details}

Recorded completion tokens: {sum(tokens)} total, {statistics.median(tokens) if tokens else 'unavailable'} median per sample.
Manifest wall time: {wall} s for this invocation ({manifest.get('requests_written_this_run', 'unknown')} requests written); throughput: {token_rate}; per-request latency was not recorded by the sampler.
Manifest metadata: finished={manifest.get('finished_at', 'unknown')}, top-k={manifest.get('top_k', 'unknown')}, note={manifest.get('note', '')!r}.

Evaluation leakage gate: passed against dev, everyday, and frozen requests and command signatures. The frozen set was used only for this gate.

No-command target: empty assistant content. The serving worker returns `unsupported` with no command when upstream generation produces no complete command; the worker-path test covers this behavior. The MLX prompt audit must still confirm that an empty target trains its end-of-turn token on the Mac. A live-model abstention probe remains pending.

Human precision review: **pending**. {len(sample)} rows were saved to `{review_path}` with blank human verdicts; no precision estimate is claimed. At least 30 reviewed rows are required for acceptance.
'''
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in labels))
    review_path.write_text(''.join(json.dumps({**row, 'human_correct': None, 'review_notes': ''},
                                               ensure_ascii=False) + '\n' for row in sample))
    report_path.write_text(report)
    return decisions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    defaults = {'requests': 'data/corpus/requests.jsonl',
                'raw': 'data/teacher/pilot_raw_samples.jsonl',
                'manifest': 'data/teacher/pilot_manifest.json',
                'eval-dir': 'eval',
                'out': 'data/distill/pilot_train.jsonl',
                'report': 'data/distill/quality_report.md',
                'review-sample': 'data/distill/pilot_review_sample.jsonl'}
    for flag, default in defaults.items():
        parser.add_argument('--' + flag, default=Path(default), type=Path)
    args = parser.parse_args()
    print(build(args.requests, args.raw, args.manifest, args.eval_dir,
                args.out, args.report, args.review_sample))


if __name__ == '__main__':
    main()
