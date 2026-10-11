"""Run the optional local shell generator in an isolated worker process."""

import json
import os
import subprocess
import sys
from dataclasses import asdict

SAFE_ENV = {'HOME', 'LANG', 'LC_ALL', 'PATH', 'PYTHONPATH', 'TMPDIR',
            'VIRTUAL_ENV', 'XDG_DATA_HOME'}


def suggest_local(request: str, *, path: str | None = None, log_filter=None,
                  service_target=None) -> dict:
    if (not isinstance(request, str) or not request.strip() or len(request) > 2000 or
            any(char in request for char in '\x00\r\n')):
        return _failure('Request must contain 1–2000 characters on one line.')
    payload = {'request': request, 'path': path,
               'log_filter': asdict(log_filter) if log_filter is not None else None,
               'service_target': asdict(service_target) if service_target is not None else None}
    env = {key: value for key, value in os.environ.items() if key in SAFE_ENV}
    for key in ('WHATISIT_MODEL', 'WHATISIT_DATA_DIR', 'WHATISIT_LLAMA_SERVER'):
        if key in os.environ:
            env[key] = os.environ[key]
    try:
        result = subprocess.run([sys.executable, '-m', 'whatisit_macos.local_recovery_worker'],
                                input=json.dumps(payload), capture_output=True, text=True,
                                env=env, timeout=180, check=False)
        if result.returncode == 0 and len(result.stdout) <= 16_384:
            answer = json.loads(result.stdout)
        else:
            answer = None
        if _valid_answer(answer):
            return answer
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, TypeError, ValueError):
        pass
    return _failure('Local generation failed; no command was produced.')


def _valid_answer(answer: object) -> bool:
    if not isinstance(answer, dict):
        return False
    if (not isinstance(answer.get('reason'), str) or
            not isinstance(answer.get('notes'), list) or
            not all(isinstance(note, str) for note in answer['notes']) or
            not isinstance(answer.get('sources'), list) or
            not all(isinstance(source, str) for source in answer['sources'])):
        return False
    if answer.get('status') == 'suggestion':
        return (isinstance(answer.get('command'), str) and bool(answer['command'].strip()) and
                len(answer['command']) <= 4096 and
                not any(char in answer['command'] for char in '\x00\r\n'))
    return answer.get('status') == 'unsupported' and answer.get('command') is None


def _failure(reason: str) -> dict:
    return {'status': 'unsupported', 'command': None, 'reason': reason,
            'notes': [], 'sources': []}
