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
TRIVIAL = {'echo', 'printf', '[', '[[', 'test', 'true', 'false', ':'}  # shell glue; carries no tool knowledge
PATH_EXTENSIONS = {'txt', 'log', 'csv', 'json', 'plist', 'pdf', 'md', 'sh', 'py', 'zip', 'gz', 'tar', 'png',
                   'jpg', 'jpeg', 'dmg', 'iso', 'app', 'html', 'xml', 'yaml', 'yml', 'conf', 'bak', 'tmp', 'tsv', 'mov',
                   'm4a', 'wav', 'aiff', 'aif', 'mp3', 'mp4', 'zsh', 'bash', 'pkg', 'ips', 'heic', 'db', 'sqlite',
                   'rtf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'key', 'pages', 'numbers', 'swift', 'c',
                   'h', 'js', 'ts', 'rb', 'pl', 'sql', 'ini', 'cfg', 'toml', 'lock', 'out', 'dat', 'bin', 'img',
                   'cer', 'crt', 'pem', 'csr', 'p12', 'gif', 'tiff', 'bmp', 'webp', 'svg', 'epub', 'tgz', 'bz2',
                   'xz', '7z', 'rar', 'sparseimage', 'sparsebundle', 'webloc', 'strings', 'entitlements'}
INTERACTIVE = re.compile(r'\s*(?:sudo\s+)?(?:man|less|more|vi|vim|nano|emacs|top)\b[^|]*$')  # needs a terminal, not an answer
REDIRECT = re.compile(r'^(?:\d*|&)(?:>>|>|<)(?:&\d+)?$')
REVIEW_JACCARD = 0.5
SHORT_OPTION_TOOLS = {'ls', 'cp', 'mv', 'rm', 'df', 'du', 'ps', 'grep', 'sort', 'tar', 'chmod'}


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _segments(command):
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
    if not tokens:
        raise ValueError('empty command signature in leakage check')
    return segments


def _flags(tool, args):
    flags = set()
    for arg in args:
        option = arg.split('=')[0]
        if tool in SHORT_OPTION_TOOLS and re.fullmatch(r'-[A-Za-z]{2,4}', option):
            flags.update('-' + char for char in option[1:])
        elif re.fullmatch(r'-[0-9]', option):
            flags.add(option)
        elif re.match(r'^-{1,2}[A-Za-z]', option):
            flags.add(option if re.fullmatch(r'-{1,2}[A-Za-z][\w-]*', option) else option[:2])
    return tuple(sorted(flags))


PROGRAM_TOOLS = {'sed', 'awk', 'gawk', 'grep', 'egrep', 'fgrep', 'perl', 'mdfind', 'tr', 'jq'}


def _path_like(arg, tool=''):
    """A filesystem operand: a single word of path characters (or a glob or known extension)."""
    if re.search(r'\s', arg) or re.search(r'[=(){}"\']', arg):
        return False  # programs, predicates and queries carry knowledge
    if re.fullmatch(r'\d+(?:\.\d+)?[A-Za-z]{0,2}', arg):
        return tool != 'chmod'  # PIDs, counts and durations are user literals; chmod modes are not
    if tool == 'sysctl':
        return False  # keys such as hw.ncpu look like file.ext
    return bool(re.fullmatch(r'[~./$][\w.*?\[\]~$/+-]*|[\w.*?\[\]+-]+(/[\w.*?\[\]+-]*)+/?', arg) or
                '*' in arg or '.' in arg and arg.rsplit('.', 1)[-1].lower() in PATH_EXTENSIONS)


def _parts(command):
    """Yield (tool, flags, operands) for each non-trivial pipeline stage."""
    for segment in _segments(command):
        while segment and (segment[0] in WRAPPERS or re.fullmatch(r'\w+=.*', segment[0])):
            segment.pop(0)
        if not segment or segment[0] in TRIVIAL:
            continue
        tool = Path(segment[0]).name
        args = segment[1:]
        if tool in SUBCOMMANDS and args and not args[0].startswith('-'):
            tool += ' ' + args.pop(0)
        cleaned, skip = [], False
        for a in args:  # redirections are plumbing, not operands
            if skip:
                skip = False
            elif REDIRECT.fullmatch(a):
                skip = not re.search(r'&\d+$', a)
            elif not re.match(r'^(?:\d*|&)(?:>>|>|<)\S', a):
                cleaned.append(a)
        args = cleaned
        words_ = [a for a in args if a and not a.startswith('-')]
        keep_first = {words_[0]} if tool in PROGRAM_TOOLS and words_ else set()  # sed/grep pattern, not a path
        operands = frozenset(a for a in words_ if a in keep_first or not _path_like(a, tool))
        yield tool, _flags(tool, args), operands


def signature(command):
    """Tool/subcommand and option names per stage, ignoring shell glue such as echo and [. Report-only."""
    return tuple((tool, flags) for tool, flags, _ in _parts(command))


