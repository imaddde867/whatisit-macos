"""Command lookup and optional local model selection; task commands stay manual."""

import argparse
import json
import platform
import shutil
import sys
import time
import sqlite3
from pathlib import Path

from . import __version__
from .engine import LogFilter, ServiceTarget, load_recipes, suggest
from .retrieval import search


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Look up a documented macOS command. Prototype; never executes suggestions.")
    parser.add_argument("words", nargs="*", help="inspection request in plain English")
    parser.add_argument("--path", help="explicit file or app bundle path")
    parser.add_argument('--subsystem', help='exact unified-log subsystem (ASCII identifier)')
    parser.add_argument('--pid', type=int, help='explicit positive process ID for log filtering')
    parser.add_argument('--level', help='exact log severity: error or default')
    parser.add_argument('--start', help='log interval start: YYYY-MM-DD HH:MM:SS+HHMM')
    parser.add_argument('--end', help='log interval end: YYYY-MM-DD HH:MM:SS+HHMM')
    parser.add_argument('--domain', help='explicit launchd service domain: system, user/<uid> or gui/<uid>')
    parser.add_argument('--label', help='explicit launchd service label')
    parser.add_argument("--docs-index", type=Path, help="search an explicitly captured local manual index")
    parser.add_argument('--model', type=Path, help='optional local MLX model directory; requires --docs-index')
    parser.add_argument("--json", action="store_true", help="print structured output")
    parser.add_argument("--list", action="store_true", help="list the starter catalog")
    parser.add_argument("-t", "--timing", action="store_true", help="report lookup latency")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    if args.list:
        recipes = load_recipes()
        if args.json:
            print(json.dumps(recipes, indent=2))
        else:
            for recipe in recipes:
                print(f"{recipe['id']}: {recipe['title']}")
        return 0
    if not args.words:
        parser.print_help()
        return 2
    start = time.perf_counter()
    request = ' '.join(args.words)
    log_filter = (LogFilter(args.subsystem, args.pid, args.level, args.start, args.end)
                  if any(value is not None for value in (args.subsystem, args.pid, args.level, args.start, args.end))
                  else None)
    service_target = (ServiceTarget(args.domain, args.label)
                      if args.domain is not None or args.label is not None else None)
    if args.model:
        from .local_model import LocalModel, suggest_with_model
        if not args.docs_index:
            answer = {'status': 'unsupported', 'command': None,
                      'reason': 'Model selection requires an explicit --docs-index documentation capture.'}
        else:
            model = LocalModel(args.model)
            try:
                answer = suggest_with_model(request, index=args.docs_index, select=model.select,
                                            system=platform.system(), which=shutil.which, path=args.path,
                                            log_filter=log_filter, service_target=service_target)
                answer['model_load_ms'] = model.load_ms
            finally:
                model.close()
    else:
        answer = suggest(request, system=platform.system(), which=shutil.which, path=args.path,
                         log_filter=log_filter, service_target=service_target)
    if args.docs_index and not args.model:
        try:
            answer["documentation"] = search(args.docs_index, " ".join(args.words))
        except (OSError, sqlite3.Error, ValueError) as error:
            answer["documentation"] = []
            answer["documentation_error"] = str(error)
    elapsed_ms = (time.perf_counter() - start) * 1000
    if args.json:
        print(json.dumps(answer, indent=2))
    elif answer["command"]:
        print(answer["command"])
        for note in answer["notes"]:
            print(f"Note: {note}")
        print("Sources: " + "; ".join(answer["sources"]))
    else:
        print(f"{answer['status']}: {answer['reason']}", file=sys.stderr)
    if not args.json and args.docs_index:
        print("Documentation evidence only; review relevance, capture date and macOS version.")
        for hit in answer.get('documentation', []):
            print(f"{hit['tool']}: {hit['source']} (macOS {hit['macos_version']}, {hit['captured_at']})")
            print(hit["text"])
        if answer.get("documentation_error"):
            print("Documentation error: " + answer["documentation_error"], file=sys.stderr)
    if args.timing:
        print(f"Lookup: {elapsed_ms:.2f} ms", file=sys.stderr)
    return 0 if answer["status"] == "suggestion" else 2
