"""Select fixed templates; never execute the suggested command."""

import json
import os
import re
import shlex
from importlib.resources import files
from typing import Callable


def load_recipes() -> list[dict]:
    return json.loads(files("whatisit_macos").joinpath("recipes.json").read_text())


def suggest(
    request: str,
    *,
    system: str,
    which: Callable[[str], str | None],
    path: str | None = None,
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
        status = 'unsupported' if any(r['id'].startswith('app-') for r in matches) else 'ambiguous'
        return {**result, 'status': status, "reason": "Ask for one supported task at a time."}
    recipe = matches[0]
    return render(recipe['id'], request=request, system=system, which=which, path=path)


def render(recipe_id: str, *, request: str, system: str,
           which: Callable[[str], str | None], path: str | None = None) -> dict:
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
    }
    # shortcut: lexical qualifiers are conservative; use intent parsing before expanding catalog scope.
    if (re.search(r"\ball\s+(?:files|documents)\b", request.casefold()) or
            any(r['id'] != recipe_id and all(tokens.intersection(g) for g in r['match_groups'])
                for r in load_recipes()) or
            tokens & unsupported[recipe["id"]] or
            tokens & {'then', 'json', 'xml', 'launchd', 'logs', 'trace', 'tracing',
                      'delete', 'remove', 'erase', 'disable', 'enable', 'install', 'set', 'change', 'write'} or
            (recipe['id'].startswith('app-') and tokens & {'and', 'every', 'all', 'recursive', 'recursively'}) or
            (not recipe['id'].startswith('app-') and
             tokens & {'signature', 'signing', 'notarization', 'gatekeeper'})):
        return {**result, "reason": "This recipe cannot satisfy the requested scope or output. Ask for its basic inspection report."}
    tool = recipe["argv"][0]
    details = {"recipe_id": recipe["id"], "title": recipe["title"],
               "sources": recipe["sources"], "notes": recipe["notes"]}
    if which(tool) is None:
        return {**result, **details, "status": "unavailable", "reason": f"{tool} is not available on PATH."}
    missing = [name for name in recipe["parameters"] if name == "path" and not path]
    if missing:
        return {**result, **details, "status": "needs-input", "missing": missing,
                "reason": "Supply the path with --path. No path is guessed."}
    # Absolute paths cannot accidentally become option flags. shlex.join quotes
    # shell metacharacters; no user-supplied shell fragment is interpolated.
    if path is not None and "path" not in recipe["parameters"]:
        return {**result, **details, "status": "needs-input", "reason": "This operation does not use --path."}
    value = os.path.abspath(os.path.expanduser(path)) if path else ""
    argv = [value if arg == "{path}" else arg for arg in recipe["argv"]]
    if any("\x00" in arg or "\n" in arg or "\r" in arg for arg in argv):
        return {**result, **details, "status": "needs-input", "reason": "Use a path without NUL or newline characters."}
    return {**result, **details, "status": "suggestion", "reason": "",
            "command": shlex.join(argv), "argv": argv}
