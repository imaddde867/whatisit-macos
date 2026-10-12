"""Isolated adapter for the optional upstream local generator."""

import json
import sys
from pathlib import Path

MACOS_PREFIX = ('Target system: macOS, using zsh and the built-in BSD command-line tools. '
                'Use macOS commands and flags, not Linux/GNU-only ones. If required inputs are missing or '
                'the request is ambiguous, output no command.\n')


def suggest(payload: object, harness: str = 'lint') -> dict:
    """harness 'model' skips the macOS lint; it exists only so tools/eval_fallback.py can ablate it."""
    if not isinstance(payload, dict) or set(payload) != {'request', 'path'}:
        return _unsupported('Invalid local generation request.')
    request = payload['request']
    if (not isinstance(request, str) or not request.strip() or len(request) > 2000 or
            any(char in request for char in '\x00\r\n')):
        return _unsupported('Request must contain 1–2000 characters.')
    path = payload['path']
    if path is not None and (not isinstance(path, str) or len(path) > 8192):
        return _unsupported('Invalid explicit inputs.')
    try:
        from whatisit import config, engine, safety
    except ImportError:
        return _unsupported("Install with `pip install 'whatisit-macos[local]'` to enable local generation.")

    try:
        saved = config.load_config()
        model = config.find_model()
        data_dir = config.data_dir()
    except (OSError, ValueError, TypeError) as error:
        return _unsupported(f'Local configuration failed: {error}')
    cfg = dict(config.DEFAULTS)
    if isinstance(saved.get('threads'), int) and saved['threads'] >= 0:
        cfg['threads'] = saved['threads']
    if isinstance(saved.get('force_tcp'), bool):
        cfg['force_tcp'] = saved['force_tcp']
    if saved.get('server_port') is None or (type(saved.get('server_port')) is int and
                                             0 < saved['server_port'] < 65536):
        cfg['server_port'] = saved.get('server_port')
    if isinstance(saved.get('llama_server'), str):
        cfg['llama_server'] = saved['llama_server']
    server_setting = config.env('LLAMA_SERVER')
    server = None
    if server_setting and Path(server_setting).exists():
        server = Path(server_setting)
    elif (data_dir / 'bin' / 'llama-server').exists():
        server = data_dir / 'bin' / 'llama-server'
    elif isinstance(cfg.get('llama_server'), str) and Path(cfg['llama_server']).exists():
        server = Path(cfg['llama_server'])
    if not model or not model.is_file():
        return _unsupported('No local model is configured; run `whatisit setup` in the local environment.')
    if server is None:
        return _unsupported('No local llama-server is configured; run `whatisit setup` in the local environment.')

    prompt = MACOS_PREFIX + request
    if path is not None:
        prompt += '\nExplicit inputs: ' + json.dumps({'path': path}, ensure_ascii=False)
    cfg.update(openai_base_url='', max_tokens=256, ctx_size=4096,
               host_context=False, idle_timeout=60)
    try:
        commands, _, mode = engine.generate(prompt, cfg, force_oneshot=False, quiet=True)
    except (OSError, RuntimeError, ValueError, TypeError) as error:
        return _unsupported(f'Local generation failed: {str(error)[:500]}')
    if mode != 'server':
        return _unsupported('Local generation did not use the finish-aware server.')
    if not commands:
        return _unsupported('Local generation returned no complete command.')
    command = commands[0]
    if len(command) > 4096 or any(char in command for char in '\x00\r\n'):
        return _unsupported('Local generation returned an invalid command.')
    findings = safety.check(command)
    if any(severity == 'DANGER' for severity, _ in findings):
        return _unsupported('Local generation returned a command flagged as dangerous.')
    if harness != 'model':
        from whatisit_macos.maclint import problems, unrequested_deletion
        issues = problems(command) + unrequested_deletion(command, request)
        # PLACEHOLDER_HINT only: upstream's <...> pattern also matches redirections like `sort <a >b`.
        issues += [f'{m.group(0)!r} is a placeholder, not something you named'
                   for m in safety.PLACEHOLDER_HINT.finditer(command)
                   if m.group(0).casefold() not in request.casefold()]
        if issues:
            return _unsupported('Generated command is not valid on macOS: ' + '; '.join(issues[:3]))
    notes = ['Generated locally; review before running.']
    notes.extend(f'Review: {reason}' for severity, reason in findings if severity == 'CAUTION')
    return {'status': 'suggestion', 'command': command, 'reason': '', 'notes': notes,
            'sources': ['local whatisit model']}


def _unsupported(reason: str) -> dict:
    return {'status': 'unsupported', 'command': None, 'reason': reason,
            'notes': [], 'sources': []}


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        answer = suggest(payload)
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        answer = _unsupported('Invalid local generation request.')
    json.dump(answer, sys.stdout)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
