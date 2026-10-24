# Small-model selection plan

Docs only; nothing here has been run. Target: Apple M4, 16 GiB, stock macOS `/bin/zsh -f`, BSD utilities.

**Ship rule:** a 1.5B-class Q4_K_M model plus the lint harness. Candidates outside that class are screening comparators only; shipping one needs an explicit owner decision.
**Out of scope:** Qwen3-1.7B (owner decision). No ranking below; order is arbitrary.

## Candidates

Checkpoint IDs, revisions, licences, text-only support and chat-template/thinking behaviour: **verify at run time** for every row.

| Model | Runtime to try | Note |
| --- | --- | --- |
| NL2SH-1.5B (shipped) | llama.cpp (GGUF) | Control; re-baseline post-#35 |
| LFM2.5-1.2B-Instruct | MLX, llama.cpp | Hybrid conv/attention; non-Apache licence, check redistribution |
| MiniCPM5 (size/variant TBD) | MLX, llama.cpp | Not yet inspected |
| Qwen3.5-2B | MLX, llama.cpp | Multimodal checkpoint; needs a text-only path; GatedDeltaNet LoRA backward is slow in MLX (mlx-lm #1956) |
| Qwen2.5-Coder-1.5B-Instruct | MLX, llama.cpp | Clean-checkpoint control |
| Qwen3.5-0.8B | MLX, llama.cpp | Same hybrid questions as 2B |
| Granite 4 1B | MLX, llama.cpp | Check checkpoint and licence |
| LFM2.5-2.6B | MLX, llama.cpp | Always-thinking; likely poor fit |
| SmolLM3-3B, Gemma 4 E2B, Ministral 3 3B | MLX, llama.cpp | Above 1.5B class; comparators |
| Llama 3.2 1B, Gemma 3 1B, Phi-4-mini | MLX, llama.cpp | Sanity controls |

Skip any model with no working runtime path (`backend_unqualified`). Add models by appending rows.

## Runtimes

- MLX / mlx-lm: zero-shot screen and LoRA/QLoRA. An MLX adapter does not run on `llama-server`.
- llama.cpp (GGUF, Q4_K_M; Q5_K_M/Q6_K if Q4 loses quality): the shipping path.
- Others (e.g. Ollama, LM Studio) only if a candidate has no MLX/GGUF path; record why.
- Download one model at a time, outside the repo (`$MODEL_RUN`); commit no weights or outputs.

## Gates (keep all)

1. **Protected sets:** never read, score or tune on `eval/frozen.jsonl` or `eval/heldout.jsonl` before the final gate. Screening uses development cases only.
2. **Screen (no training):** same balanced <=100 dev requests, prompt and validator for every model; BSD options, macOS-only tools, operands, composition, abstention. Record raw output, guard reason, blind semantic verdict with evidence. Rank by accepted-wrong/safety, then semantic correct, abstention, latency/memory; not by vendor benchmarks.
3. **No training until #36 accepts the v4 labels** (20% independent pass-2 confirm, >=30 human spot-check, leakage audit, byte-identical rebuild). #15 blocks v4 training until then. A 20-step optimizer probe counts as training.
4. **Template parity:** train-time and serve-time rendering must match (thinking prefix, EOS, loss mask, empty-abstention encoding). Mismatch: stop.
5. **Pre-register** before any gradient step: one primary and at most one challenger, split, revision, optimizer, seeds (42/43/44), stop rule, memory budget. Report all seeds.
6. **Quantization parity:** compare base, adapter, fused and deployed Q4_K_M per case. If Q4 erases the gain (seen before), stop or try Q5/Q6.
7. **Perf:** cold and warm p50/p95, whole-process-tree RSS, idle unload, through the same worker plus guard. Never compare a fresh MLX process with a warm server.
8. **Final gate (#11):** one-shot pooled frozen (59) + held-out (150), exact one-sided sign test p <= 0.05, abstain-missed not increased, no dev regression, memory/latency within budget. Otherwise SHELVE. No second criterion.
9. **Do not touch** `src/`, `eval/`, `data/distill/stage2-v3/` or the shipped model from this branch. Never execute generated commands outside the allowlisted scratch-fixture evaluator.

## Stop conditions

- Fails stock-macOS smoke tests or cannot emit a short one-line command or abstention.
- MLX backward/optimizer crashes, swaps heavily, or exceeds the recorded memory budget.
- Template divergence between training and serving.
- Gains regex matches but not blinded semantic correctness, or raises accepted-wrong.
- Gain lost after conversion or quantization.
- Larger memory or latency for a non-significant gain.
- #36 unresolved (provenance, confirmation, leakage).

## Receipts (per run, outside the repo)

Environment and git SHA, resolved requirements, model manifest (ID, revision, hashes, licence), screen requests and outputs, decision note, data manifest and hashes, training reports and adapter SHA-256, conversion manifest, perf JSON, per-case dev verdicts, `KEEP-or-SHELVE`.

Links: [#36](https://github.com/imaddde867/whatisit-macos/issues/36), [#15](https://github.com/imaddde867/whatisit-macos/issues/15), [#11](https://github.com/imaddde867/whatisit-macos/issues/11), [PR #38](https://github.com/imaddde867/whatisit-macos/pull/38).
