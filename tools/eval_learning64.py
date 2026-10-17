"""Inference-only diagnostic; JSONL output retains every HTTP response and score.

Run against an already running llama-server with the base model or runtime LoRA.
No generated command is executed. Acceptance misses need semantic review.
"""

import argparse
import base64
import hashlib
import json
import re
import shlex
import sys
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path


def load_cases(path):
    data = path.read_bytes()
    cases, seen = [], set()
    for number, line in enumerate(data.decode('utf-8').splitlines(), 1):
        if not line.strip():
            continue
        case = json.loads(line)
        if not isinstance(case, dict):
            raise ValueError(f'line {number}: expected an object')
        for field in ('id', 'group', 'request', 'reference'):
            if not isinstance(case.get(field), str) or not case[field].strip():
                raise ValueError(f'line {number}: invalid {field}')
        if case['id'] in seen:
            raise ValueError(f'duplicate id: {case["id"]}')
        seen.add(case['id'])
        messages = case.get('messages')
        if (not isinstance(messages, list) or len(messages) != 2 or
                any(not isinstance(m, dict) or m.get('role') != role or
                    not isinstance(m.get('content'), str) or not m['content']
                    for m, role in zip(messages, ('system', 'user')))):
            raise ValueError(f'line {number}: expected exact system/user messages')
        patterns = case.get('accept')
        if not isinstance(patterns, list) or not patterns:
            raise ValueError(f'line {number}: accept must be a nonempty regex list')
        for pattern in patterns:
            if not isinstance(pattern, str) or not pattern.startswith('^') or not pattern.endswith('$'):
                raise ValueError(f'line {number}: accept regex must be anchored')
            re.compile(pattern)
        cases.append(case)
    if not cases:
        raise ValueError('no cases')
    return cases, hashlib.sha256(data).hexdigest()


def same_shell_whitespace(left, right):
    # Keep quotes intact; newlines are shell operators, never whitespace to fold.
    if any(char in left + right for char in '\r\n\x00'):
        return False
    if '\\' in left + right:
        return left.strip() == right.strip()
    try:
        return shlex.split(left, posix=False) == shlex.split(right, posix=False)
    except ValueError:
        return False


def classify(case, response, extract, collect):
    result = {'content': None, 'finish_reason': None, 'extracted_command': None,
              'serving_commands': [], 'generation': 'response_error',
              'exact_reference_match': False, 'whitespace_reference_match': False,
              'regex_match': False, 'accepted': False, 'verdict': 'needs_review'}
    try:
        choice = response['choices'][0]
        content = choice['message']['content']
        finish = choice['finish_reason']
        if not isinstance(content, str):
            return result
    except (KeyError, IndexError, TypeError):
        return result
    result.update(content=content, finish_reason=finish)
    extracted = extract(content)
    result['extracted_command'] = extracted or None
    result['serving_commands'] = collect([(content, finish)])
    result['generation'] = ('length' if finish == 'length' else
                            'empty' if not content.strip() else
                            'unfinished' if finish != 'stop' else
                            'parse' if not extracted else
                            'parser_filtered' if not result['serving_commands'] else 'complete')
    result['exact_reference_match'] = content.strip() == case['reference'].strip()
    result['whitespace_reference_match'] = same_shell_whitespace(content, case['reference'])
    result['regex_match'] = any(re.fullmatch(pattern, content.strip()) is not None
                                for pattern in case['accept'])
    result['accepted'] = result['generation'] == 'complete' and (
        result['regex_match'] or result['whitespace_reference_match'])
    if result['accepted']:
        result['verdict'] = 'accepted'
    return result


