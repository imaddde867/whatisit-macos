# State (2026-10-24)

The single source of current truth. Older docs under `docs/` are records of finished experiments; where they disagree with this file, this file wins.

## Goal

English request -> one copy-paste macOS command, from a small local model (1.5B, Q4_K_M GGUF) plus the lint/deletion-guard harness in `src/`. Large models are offline teachers only. No hardcoded command catalog. Target: >= 127/141 (90%) semantically correct on dev + everyday.

## Where things stand

- Shipped default scores 58/141 under the semantic audit (`docs/eval-audit/`); the best runtime LoRA adapter scores 81/141. The regex scorer is unreliable (it flips 148/883 commands); use the audited numbers.
- Teacher is 130/141 per sample. The "88 ceiling" in `docs/teacher-ceiling.md` was an artifact of exact-string voting, not teacher quality.
- No verified training dataset exists yet. `data/distill/stage2-v3` is the last complete set and an input to v4.
- v4 pass 1 (PR #38, branch `campaign/v4-r2-20261020`) is BLOCKED: population drift, unverifiable provenance, human gate unmet.
- The v4 rebuild is in progress on `campaign/v4-verified-rebuild-20261022`, untracked under `data/distill/stage2-v4/campaign-20261022/`: pool regenerated, pass 1 at 4/23 batches, no pass 2, no build.
- `eval/frozen.jsonl` and `eval/heldout.jsonl` are one-shot release-gate sets. Never tune on them or open them casually.

## Canonical v4 build path

1. `tools/build_v4_pool.py`: blind pool, keymap and controls from corpus, teacher samples, v3 and `docs/eval-audit`.
2. Pass-1 judging against `data/distill/stage2-v4/LABEL.md`.
3. `tools/make_v4_confirm.py`: 20% confirm sample, then pass-2 judging.
4. `tools/build_verified_dataset.py <keymap> <verdicts> <confirm> <confirm-verdicts> <out>` (`--controls` lands with the campaign branch, commit `aff43c0`).

The pool hash-binds `data/corpus`, `data/teacher`, `data/distill/stage2-v3`, the quarantine id files and the code in `src/`, `tools/build_distill_dataset.py` and `tools/repair_distill_dataset.py`. Do not edit those mid-campaign.

## Tests

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```

14 tests skip locally: 13 need the upstream `whatisit` safety rules and 1 needs CUDA assets.

## Next step

Finish v4 rebuild pass 1 (b04-b22), then pass 2, the build, and the human review gate (#36). Train only after that (#15), then the one-shot release gate (#11).

## Archive

Removed experiment records (Learning64 diagnostic) live at `1d5096b` on main (local tag `archive/pre-cleanup-20261024`); restore with `git checkout 1d5096b -- <path>`.
