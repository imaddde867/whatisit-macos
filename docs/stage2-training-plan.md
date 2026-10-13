# Stage-2 training reassessment (2026-10-13)

Proposal after the dataset repair, not a training result. No stage-2 optimizer run or final evaluation has been started. Keep the default model until a candidate clears the existing decision gate.

## What stage 1 tells us

- The selected 1e-5 arm scored 71/141 and 68/141 across seeds 42 and 43 versus 68/141 for the default. Accepted-wrong increased from 40 to 42 and 43. A larger learning rate scored 75 but accepted 46 wrong answers. More answers alone is not success.
- Validation loss fell from 2.911 to 0.376 for seed 42 and 0.379 for seed 43. This measures teacher-target likelihood, not command correctness. These numbers do not establish that more epochs or a larger adapter would help.
- The saved 54-row validation split has 42 command and 12 abstention rows. Only one validation command appears verbatim in training; three validation requests have training-request word Jaccard >= 0.5, none >= 0.7. Literal duplication is not a demonstrated explanation for the loss/quality gap. Semantic/template similarity remains unmeasured.
- The old corpus has no explicit `path` inputs. Its prompts match serving with `path=None`; the missing `Explicit inputs:` suffix is a coverage gap, not a formatting defect in every row.
- The old 23% abstention share follows filtering and is not an observed deployment prior. Do not downsample correct abstentions merely to match evaluation-set percentages.

Evidence: [stage-1 results](stage1-training-result.md), [saved training reports](stage1-training-reports/), `tools/train_distill_cuda.py`, and `src/whatisit_macos/local_recovery_worker.py`.

## Before another optimizer run

1. Use `stage2-v2`, which supersedes the published `stage2-v1`: v1 kept three abstention rows whose family siblings hit the leakage gate (one family against held-out) and labeled 12 command clarifications as abstentions. Freeze the repaired dataset, edit/exclusion manifest, source hashes and quality report. Treat request rewrites as new model-reviewed derivatives, not unchanged teacher evidence. Retain the original dataset for reproducing stage 1.
2. Check corrected requests against the existing leakage gate. Preserve frozen/held-out only for leakage checks and the final decision; do not use their examples to choose repairs, proportions or hyperparameters.
3. Verify every training prompt against the actual serving request, including explicit-path variants, and run the real tokenizer's prefix/masking/EOS and 512-token checks. Do not substitute a mocked tokenizer for this preflight. Done locally on 2026-10-13 for `stage2-v2`: all 1,091 rows pass `chat_tokens` with the pinned Qwen2.5-Coder-1.5B-Instruct tokenizer (revision `2e1fd397…`, transformers 4.57.1); maximum 243 tokens. The trainer repeats this check on the CUDA host before any update.
4. Use the trainer's deterministic grouped split. It joins rows that share a `source_id`, an exact command, or a request with word Jaccard >= 0.7, and records validation IDs and source-group counts in the training report. On `stage2-v2`, `--val-fraction 0.05` selects 54/1,091 rows (42 command, 12 abstain). No validation command appears in training; one validation request is template-similar (Jaccard >= 0.7 on request text alone) to a training request with a different explicit path and command. Check the recorded split and hash before starting either seed.
5. Review command semantics on a reproducible sample spanning categories, changed prompts, explicit inputs and abstentions. Report uncertain cases and review method. Lint and teacher agreement are filters, not a proof of semantic correctness; do not execute destructive commands to verify them.

Grouped splitting keeps related observations together; this is the relevant principle from [scikit-learn's grouped validation documentation](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data). No scikit-learn dependency is needed for this small dataset.

## First experiment: isolate the data repair

Use the original NL2SH source weights and existing conversion path. Keep rank 8, alpha 160, last 16 layers, current seven target modules, AdamW at 1e-5, batch 1, and one pass through the corrected training partition. On `stage2-v2` (train SHA-256 `91431de67f15232d3ec83361bd8fe6b176e10d21617b4611089de8db238081aa`) the split has 1,037 training rows, so run exactly 1,037 updates for each seed, matching stage 1's single pass (1,021 steps on 1,021 rows). From the repository root on the approved CUDA host:

```sh
PYTHONPATH=src python3 tools/train_distill_cuda.py \
  /path/to/nl2sh-1.5b-Q4_K_M.gguf /path/to/pinned-base-metadata \
  data/distill/stage2-v2/train.jsonl /path/to/stage2-seed42 \
  --steps 1037 --lr 1e-5 --seed 42 --val-fraction 0.05

PYTHONPATH=src python3 tools/train_distill_cuda.py \
  /path/to/nl2sh-1.5b-Q4_K_M.gguf /path/to/pinned-base-metadata \
  data/distill/stage2-v2/train.jsonl /path/to/stage2-seed43 \
  --steps 1037 --lr 1e-5 --seed 43 --val-fraction 0.05
```

Use separate new output directories. Confirm both reports contain the same `val_ids`, `val_source_ids`, validation count and data hash. Derive the step count again if the data or split changes. Record all defaults, including AdamW weight decay, and dataset/split/source hashes.

Keep assistant-only supervision and empty-answer end-of-turn supervision. Do not change the learning rate, rank, adapter scale, optimizer, weighting and data in the same first comparison. Standard LoRA scales the adapter by alpha/r (20 here); that is not a proof that learning rate times 20 is equivalent to another optimizer configuration. See [PEFT's LoRA reference](https://huggingface.co/docs/peft/v0.21.0/package_reference/lora).

Export each merged f16 GGUF to Q4_K_M with the pinned llama.cpp build, then compare both against the default on dev and everyday using the same Mac and harness. Report paired flips, answerable correctness, accepted-wrong, correct abstentions, abstain-missed, and separate empty generation from lint/safety rejection. The current evaluation output merges those rejection causes; extend its saved diagnostics before relying on that distinction. Re-run latency, RSS and produced-model prompt audits. Use the existing [fine-tune feasibility runbook](finetune-feasibility.md) for pinned conversion, prompt audit and evaluation commands.

Proposed screening rule, to pin before results: both seeds must improve pooled correct count over the default, neither dev nor everyday may regress, and neither accepted-wrong nor abstain-missed may increase. If both pass, nominate seed 42 in advance rather than picking the better seed. If either fails, do not run the final gate. This is a proposed rule for stage 2, not a retroactive replacement for stage 1's rule.

## If data repair is insufficient

Inspect development-only error categories before choosing one further intervention:

- If training loss improves but unseen-intent command accuracy does not, collect and verify more distinct macOS intents and natural underspecified requests. Do not generate paraphrases solely to increase the row count.
- If seed variation remains large with otherwise useful improvements, test gradient accumulation as a separate bounded experiment. Define both examples seen and optimizer updates; changing batch size changes their relationship.
- If the merged f16 model improves but Q4_K_M does not, measure quantization loss with paired outputs on development data before changing training capacity. Stage 1's zero-update parity does not prove parity after updates.
- Consider checkpoint selection or more epochs only after a disjoint semantic validation set exists. Pin candidate checkpoints and selection criteria first; validation loss alone is insufficient evidence.

No learning-rate sweep, new base model, new framework, or larger adapter is justified by the present evidence.

## Final decision

Stage 1 did not score any candidate on frozen or held-out. Baseline scores have already been seen, and development decisions have accumulated, so describe the full history honestly. Preserve issue #11's rule: one final nominated candidate, pooled frozen + held-out paired sign test, no abstention regression, no development-set regression, and the recorded latency/memory budgets. Pin the stage-2 candidate-selection rule and treatment of any later attempts before scoring; failed final-gate results must not feed another attempt on the same gate as if it were fresh.
