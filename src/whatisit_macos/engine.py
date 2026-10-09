"""Select fixed templates; never execute the suggested command."""

import json
import os
import re
import shlex
from dataclasses import asdict, dataclass
from datetime import datetime
from importlib.resources import files
from typing import Callable


@dataclass(frozen=True)
class LogFilter:
    subsystem: str | None = None
    pid: int | None = None
    level: str | None = None
    start: str | None = None
    end: str | None = None


@dataclass(frozen=True)
class ServiceTarget:
    domain: str | None = None
    label: str | None = None


def load_recipes() -> list[dict]:
    return json.loads(files("whatisit_macos").joinpath("recipes.json").read_text())


def suggest(
    request: str,
    *,
    system: str,
    which: Callable[[str], str | None],
    path: str | None = None,
    log_filter: LogFilter | None = None,
    service_target: ServiceTarget | None = None,
) -> dict:
    """Keyword routing is deliberately a baseline, not an intent classifier."""
    result = {"status": "unsupported", "command": None, "reason": ""}
    if system != "Darwin":
        return {**result, "reason": "This prototype only suggests commands on macOS."}
    tokens = set(re.findall(r"[a-z]+", request.casefold()))
    if tokens & {"delete", "remove", "erase", "disable", "enable", "install", "set", "change", "write"}:
        return {**result, "reason": "This starter catalog supports inspection requests only."}
    matches = [
        recipe for recipe in load_recipes()
        if all(tokens.intersection(group) for group in recipe["match_groups"])
    ]
    if not matches:
        return {**result, "reason": "No documented recipe matches this request yet."}
    if len(matches) != 1:
        status = 'unsupported' if any(r['id'].startswith('app-') or r['id'] == 'unified-log-filter'
                                      for r in matches) else 'ambiguous'
        return {**result, 'status': status, "reason": "Ask for one supported task at a time."}
    recipe = matches[0]
    return render(recipe['id'], request=request, system=system, which=which, path=path,
                  log_filter=log_filter, service_target=service_target)


