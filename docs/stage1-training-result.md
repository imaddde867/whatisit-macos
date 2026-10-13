# Stage-1 fine-tune result (2026-10-13)

Negative. The LoRA trained on the 1,075 Roihu teacher rows did not beat the default on dev + everyday, so the frozen and held-out sets were not scored.

Setup is the one pinned in [#15](https://github.com/imaddde867/whatisit-macos/issues/15): rank-8 LoRA at scale 20 on the last 16 layers, batch 1, AdamW, one epoch of a 1,021-row training split (5% stratified hold-out, 54 rows), llama.cpp b11565 Q4_K_M. Training takes about 40 s per arm on the RTX 5090. Per-case labels and training reports are in [`stage1-arm-labels.json`](stage1-arm-labels.json).

## Scores (pass + abstain-ok, lint + guard, dev 61 + everyday 80)

| arm | dev | everyday | pooled | paired vs default | accepted wrong | rejected | abstain-missed |
|---|---|---|---|---|---|---|---|
| default | 26 | 42 | 68 | n/a | 40 | 29 | 4 |
| 1e-5, seed 42 | 27 | 44 | 71 | +4 / −1 | 42 | 26 | 2 |
| 3e-5, seed 42 | 26 | 49 | 75 | +10 / −3 | 46 | 17 | 3 |
| 1e-5, seed 43 | 25 | 43 | 68 | +1 / −1 | 43 | 26 | 4 |

- 3e-5 vs 1e-5 (seed 42): net +4, below the +5 the rule requires, and accepted-wrong is higher (46 vs 42). 1e-5 stays the default arm.
- The second seed of 1e-5 lands exactly on the default (68), so seed 42's +3 was seed noise. The stop condition in #15 fires; no gate run.
- "Rejected" is a proxy for false abstentions: the saved labels do not separate a lint rejection from an empty answer.
- 3e-5 converts rejections into accepted commands (rejected 29 → 17, accepted wrong 40 → 46) and gains most on everyday. It was not replicated with a second seed.

## Cost

Peak sampled server RSS (0.1 s) is 1,184,864 to 1,190,480 KiB (1.213 to 1.219 GB), against 1,178,468,352 B for the default; all inside the +64 MiB budget. p50 latency is 0.18 to 0.21 s, same as the default.

## Artifacts (SHA-256 of the Q4_K_M GGUF)

| arm | SHA-256 |
|---|---|
| 1e-5, seed 42 | `035a2cfdc2ca0c5ead4724d68ae0230fa6d7902e829b9d481e7e826415bd17cb` |
| 3e-5, seed 42 | `1acde8f39a289843bf381e363ac190fdd3697160137af53e682b8821064cbfea` |
| 1e-5, seed 43 | `b181367463bf835690d95c1489ca464f76d4edf7b67837a994253ed23f5eac7c` |
| zero update (control) | `099c2c7dd8da83eb83869e2b6a00caafffb3a707601bc5a267265892c1d4b4ce` |

Training data hash `903e6063…bb9fbbb` (the 1,075-row set). No model was published.

## Not done

Held-out and frozen were never scored for these arms, so they carry no information about generalisation. Any retrain should first fix the known corpus issues listed in the README and #15 (abstain-cue skew, the `Explicit inputs:` suffix missing from training prompts, abstain share of 23% against 5 to 13% in the eval sets).
