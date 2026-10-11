"""Suggest a macOS shell command with a local model; suggestions are never executed."""

import argparse
import json
import platform
import sys
import time

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Suggest a macOS shell command; never executes suggestions.")
    parser.add_argument("words", nargs="*", help="what you want to do, in plain English")
    parser.add_argument("--path", help="explicit file or directory the request refers to")
    parser.add_argument("--json", action="store_true", help="print structured output")
    parser.add_argument("-t", "--timing", action="store_true", help="report latency")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    if not args.words:
        parser.print_help()
        return 2
    start = time.perf_counter()
    if platform.system() != 'Darwin':
        answer = {'status': 'unsupported', 'command': None, 'reason': 'This tool only suggests commands on macOS.',
                  'notes': [], 'sources': []}
    else:
        from .local_recovery import suggest_local
        answer = suggest_local(' '.join(args.words), path=args.path)
    elapsed_ms = (time.perf_counter() - start) * 1000
    if args.json:
        print(json.dumps(answer, indent=2))
    elif answer["command"]:
        print(answer["command"])
        for note in answer["notes"]:
            print(f"Note: {note}")
    else:
        print(f"{answer['status']}: {answer['reason']}", file=sys.stderr)
    if args.timing:
        print(f"Latency: {elapsed_ms:.0f} ms", file=sys.stderr)
    return 0 if answer["status"] == "suggestion" else 2