def render(recipe_id: str, *, request: str, system: str,
           which: Callable[[str], str | None], path: str | None = None,
           log_filter: LogFilter | None = None,
           service_target: ServiceTarget | None = None) -> dict:
    """Validate one catalog selection and render only explicitly supplied inputs."""
    result = {"status": "unsupported", "command": None, "reason": ""}
    if system != 'Darwin':
        return {**result, 'reason': 'This prototype only suggests commands on macOS.'}
    recipe = next((r for r in load_recipes() if r['id'] == recipe_id), None)
    if recipe is None:
        return {**result, 'reason': 'Unknown catalog operation.'}
    tokens = set(re.findall(r'[a-z]+', request.casefold()))
    unsupported = {
        "battery-cycles": {"only", "number", "json", "xml", "capacity", "health"},
        "file-metadata": {"only", "name", "raw", "recursive", "recursively", "every", "directory", "directories"},
        "sleep-assertions": {"history", "historical", "last", "hours", "yesterday", "today", "since",
                             "continuous", "continuously", "monitor", "watch", "live", "log"},
        'app-signature': {'identity', 'developer', 'notarization', 'notarized', 'ticket', 'gatekeeper', 'policy'},
        'app-gatekeeper': {'signature', 'signing', 'ticket', 'offline', 'another', 'other', 'future', 'guarantee'},
        'app-ticket': {'signature', 'signing', 'gatekeeper', 'policy', 'ever', 'revoked', 'offline'},
        'unified-log-filter': {'live', 'stream', 'streaming', 'monitor', 'watch', 'continuous',
                               'debug', 'info', 'fault', 'name', 'archive', 'archives', 'collect',
                               'message', 'messages', 'containing', 'contains', 'category',
                               'count', 'counts', 'statistics', 'all', 'every', 'or',
                               'last', 'since', 'boot', 'today', 'yesterday'},
        'launchd-service': {'owner', 'owns', 'owning', 'ownership', 'pid', 'process', 'running',
                            'identify', 'find', 'discover', 'mapping', 'map', 'plist', 'original',
                            'complete', 'full', 'all', 'every', 'loaded', 'associated', 'start', 'stop',
                            'restart', 'reload', 'load', 'unload', 'kickstart', 'bootstrap', 'bootout',
                            'kill', 'terminate', 'signal', 'enable', 'disable'},
    }
    # shortcut: lexical qualifiers are conservative; use intent parsing before expanding catalog scope.
    if (re.search(r"\ball\s+(?:files|documents)\b", request.casefold()) or
            any(r['id'] != recipe_id and all(tokens.intersection(g) for g in r['match_groups'])
                for r in load_recipes()) or
            tokens & unsupported[recipe["id"]] or
            (recipe_id != 'unified-log-filter' and tokens & {'log', 'logs'}) or
            tokens & {'then', 'json', 'xml', 'trace', 'tracing',
                      'delete', 'remove', 'erase', 'disable', 'enable', 'install', 'set', 'change', 'write'} or
            ('launchd' in tokens and recipe_id != 'launchd-service') or
            (recipe['id'].startswith('app-') and tokens & {'and', 'every', 'all', 'recursive', 'recursively'}) or
            (not recipe['id'].startswith('app-') and
             tokens & {'signature', 'signing', 'notarization', 'gatekeeper'})):
        return {**result, "reason": "This recipe cannot satisfy the requested scope or output. Ask for its basic inspection report."}
    tool = recipe["argv"][0]
    details = {"recipe_id": recipe["id"], "title": recipe["title"],
               "sources": recipe["sources"], "notes": recipe["notes"]}
    if which(tool) is None:
        return {**result, **details, "status": "unavailable", "reason": f"{tool} is not available on PATH."}
    if log_filter is not None and recipe_id != 'unified-log-filter':
        return {**result, **details, 'status': 'needs-input', 'reason': 'This operation does not use log-filter flags.'}
    if service_target is not None and recipe_id != 'launchd-service':
        return {**result, **details, 'status': 'needs-input', 'reason': 'This operation does not use --domain or --label.'}
    if path is not None and "path" not in recipe["parameters"]:
        return {**result, **details, "status": "needs-input", "reason": "This operation does not use --path."}
    values = (asdict(log_filter or LogFilter()) if recipe_id == 'unified-log-filter' else
              asdict(service_target or ServiceTarget()) if recipe_id == 'launchd-service' else
              {'path': path})
    missing = [name for name in recipe['parameters'] if values[name] is None or values[name] == '']
    if missing:
        return {**result, **details, "status": "needs-input", "missing": missing,
                "reason": 'Supply ' + ', '.join('--' + name for name in missing) + '. No input is guessed.'}
    if recipe_id == 'unified-log-filter':
        if (not isinstance(values['subsystem'], str) or
                not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,254}', values['subsystem']) or
                type(values['pid']) is not int or values['pid'] <= 0 or
                values['level'] not in ('error', 'default')):
            return {**result, **details, 'status': 'needs-input',
                    'reason': 'Use a subsystem of 1–255 ASCII letters/digits/dots/underscores/hyphens, a positive integer PID, and level error or default.'}
        try:
            bounds = []
            for name in ('start', 'end'):
                value = values[name]
                if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[+-]\d{4}', value):
                    raise ValueError('Invalid timestamp format')
                bounds.append(datetime.strptime(value, '%Y-%m-%d %H:%M:%S%z'))
            if bounds[0] >= bounds[1]:
                raise ValueError('End must follow start')
        except ValueError:
            return {**result, **details, 'status': 'needs-input',
                    'reason': 'Use --start and --end as YYYY-MM-DD HH:MM:SS+HHMM, with end after start.'}
    if recipe_id == 'launchd-service':
        domain = values['domain']
        valid_domain = (domain == 'system' or
                        isinstance(domain, str) and bool(re.fullmatch(r'(?:user|gui)/[0-9]+', domain)))
        if (not valid_domain or not isinstance(values['label'], str) or
                not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,254}', values['label'])):
            return {**result, **details, 'status': 'needs-input',
                    'reason': 'Use domain system, user/<uid> or gui/<uid> with a nonnegative decimal UID, and a 1–255 character ASCII service label.'}
    # Absolute paths cannot accidentally become option flags. shlex.join quotes
    # shell metacharacters; no user-supplied shell fragment is interpolated.
    if path:
        values['path'] = os.path.abspath(os.path.expanduser(path))
    argv = [arg.format_map(values) for arg in recipe['argv']]
    if any("\x00" in arg or "\n" in arg or "\r" in arg for arg in argv):
        return {**result, **details, "status": "needs-input", "reason": "Use a path without NUL or newline characters."}
    return {**result, **details, "status": "suggestion", "reason": "",
            "command": shlex.join(argv), "argv": argv}
