# whatisit-macos

A lightweight macOS command assistant focused on accuracy and documented commands.

**Status: initial prototype.** Three fixed inspection recipes work today. Natural-language routing uses simple keywords; general command generation, local-man-page retrieval, and model integration are future work. This is a fresh implementation inspired by [whatisit-nl2sh](https://github.com/ThorOdinson246/whatisit-nl2sh), not a fork or a drop-in replacement.

The goal is to make forgotten terminal commands easy to recover without guessing Linux commands on macOS or inventing flags. Start with a small documented catalog, measure its limits, then decide whether a small local model improves coverage enough to justify its memory and latency.

## Try it

Requires macOS and Python 3.11+. From your existing clone:

```bash
git pull --ff-only
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

whatisit-macos 'show battery cycle count'
whatisit-macos 'show assertions preventing sleep'
whatisit-macos 'show Spotlight metadata for a file' --path "$HOME/Downloads/example.pdf"
whatisit-macos --list
```

Use an actual file path for the metadata example. Output includes the command, brief caveats, and sources. Nothing is executed; copy and review the command before running it yourself.

| Starter task | Command template | Behavior |
| --- | --- | --- |
| Battery cycle count | `system_profiler SPPowerDataType` | Prints the power report; read Cycle Count in Battery Information. |
| Spotlight file metadata | `mdls PATH` | Requires explicit `--path`; quotes the absolute path. |
| Sleep assertions | `pmset -g assertions` | Shows current assertions and owners; not every possible cause of a sleep problem. |

```bash
whatisit-macos --json 'show battery cycle count'
whatisit-macos --timing 'show assertions preventing sleep'
```

`--timing` measures lookup work inside Python, excluding interpreter startup and the suggested command's runtime. Exit code `0` means a suggestion was returned (or a listing/help flag succeeded); `2` means input is missing, ambiguous, unsupported, or a required tool is unavailable. Non-macOS hosts can inspect the catalog and run tests, but do not receive command suggestions.

## Current limits

- No model, model download, background server, network calls, or third-party runtime dependencies.
- Keyword matching can miss paraphrases and qualifiers. A source-backed template does not prove that the selected template satisfies the whole request.
- Unknown requests return `unsupported`; missing file paths return `needs-input` rather than a runnable placeholder.
- Only tool availability on PATH is checked. Command behavior has not yet been validated across macOS releases or on the target MacBook.
- The original tracing, launchd, unified-log, and notarization queries are tracked as unsupported seed cases, not claimed as solved.

## Development

```bash
python -m unittest discover -s tests -v
```

Tests cover routing, platform/tool checks, quoting, incomplete inputs, CLI behavior, and the seed cases in `eval/cases.jsonl`. CI runs the same suite on Ubuntu and macOS and checks that the recipe data ships in an installed wheel. These tests do not execute the suggested commands or establish real-world macOS correctness.

- [Research and diagnosis](docs/RESEARCH.md): observations, upstream evidence, and hypotheses.
- [Design](docs/DESIGN.md): implemented flow and proposed retrieval/model flow.
- [Roadmap](docs/ROADMAP.md): concrete next steps and evaluation gates.
- [Evaluation](eval/README.md): separate command correctness from useful coverage and resource cost.
- [Contributing](CONTRIBUTING.md): adding a recipe or a regression case.

## License

MIT for this repository. No upstream code, model weights, training datasets, or copied manual pages are included. See [LICENSE](LICENSE). Any future imported material needs its own license and attribution review.
