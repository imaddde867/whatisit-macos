# whatisit-macos

Suggest a macOS shell command from plain English. Inspired by [whatisit-nl2sh](https://github.com/ThorOdinson246/whatisit-nl2sh); a fresh implementation, not a fork. **Experimental.** Suggestions are never executed — review them before running.

## How it works

1. **Catalog (instant, no model).** Six fixed-argv recipes for things small models get wrong on macOS: battery cycles, Spotlight metadata, sleep assertions, and app signature / Gatekeeper / notarization-ticket checks.
2. **Local model fallback (optional).** Anything else goes to upstream [`whatisit`](https://github.com/ThorOdinson246/whatisit-nl2sh) (`nl2sh-1.5b`, llama-server, 60 s idle unload) in an isolated subprocess with remote config stripped.
3. **macOS lint gate.** Generated commands are rejected if a tool isn't installed or a flag isn't in the local man page (`free`, `nproc`, `du --max-depth`, `stat -c`, `sed -i` without a suffix, …). Upstream's safety scanner also rejects DANGER findings and notes CAUTION ones.

A rejected or failed generation prints `unsupported: <reason>`, exit code 2.

## Use

```sh
pip install -e '.[local]'         # or plain `pip install -e .` for catalog only
whatisit-macos show sleep assertions
whatisit-macos --path /Applications/Foo.app verify app signature
whatisit-macos find files larger than 100MB in my home folder   # fallback
whatisit-macos --catalog-only --json show battery cycles
whatisit-macos --list
```

The fallback needs upstream's model and `llama-server` already installed (`whatisit` setup); nothing is downloaded automatically.

## Measure

```sh
PYTHONPATH=src ~/.local/pipx/venvs/whatisit/bin/python tools/eval_fallback.py
```

Scores 44 fixed requests (24 development, 20 held-out) as pass / rejected / wrong with p50 latency. The accepted-answer regexes are loose and written by the implementer; treat the result as a regression signal, not a benchmark. Last run: 28/44 pass, 6 rejected, 10 wrong, p50 0.5 s warm.

## Known limits

- The 1.5B model does not know many macOS-only commands and sometimes invents flags or paths. The lint gate catches missing tools/flags, not wrong semantics (e.g. `pmset cycles`, `diskutil eject /dev/disk4`).
- The lint gate is host-specific by design (it reads this Mac's `PATH` and man pages) and can false-positive on unusual flag syntax.
- Prompt tuning, few-shot examples, manual-page retrieval and a 4B model were tried and did not beat the current prompt plus lint.

## Tests

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```
