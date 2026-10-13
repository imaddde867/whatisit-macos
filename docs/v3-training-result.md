# Data v3 training and development screening

Registered before computing v3 development scores. Seed 42 is nominated in advance.
Development/everyday sets are used only for this final screening, never to choose
voting variants, thresholds or training hyperparameters.

For each precision Q8_0, Q6_K and Q4_K_M, v3 passes versus default only if both
seeds improve pooled correct, neither dev nor everyday regresses, accepted-wrong
does not increase and abstain-missed does not increase. Correct = pass + abstain-ok.

Claim "re-labelling helped" versus v2 only if both v3 Q8_0 seeds score at least
v2 seed 42 + 3 pooled correct and paired wins exceed losses. Same-precision v2
comparisons use seed 42. No better-seed selection after results.

Report all per-case flips versus default and v2, tool/flag coverage buckets,
teacher-right/student-wrong fixes, p50 latency and Q6_K sampled RSS against
default sampled RSS + 64 MiB. The final frozen/heldout gate is not run.

Data: 60 recovered commands; 1,149 total rows, 902 commands and 247 abstentions.
Model review: 51/60 OK, 8 wrong, 1 debatable; 85.0%, Wilson 95% 73.9–91.9%.
Inclusive review gate passes with nine non-OK. Grouped split: 1,092 training,
57 validation rows; no validation command strings in training. Every row passes
the real pinned tokenizer. All 60 merge clusters / 131 strings were read.

Train SHA-256: `c8f9661db1cadf79d81c58f0fd8f0628ad3461c61c0a5f97c6b20f195ec06550`.
Source SHA-256: `6f8a17a11129a31074c944f4c2602453fafd9de43bdaeb1630a8f511ec820f71`.
HF commit: `5a62bf3f3a98aa0d2f03b2fe6630f33d7883f72e` (re-download hash verified).

Training completed on the RTX 5090: rank 8, alpha 160, last 16 layers, seven
projection modules, batch 1, AdamW lr 1e-5, one epoch of 1,092 steps per seed.
The environment is torch 2.14.1+cu130, transformers 5.19.0, peft 0.21.0,
gguf 0.19.0; CUDA 13.0. Seed 42 took 39.86 s training / 67.77 s total,
seed 43 40.43 s / 68.66 s. Peak allocated memory was 6,069,899,264 and
6,070,642,176 bytes. Validation loss fell from 2.7951 to 0.3630 / 0.3486.
Validation loss measures teacher-target likelihood, not command correctness.

Both reports verify train_rows == steps, direct equality of val_ids, and the
registered data/source hashes. Before merge, each unmerged LoRA adapter was
saved; every adapter file hash is in its training report. A real-GPU zero-step
integration test verified adapter persistence and unchanged merged source weights.
The Mac suite has 81 tests with that hardware-only test skipped locally; all
six trainer tests passed on the GPU host. Host chat_tokens preflight passed
all 1,149 rows (maximum 243 tokens). No eval directory was copied to the host.

Quantization uses only GPU-host llama.cpp build 11565, commit f9a95aeb2, four
threads. The executable SHA-256 is
`650b82c73a245e1a5058c848d45c6a3571f748b4c837972e235a420bffcf267d`;
all libraries and pinned tokenizer metadata hashes are recorded in
[v3-training-reports/host-assets-sha256.txt](v3-training-reports/host-assets-sha256.txt).
All artifact hashes, including f16 outputs and adapters, are retained in the
per-seed checksum files. Q8_0 is the pre-registered f16 stand-in.

The initial 64-row diagnostic data commit was superseded before HF publication
or training. Independent model code review prompted additional conservative
lexer guards. A later synthetic stock-zsh EQUALS counterexample was fixed in
active builder commit 655f7d2; fresh full-corpus base/repair rebuilds preserve
every train, request, audit, cluster and leakage byte. The frozen generator
snapshot remains pinned to its original code hash for reproducibility; the
active builder includes that additional guard. The dataset and training runs
were therefore unchanged. See post-freeze-vote-validation.json.

Default sanity check passes: all 141 per-case labels exactly reproduce the
saved default arm with stock PATH. Dev 26/61, everyday 42/80, pooled 68/141.

Development screening results pending transfer completion.
