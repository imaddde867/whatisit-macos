# whatisit-macos

Suggest a macOS shell command from plain English. Inspired by [whatisit-nl2sh](https://github.com/ThorOdinson246/whatisit-nl2sh); a fresh implementation, not a fork. **Experimental.** Suggestions are never executed — review them before running.

## How it works

1. **Local model.** Requests go to upstream [`whatisit`](https://github.com/ThorOdinson246/whatisit-nl2sh) (`nl2sh-1.5b`, llama-server, 60 s idle unload) in an isolated subprocess with remote config stripped. There is no catalog of hardcoded commands.
2. **macOS lint gate.** The generated command is checked against *this* Mac: every tool must be on `PATH`, every flag must appear in its man page, `sysctl` keys must exist, system paths must exist, and BSD `sed -i` needs a suffix. Upstream's safety scanner also rejects DANGER findings and notes CAUTION ones. A finding yields `unsupported: <reason>` (exit code 2), never a guess.

## Use

```sh
pip install -e .                  # needs upstream whatisit installed with its model + llama-server
whatisit-macos find files larger than 100MB in my home folder
whatisit-macos --path ~/Downloads show the 5 largest files
whatisit-macos --json -t show listening tcp ports
```

Nothing is downloaded automatically; set up upstream `whatisit` first. Set `WHATISIT_MODEL` to try another GGUF.

## Measure

```sh
PYTHONPATH=src ~/.local/pipx/venvs/whatisit/bin/python tools/eval_fallback.py
```

Scores fixed request→command-pattern cases as pass / rejected / wrong with p50 latency. The accepted-answer regexes are loose and written by the implementer; treat the result as a regression signal, not a benchmark. Run it twice; output is deterministic (greedy decoding).

## Known limits

- The 1.5B model does not know many macOS-only commands and sometimes invents flags or paths. The lint gate catches missing tools/flags, not wrong semantics (e.g. `pmset cycles`, `diskutil eject /dev/disk4`).
- The lint gate is host-specific by design (it reads this Mac's `PATH` and man pages) and can false-positive on unusual flag syntax.
- Tried and rejected on dev: prompt rewrites, static few-shot, man-page retrieval, a 4B model, one lint-guided repair re-prompt, and top-2 tldr-pages example retrieval (12/61 vs 26/61 without it: the 1.5B model copies or mimics the examples). The `qcoder-nl2sh` GGUF scored the same as the default model.
- Dev (61 cases, `eval/dev.jsonl`): model only 23 correct / 32 wrong; model + lint + deletion guard 26 correct / 23 wrong, 10 rejected. Most remaining failures are model knowledge gaps (invented flags, wrong tool), not harness gaps.

## Tests

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```
