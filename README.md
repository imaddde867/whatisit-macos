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
PYTHONPATH=src ~/.local/pipx/venvs/whatisit/bin/python tools/eval_fallback.py dev|frozen [model|lint]
```

`eval/dev.jsonl` (61 cases) was used to tune the harness; `eval/frozen.jsonl` (59 cases) was run once at the end. Cases are ChatGPT-authored request → reference pairs with regex accept patterns (frozen patterns also ChatGPT-widened, without seeing model output). Output is deterministic (greedy decoding).

Frozen results (`model` = no checks, `lint` = macOS lint + deletion guard):

| model | harness | correct | wrong | rejected | p50 |
|---|---|---|---|---|---|
| nl2sh-1.5b | model | 6/59 | 45 | 1 | 0.18 s |
| nl2sh-1.5b | lint | 8/59 | 34 | 12 | 0.23 s |
| nl2sh-3b | model | 11/59 | 40 | 1 | 0.33 s |
| nl2sh-3b | lint | 13/59 | 26 | 15 | 0.39 s |

Treat these as a low-power regression signal, not a benchmark: 59 cases, implementer-built harness, strict regexes. 3B beat 1.5B on frozen but lost on dev (15/61 vs 26/61, where 1.5B was tuned), so the model choice is unsettled; 1.5B stays the default. The lint gate never turned a correct answer into a wrong one on either split.

## Known limits

- The 1.5B model does not know many macOS-only commands and sometimes invents flags or paths; only about 1 in 7 independent requests is answered correctly. The lint gate catches missing tools/flags, not wrong semantics (e.g. `pmset cycles`).
- The lint gate is host-specific by design (it reads this Mac's `PATH` and man pages). It can false-positive on real flags the man page omits (`scutil --nwi`, `qlmanage -o`).
- The deletion guard requires every delete target to appear literally in the request; upstream's scanner alone let `rm -rf ~/Library/Caches` and `… | xargs rm -f` through.
- Tried and rejected on dev: prompt rewrites, static few-shot, man-page retrieval, one lint-guided repair re-prompt, top-2 tldr-pages example retrieval (12/61 vs 26/61 without it: the 1.5B model copies the examples), a 4B model, and the `qcoder-nl2sh` GGUF (same score as default).
- Next lever: a macOS-specific fine-tune. [Zero-step toolchain feasibility passed](docs/finetune-feasibility.md) with 0/61 dev label flips; a first LoRA on 1,075 teacher rows did not beat the default on dev + everyday (71 and 68 of 141 across two seeds, against 68 for the default), so it was not scored on frozen or held-out: [stage-1 result](docs/stage1-training-result.md).

## Tests

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```
