# Runtime LoRA: eight-seed A/B experiment

## Pre-registered decision rules

**Definitions:**
- **"Correct":** pass + abstain-ok, pooled over dev (61) + everyday (80) = 141.
- **"Seed mean / SD":** across the 8 seeds of one arm, each evaluated as the shipped Q4 + its runtime adapter.
- **"Per-case majority":** a case counts correct for an arm if at least 5 of its 8 seeds are correct.
- **"McNemar":** an exact two-sided binomial test on discordant cases, per-case majority vs default.
- **"Empty-on-answerable":** answerable cases (non-null accept) with `no_command_kind == empty_output`, averaged over seeds.
- **"Accepted-wrong":** label `wrong`, averaged over seeds.

**Rules:**

| # | Condition | Conclusion |
|---|---|---|
| R1 | A's seed mean ≥ default + 8, A's per-case majority McNemar p < 0.05, and A's mean accepted-wrong ≤ default + 2 | The runtime-LoRA gain is real on these 141 cases |
| R2 | B's seed SD ≤ ½ of A's, B's mean empty-on-answerable ≤ 5, and B's seed mean ≥ A's seed mean − 2 | Reducing empty targets is the stability fix |
| R3 | A's mean gain < 5 and McNemar p > 0.2 | Seed 42's 82 was a lucky draw. Recommend stopping tuning of this recipe (next options: verifier-selected labels with a re-aimed corpus, or retrieval / teacher fallback) |
| R4 | Any arm's mean sampled server RSS with adapter > default + 64 MiB, or p50 latency > default + 0.05 s | That arm fails the deployment budget, whatever its score |

None of these is a ship decision; shipping and serving changes are the user's call.

## Setup registered before trained-run evaluation

Branch `exp/runtime-lora-8seed`, from `data/v3-relabel` at
`967435938bd6a788b92bb91b69366097f2ea3330`. Arms A and B, seeds 1–8.
Unchanged rank 8 / alpha 160 / scale 20, last 16 layers, seven projection
modules, batch 1, AdamW lr 1e-5, one epoch, grouped validation fraction 0.05.

A: 1,149 rows (902 commands / 247 empty), grouped train 1,092 / validation 57;
steps 1,092. SHA-256
`c8f9661db1cadf79d81c58f0fd8f0628ad3461c61c0a5f97c6b20f195ec06550`.
B: 985 rows (902 commands / 83 empty, 8.426%), grouped train 936 / validation 49;
steps 936. Seeded subsample `random.Random(20261014)`; original bytes/order.
B has fewer optimizer steps and a different grouped validation partition; these
are confounds in attributing stability to the empty-target proportion alone.
B data hash is in `data/distill/stage2-v3-abstain8/manifest.json`.

Source/shipped base SHA-256:
`6f8a17a11129a31074c944f4c2602453fafd9de43bdaeb1630a8f511ec820f71`.
Tokenizer Qwen/Qwen2.5-Coder-1.5B-Instruct revision
`2e1fd397ee46e1388853d2af2c993145b0f1098a`; local transformers 4.57.1.
All 985 B rows pass chat_tokens; maximum 243 tokens. File hashes are in
`runtime-lora-8seed/reports/tokenizer-preflight.json`.
Host environment verified: torch 2.14.1+cu130, transformers 5.19.0,
peft 0.21.0, gguf 0.19.0; idle RTX 5090, CUDA 13.0, llama.cpp b11565.

Step-1 default sanity: exact equality of all 61 dev and 80 everyday labels with
`docs/stage2-arm-labels.json`; correct 26 + 42 = 68, accepted-wrong 40.
Stock PATH `/usr/bin:/bin:/usr/sbin:/sbin`, existing Mac server, shipped Q4.
No trained-run evaluation has occurred at registration.

Analysis conventions fixed now: sample SD (n−1), bootstrap 10,000 case resamples
with random.Random(20261014), percentile CI. Bootstrap samples a case with all
its eight seed outcomes, preserving the paired default. Unstable-case ordering:
closest to four correct seeds first, then case ID; report separately by arm.
Memory is sampled every 0.1 s on default and seed 1 of each arm, per requested
workload. Report sample mean and peak; seed-1 memory alone cannot estimate an
across-eight-seed mean. Compare each split's rounded eval p50 to default.

## Results

Pending training and evaluation.

## Deviations

None at registration.

## Not done

- Frozen/held-out reads, scores and final gate: prohibited.
- Serving or shipped-model changes, shipping, PR merge, HF publication: prohibited.
