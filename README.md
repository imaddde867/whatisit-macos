# whatisit-macos

A lightweight macOS command assistant focused on accuracy and documented commands.

**Status: experimental prototype.** Seven fixed inspection recipes, local documentation retrieval, and an optional local MLX selector work today. Default routing uses keywords. Model output selects an operation; validated templates render commands from explicit inputs. This is a fresh implementation inspired by [whatisit-nl2sh](https://github.com/ThorOdinson246/whatisit-nl2sh), not a fork or a drop-in replacement.

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
whatisit-macos 'verify app signature' --path /Applications/Example.app
whatisit-macos 'assess Gatekeeper policy for an app' --path /Applications/Example.app
whatisit-macos 'validate an app stapled ticket' --path /Applications/Example.app
whatisit-macos 'filter unified logs' --subsystem com.example.whatisit --pid 123 \
  --level error --start '2026-10-09 10:00:00+0300' --end '2026-10-09 10:01:00+0300'
whatisit-macos --list
```

Use an actual file path for the metadata example. For log filtering, supply the intended subsystem, PID and interval; the example uses synthetic values. All five log inputs are required. Severity is exactly `error` or `default`; timestamps require a UTC offset and end must follow start. Subsystems are limited to 1–255 ASCII letters, digits, dots, underscores and hyphens, beginning with a letter or digit. No values are inferred from request text. Output includes the command, brief caveats, and sources. Nothing is executed; copy and review the command before running it yourself.

| Inspection task | Command template | Behavior |
| --- | --- | --- |
| Battery cycle count | `system_profiler SPPowerDataType` | Prints the power report; read Cycle Count in Battery Information. |
| Spotlight file metadata | `mdls PATH` | Requires explicit `--path`; quotes the absolute path. |
| Sleep assertions | `pmset -g assertions` | Shows current assertions and owners; not every possible cause of a sleep problem. |
| App signature | `codesign --verify --deep --strict --verbose=2 PATH` | Signature integrity; requires an explicit app path. |
| App Gatekeeper policy | `spctl --assess --type execute --verbose=2 PATH` | Local policy at check time; separate from signature and ticket validation. |
| App stapled ticket | `/Library/Developer/CommandLineTools/usr/bin/stapler validate -q PATH` | Requires Command Line Tools; may contact Apple. Missing ticket does not prove never notarized. |

```bash
whatisit-macos --json 'show battery cycle count'
whatisit-macos --timing 'show assertions preventing sleep'
```

`--timing` measures lookup work inside Python, including optional documentation retrieval, excluding interpreter startup and the suggested command's runtime. Exit code `0` means a suggestion was returned (or a listing/help flag succeeded); `2` means input is missing, ambiguous, unsupported, or a required tool is unavailable. Non-macOS hosts can inspect the catalog and run tests, but do not receive command suggestions.

Log filtering prints stored events matching subsystem, PID, severity and time together, using compact text. Empty output does not establish absence of events. PID reuse, retention, redaction and access limit what a bounded query can establish. Live monitoring, process-name selection, archives, message filters and info/debug persistence remain unsupported. Existing device evidence covers controlled public events; see [the log-filter slice](docs/LOG_FILTER.md).

## Local documentation

Build an index explicitly on the Mac; this reads 12 selected system manuals and the curated recipe catalog. It runs only `sw_vers`, `man` and `col`, never the commands being documented. Apple manuals and catalog entries are bound to executables in `/usr/bin`, `/usr/sbin`, `/bin` and `/sbin`, ignoring PATH shadows. This provenance does not certify a PATH-selected executable when you later run a command. Rebuild older indexes using a new filename. Requires Python's SQLite with FTS5 support. The installed wheel includes `whatisit-macos-build-docs`; it works outside the clone. Choose a writable local index directory:

```bash
mkdir -p .cache eval/results
whatisit-macos-build-docs .cache/manuals.sqlite3 > eval/results/inventory.json
PYTHONPATH=src python3 -m whatisit_macos --docs-index .cache/manuals.sqlite3 --json 'stream unified logs live'
```

The second command returns `unsupported` with documentation evidence and exit code `2`. Evidence includes the source path, tool path, capture time, macOS version, document hash and chunk number. Retrieval does not approve a command or change recipe routing. Missing/unreadable indexes produce a visible documentation error while preserving the original suggestion status. Without `--docs-index`, no index is read. Choose a new filename to rebuild after an OS update; existing captures are never overwritten. Keep indexes in ignored `.cache/`, not in Git.

```bash
PYTHONPATH=src python3 tools/evaluate.py --docs-index .cache/manuals.sqlite3 > eval/results/evaluation.json
PYTHONPATH=src python3 -m tools.benchmark --docs-index .cache/manuals.sqlite3 > eval/results/benchmark.json
```

The evaluation reads 40 authored tasks with a frozen dev/held-out split. The benchmark starts only lookup CLI processes. Neither executes suggested commands. See [target Mac measurements and known gaps](docs/MEASUREMENTS.md) for results and methodology.

## Current limits

- Default lookup has no model or third-party runtime dependencies. Optional MLX loading uses an existing local directory, runs on demand, unloads explicitly and exits with the CLI; no background server is started. See [the experiment and pilot measurements](docs/EXPERIMENT.md) for setup, commands and limits.
- Keyword matching can miss paraphrases and qualifiers. Known unsupported output, traversal and monitoring qualifiers now abstain. A source-backed template does not prove that the selected template satisfies the whole request.
- Unknown and combined app-audit requests return `unsupported`; missing file/app paths return `needs-input` rather than a runnable placeholder.
- Only tool availability on PATH is checked. Manuals and lookup resource cost have been inspected on the target Mac; suggested commands still require manual device validation. Lexical retrieval can return irrelevant or partial passages, including mutation documentation. Capture provenance does not prove compatibility with the current OS.
- The original tracing, launchd and combined app-audit queries remain unsupported. Bounded unified-log requests now ask for explicit filters; broader log requests abstain. Signature, local policy and stapled ticket checks are separate supported operations; they do not establish a complete app safety diagnosis.

## Development

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Tests cover routing, platform/tool checks, quoting, incomplete inputs, CLI behavior, retrieval provenance and failures, evaluation reporting, and the seed cases in `eval/cases.jsonl`. CI runs the same suite on Ubuntu and macOS and checks that the recipe data ships in an installed wheel. These tests do not execute the suggested commands or establish real-world macOS correctness.

- [Research and diagnosis](docs/RESEARCH.md): observations, upstream evidence, and hypotheses.
- [Design](docs/DESIGN.md): implemented flow and proposed retrieval/model flow.
- [Roadmap](docs/ROADMAP.md): concrete next steps and evaluation gates.
- [Evaluation](eval/README.md): separate command correctness from useful coverage and resource cost.
- [Contributing](CONTRIBUTING.md): adding a recipe or a regression case.

## License

MIT for this repository. No upstream code, model weights, training datasets, or copied manual pages are included. See [LICENSE](LICENSE). Any future imported material needs its own license and attribution review.

Wheel isolation checks and per-task manual validation commands are recorded in [VALIDATION.md](docs/VALIDATION.md).