def normalized(command):
    """Stages that carry specific knowledge: tool, flags and non-path operands (sysctl keys, mdls
    attributes, plutil formats, awk programs). A bare tool-plus-flags stage inside a pipeline counts
    only when the whole command is that single stage. Hard leakage check."""
    parts = list(_parts(command))
    return tuple(part for part in parts if part[2] or len(parts) == 1)


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
    """Return (hard, review): hard hits are quarantined; review hits are only reported."""
    eval_requests, eval_signatures, eval_normalized = [], {}, {}
    for split in ('dev', 'everyday', 'frozen', 'heldout'):
        for case in read_jsonl(eval_dir / f'{split}.jsonl'):
            eval_requests.append((split, words(case['request'])))
            for command in [case.get('reference'), *(case.get('also_correct') or [])]:
                if isinstance(command, str) and command.strip():
                    for part in signature(command):
                        eval_signatures.setdefault(part, set()).add(split)
                    for part in normalized(command):
                        eval_normalized.setdefault(part, set()).add(split)
    hard, review = set(), set()
    for row in requests:
        for split, target in eval_requests:
            score = jaccard(words(row['request']), target)
            if score >= 0.7:
                hard.add((row['id'], 'request', split))
            elif score >= REVIEW_JACCARD:
                review.add((row['id'], 'request similarity 0.5-0.7', split))
    for row in labels:
        command = row['messages'][-1]['content']
        if command:
            for part in normalized(command):
                for split in eval_normalized.get(part, ()):
                    hard.add((row['id'], 'normalized command', split))
            for part in signature(command):
                for split in eval_signatures.get(part, ()):
                    review.add((row['id'], 'tool+flags', split))
    return sorted(hard), sorted(review)


def read_quarantine(path, known):
    ids = {}
    for line in path.read_text().splitlines() if path.exists() else []:
        line = line.strip()
        if line and not line.startswith('#'):
            rid, _, why = line.partition('#')
            ids[rid.strip()] = why.strip()
    if set(ids) - known:
        raise ValueError(f'quarantine list names unknown ids: {sorted(set(ids) - known)}')
    return ids


def build(requests_path, raw_path, manifest_path, eval_dir, output_path, report_path, review_path,
          quarantine_path=Path('data/distill/quarantine_ids.txt')):
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
            if INTERACTIVE.fullmatch(command):
                rejects['interactive'] += 1
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

    leakage, review_hits = eval_leakage(requests, labels, eval_dir)
    listed = read_quarantine(quarantine_path, set(request_by_id))
    leakage = sorted(set(leakage) | {(rid, 'author quarantine list: ' + why, 'frozen/dev') for rid, why in listed.items()})
    quarantined = sorted({rid for rid, _, _ in leakage})
    for row in labels:
        if row['id'] in quarantined:
            decisions['kept' if row['messages'][-1]['content'] else 'abstain'] -= 1
    labels = [r for r in labels if r['id'] not in quarantined]
    commands = [r for r in labels if r['messages'][-1]['content']]
    sample = random.Random(7).sample(commands, min(30, len(commands)))
    drop_details = ''.join(f'- {rid}: {reason} (maximum agreement {best})\n'
                           for rid, reason, best in dropped) or 'None.\n'
    wall = manifest['wall_seconds_this_run']
    token_rate = (f'{sum(tokens) / wall:.1f} tokens/s' if wall and
                  manifest.get('requests_written_this_run') == len(raw) else 'unavailable for resumed run')
    by_kind = Counter((kind, split) for _, kind, split in review_hits)
    overlap_text = ('; '.join(f'{kind} vs {split}: {count} rows' for (kind, split), count in sorted(by_kind.items()))
                    or 'none') + f' ({len(review_hits)} row/split pairs; ids are in the review-hit list below).'
    overlap_text += ''.join(f'\n- quarantined {rid}: {kind} {split}' for rid, kind, split in leakage)
    overlap_text += ''.join(f'\n- {rid}: {kind} {split}' for rid, kind, split in review_hits if kind != 'tool+flags')
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

Evaluation leakage gate: {len(quarantined)} rows quarantined (excluded from the dataset, never trained on). Hard checks: request word-Jaccard >= 0.7 and normalized command (tool, flags and non-path operands) against dev, everyday and frozen references. The frozen set was used only for this gate.
Report-only overlaps (not gated): {overlap_text}

No-command target: empty assistant content. The serving worker returns `unsupported` with no command when upstream generation produces no complete command; the worker-path test covers this behavior. The Mac prompt audit (`docs/distill-prompt-audit.json`) confirmed that an empty target trains its end-of-turn token. A live-model abstention probe remains pending.

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
    parser.add_argument('--quarantine', default=Path('data/distill/quarantine_ids.txt'), type=Path)
    args = parser.parse_args()
    print(build(args.requests, args.raw, args.manifest, args.eval_dir,
                args.out, args.report, args.review_sample, args.quarantine))


if __name__ == '__main__':
    main()
