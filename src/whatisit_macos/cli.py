"""Command-line entry point. Output only; no execution or network calls."""

import argparse
import json
import platform
import shutil
import sys
import time

from . import __version__
from .engine import load_recipes, suggest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Look up a documented macOS command. Prototype; never executes suggestions.")
    parser.add_argument("words", nargs="*", help="inspection request in plain English")
    parser.add_argument("--path", help="file path for metadata lookup")
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
    answer = suggest(" ".join(args.words), system=platform.system(), which=shutil.which, path=args.path)
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
    if args.timing:
        print(f"Lookup: {elapsed_ms:.2f} ms", file=sys.stderr)
    return 0 if answer["status"] == "suggestion" else 2
