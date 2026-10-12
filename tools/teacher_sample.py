#!/usr/bin/env python3
"""Sample teacher answers for training-request corpus (stdlib only; run on the GPU machine).

    python3 tools/teacher_sample.py --requests data/corpus/requests.jsonl \
        --out data/teacher/raw_samples.jsonl --manifest data/teacher/manifest.json \
        --base-url http://127.0.0.1:8080/v1 --model <served-model-name> --n 5 --limit 100

Talks to any OpenAI-compatible /v1/chat/completions server (llama.cpp server, vLLM, LM Studio, Ollama).
Appends one JSON line per request and skips ids already present, so an interrupted run resumes.
No macOS verification happens here; that runs later on a Mac.
"""

import argparse
import concurrent.futures as futures
import hashlib
import json
import platform
import re
import sys
import time
import urllib.request
from pathlib import Path

TEACHER_SYSTEM_PROMPT = """You are an expert macOS command-line assistant. Reply with exactly one JSON object and nothing else.

If the request can be done with one shell command line, reply: {"command": "<the command>"}
Otherwise reply: {"command": null, "reason": "<short reason>"}

Rules:
- Target: current macOS on Apple Silicon, zsh, the built-in BSD userland. Assume NO Homebrew and no GNU coreutils (no gsed, no sha256sum, no free, no ip, no xclip).
- The command is a single command line; pipelines and && are allowed. No explanation, no markdown fences.
- Use the literal file names, paths and values from the request. Never emit placeholders such as <file>, {{name}}, /path/to/ or your_x.
- Use only tools and flags you are certain exist on macOS. If unsure of a flag, use a simpler correct form.
- Do not use sudo unless the request says so. Do not modify system settings unless the request asks for it.
- Reply {"command": null, ...} when a required value is missing, the request is ambiguous, it asks for something destructive without naming the target, or it cannot be done from the shell.
"""


def post(base_url, payload, timeout):
    request = urllib.request.Request(base_url.rstrip('/') + '/chat/completions',
                                     data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def parse_answer(text):
    """Return (command_or_None, reason, ok). Strips <think> blocks and fences, takes the last JSON object."""
    text = re.sub(r'<think>.*?</think>', '', text or '', flags=re.S).strip()
    text = re.sub(r'^```(?:json)?|```$', '', text.strip(), flags=re.M).strip()
    decoder = json.JSONDecoder()
    for start in reversed([m.start() for m in re.finditer(r'\{', text)]):
        try:
            obj, _ = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and 'command' in obj:
            command = obj['command']
            if command is None:
                return None, str(obj.get('reason', ''))[:300], True
            if isinstance(command, str) and command.strip() and '\n' not in command.strip():
                return command.strip(), '', True
    return None, '', False


def sample_one(args, request, index):
    payload = {'model': args.model, 'temperature': args.temperature, 'top_p': args.top_p,
               'max_tokens': args.max_tokens, 'seed': args.seed + index,
               'messages': [{'role': 'system', 'content': TEACHER_SYSTEM_PROMPT},
                            {'role': 'user', 'content': request}]}
    if args.top_k:
        payload['top_k'] = args.top_k
    for attempt in range(3):
        try:
            data = post(args.base_url, payload, args.timeout)
            choice = data['choices'][0]
            text = choice['message'].get('content') or ''
            command, reason, ok = parse_answer(text)
            usage = data.get('usage', {})
            return {'command': command, 'reason': reason, 'parsed': ok,
                    'finish_reason': choice.get('finish_reason'),
                    'completion_tokens': usage.get('completion_tokens'),
                    'raw': None if ok else text[:500]}
        except Exception as error:  # network/server hiccup: retry, then record the failure
            last = str(error)[:200]
            time.sleep(2 * (attempt + 1))
    return {'command': None, 'reason': '', 'parsed': False, 'finish_reason': 'error', 'raw': last}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--requests', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:8080/v1')
    parser.add_argument('--model', required=True, help='model name as served')
    parser.add_argument('--n', type=int, default=5, help='samples per request')
    parser.add_argument('--limit', type=int, default=0, help='first K requests only (0 = all)')
    parser.add_argument('--temperature', type=float, default=0.7)
    parser.add_argument('--top-p', type=float, default=0.95)
    parser.add_argument('--top-k', type=int, default=0)
    parser.add_argument('--max-tokens', type=int, default=8192, help='includes thinking tokens')
    parser.add_argument('--concurrency', type=int, default=8)
    parser.add_argument('--timeout', type=int, default=900)
    parser.add_argument('--seed', type=int, default=1000)
    parser.add_argument('--quant', default='', help='free text: quant name/file, for the manifest')
    parser.add_argument('--server', default='', help='free text: server software and version')
    parser.add_argument('--note', default='')
    args = parser.parse_args()

    requests = [json.loads(line) for line in args.requests.read_text().splitlines() if line.strip()]
    if args.limit:
        requests = requests[:args.limit]
    done = set()
    if args.out.exists():
        done = {json.loads(line)['id'] for line in args.out.read_text().splitlines() if line.strip()}
    todo = [r for r in requests if r['id'] not in done]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    written = 0
    with args.out.open('a') as out, futures.ThreadPoolExecutor(args.concurrency) as pool:
        def work(item):
            return item, [sample_one(args, item['request'], i) for i in range(args.n)]
        for item, samples in pool.map(work, todo):
            out.write(json.dumps({'id': item['id'], 'request': item['request'], 'samples': samples},
                                 ensure_ascii=False) + '\n')
            out.flush()
            written += 1
            if written % 25 == 0:
                print(f'{written}/{len(todo)} requests', file=sys.stderr)
    manifest = {
        'script': 'tools/teacher_sample.py', 'finished_at': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'model': args.model, 'quant': args.quant, 'server': args.server, 'base_url': args.base_url,
        'samples_per_request': args.n, 'temperature': args.temperature, 'top_p': args.top_p,
        'top_k': args.top_k, 'max_tokens': args.max_tokens, 'seed_base': args.seed,
        'system_prompt_sha256': hashlib.sha256(TEACHER_SYSTEM_PROMPT.encode()).hexdigest(),
        'requests_file_sha256': hashlib.sha256(args.requests.read_bytes()).hexdigest(),
        'requests_total': len(requests), 'requests_written_this_run': written,
        'wall_seconds_this_run': round(time.time() - started, 1),
        'host': platform.platform(), 'note': args.note,
    }
    args.manifest.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