def apply_harness(case, record, enabled, lint_reject=None):
    result = {'filtered_command': None, 'filtered_accepted': False,
              'harness_status': 'not_run', 'harness_reason': 'Mac harness not requested'}
    if not enabled:
        return result
    if sys.platform != 'darwin':
        return {**result, 'harness_status': 'unavailable',
                'harness_reason': 'Mac harness requires Darwin; no macOS verification'}
    if not record['serving_commands']:
        return {**result, 'harness_status': 'no_command',
                'harness_reason': 'Serving parser/finish filter returned no command'}
    if lint_reject is None:
        from score_teacher_eval import lint_reject
    command = record['serving_commands'][0]
    if lint_reject(command, case['request']):
        return {**result, 'harness_status': 'rejected',
                'harness_reason': 'Serving length/control, safety, or macOS lint gate rejected'}
    return {**result, 'filtered_command': command, 'harness_status': 'accepted',
            'harness_reason': None,
            'filtered_accepted': same_shell_whitespace(command, case['reference']) or
                any(re.fullmatch(pattern, command) is not None for pattern in case['accept'])}


def query(base_url, messages):
    payload = {'messages': messages, 'seed': 42, 'temperature': 0, 'max_tokens': 256,
               'repeat_penalty': 1.08, 'repeat_last_n': 64,
               'stop': ['\n', '<|im_end|>', '```']}
    request = urllib.request.Request(base_url.rstrip('/') + '/chat/completions',
                                     data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'})
    result = {'request': payload}
    try:
        try:
            http = urllib.request.urlopen(request, timeout=180)
        except urllib.error.HTTPError as error:
            http = error
        with http:
            body = http.read()
            result.update(status=http.status, headers=dict(http.headers),
                          body=body.decode('utf-8', errors='replace'),
                          body_base64=base64.b64encode(body).decode('ascii'))
        try:
            result['response'] = json.loads(body)
        except (ValueError, UnicodeError):
            result['response'] = None
    except (OSError, TimeoutError) as error:
        result.update(error=f'{type(error).__name__}: {error}', response=None)
    return result


def summarize(records):
    counts = Counter(record['generation'] for record in records)
    return {'total': len(records), 'generation': dict(counts),
            **{key: sum(bool(record[key]) for record in records)
               for key in ('accepted', 'exact_reference_match',
                           'whitespace_reference_match', 'regex_match')},
            'needs_review': sum(record['verdict'] == 'needs_review' for record in records),
            'harness_status': dict(Counter(record.get('harness_status') for record in records)),
            'filtered_accepted': sum(record.get('filtered_accepted', False) for record in records)}


def run(base_url, cases, digest, out, tag, extract, collect, mac_harness=False):
    with out.open('x', encoding='utf-8') as stream:
        def write(record):
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
            stream.flush()
        write({'type': 'metadata', 'tag': tag, 'cases_sha256': digest,
               'base_url': base_url, 'case_count': len(cases),
               'host_platform': sys.platform, 'mac_harness_requested': mac_harness,
               'mac_verification': ('serving filters on Darwin; commands not executed'
                                    if mac_harness and sys.platform == 'darwin' else
                                    'not run; no macOS verification'),
               'scoring': 'entire raw content fullmatch or quote-preserving reference whitespace; stop required; misses need semantic review'})
        records = []
        for case in cases:
            http = query(base_url, case['messages'])
            record = {'type': 'case', 'case': case, 'http': http,
                      **classify(case, http.get('response') if http.get('status') == 200 else None,
                                 extract, collect)}
            record.update(apply_harness(case, record, mac_harness))
            records.append(record)
            write(record)
            print(f'{tag} {case["id"]}: {record["generation"]} {record["verdict"]}', flush=True)
        summary = {'type': 'summary', 'pooled': summarize(records), 'groups': {
            group: summarize([r for r in records if r['case']['group'] == group])
            for group in sorted({case['group'] for case in cases})}}
        write(summary)
    print(json.dumps(summary, indent=2))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True, help='llama-server OpenAI endpoint ending /v1')
    parser.add_argument('--cases', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path, help='new JSONL file; never overwritten')
    parser.add_argument('--tag', default='')
    parser.add_argument('--mac-harness', action='store_true',
                        help='apply serving safety/macOS filters on Darwin only')
    args = parser.parse_args()
    cases, digest = load_cases(args.cases)
    from whatisit import engine
    run(args.base_url, cases, digest, args.out, args.tag,
        engine.extract, engine._collect_commands, args.mac_harness)
    return 0


if __name__ == '__main__':
    sys.exit(main())
