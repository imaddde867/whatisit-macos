# Stage-2 fine-tune screening result (2026-10-13)

Screening passed for both seeds. The final frozen + held-out gate has not been run: it consumes the held-out set and is pending an explicit decision. The default model stays until the final gate passes.

Setup is the stage-1 recipe on the repaired data: `data/distill/stage2-v2/train.jsonl` (SHA-256 `91431de67f15232d3ec83361bd8fe6b176e10d21617b4611089de8db238081aa`, 1,091 rows). Otherwise unchanged: rank-8 LoRA, alpha 160 (scale 20), last 16 layers, seven target modules, AdamW lr 1e-5, batch 1, one epoch = 1,037 steps on the 1,037-row training partition. The 54-row validation split (42 command, 12 abstain) is grouped by source_id, exact command and request Jaccard >= 0.7, with identical val_ids for both seeds. Source GGUF sha `6f8a17a1…`; tokenizer Qwen2.5-Coder-1.5B-Instruct rev `2e1fd397`. Host RTX 5090, CUDA 13.0, torch 2.14.1, transformers 5.19.0, peft 0.21.0. Training takes about 38 s (about 65 s wall) per seed, peak allocated 6.07 GB. Quantized to Q4_K_M with llama.cpp b11565 `llama-quantize`. Per-case labels are in [`stage2-arm-labels.json`](stage2-arm-labels.json) and training reports in [`stage2-training-reports/`](stage2-training-reports/).

Validation loss falls from 3.004 to 0.6145 (seed 42) and 0.6125 (seed 43). This is not comparable to stage 1's 0.376, because the stage-2 validation split is grouped by intent. It measures teacher-target likelihood, not command correctness.

## Scores (pass + abstain-ok, lint + guard, dev 61 + everyday 80)

| arm | dev | everyday | pooled | paired vs default | accepted wrong | rejected | abstain-missed |
|---|---|---|---|---|---|---|---|
| default | 26 | 42 | 68 | n/a | 40 | 29 | 4 |
| stage2 1e-5, seed 42 | 27 | 43 | 70 | +2 / −0 | 38 | 30 | 3 |
| stage2 1e-5, seed 43 | 27 | 43 | 70 | +2 / −0 | 38 | 30 | 3 |

- Both seeds produce identical per-case labels on all 141 cases. Changes vs default: m112 abstain-missed → abstain-ok, e006 wrong → pass, m094 wrong → rejected.
- The default run reproduces the saved stage-1 default labels exactly.
- Screening rule, pinned in the plan before results: both seeds improve pooled, neither dev nor everyday regresses, neither accepted-wrong nor abstain-missed increases. Both seeds pass; seed 42 was nominated in advance.
- The gain is small (+2 of 141, no losses). The final paired sign test on frozen + held-out decides.
- "Rejected" still merges empty answers with lint rejections.

## Harness note

`maclint` decides "not installed on macOS" by looking tools up on PATH. A first evaluation run inherited a PATH containing `/opt/homebrew/bin`, so ImageMagick commands (`identify`, `convert`) from the default model were accepted as commands and labeled wrong instead of rejected (3 default cases: m074, m076, e056). The correct counts were unchanged. All reported numbers use `PATH=/usr/bin:/bin:/usr/sbin:/sbin`, which reproduces stage 1's default labels. Future evaluations must pin PATH.

## Artifacts (SHA-256 of the Q4_K_M GGUF)

| arm | SHA-256 |
|---|---|
| stage2 1e-5, seed 42 | `673bdd9c…` |
| stage2 1e-5, seed 43 | `ad14cd86…` |

No model was published.

## Not done

- Final frozen + held-out gate, pending an explicit decision.
- Latency/RSS and produced-model prompt audits per [`finetune-feasibility.md`](finetune-feasibility.md).
- Pin how later attempts are treated if the gate fails.
