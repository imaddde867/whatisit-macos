# Data v3 training and development screening (2026-10-14)

Q4_K_M and Q8_0 pass screening against default for both seeds. Q6_K fails:
seed 42 increases accepted-wrong from 40 to 42. Attribution against v2 fails:
Q8_0 scores 82 / 71 versus v2 seed 42's 81, below the required 84 for both seeds.
No claim that re-labelling helped is supported. Seed 42 stays nominated in advance.
The final gate was not run; shipped model and serving code stay unchanged.

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

Tokenizer: Qwen/Qwen2.5-Coder-1.5B-Instruct revision
`2e1fd397ee46e1388853d2af2c993145b0f1098a`; local transformers 4.57.1 and
host 5.19.0 use identical pinned tokenizer-file hashes, including LICENSE on
the host. Initial weights are dequantized from the shipped NL2SH Q4 source.

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
The Mac suite has 83 tests with that hardware-only test skipped locally; all
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
active builder includes that additional guard. The later option/path-role guards at 88e99ac also preserve all 26 frozen files,
including every label and review input. These corrections follow man-page
semantics and failing unit tests, independently of development scores. The
dataset and training runs were therefore unchanged. See post-freeze-vote-validation.json.

Default sanity check passes: all 141 per-case labels exactly reproduce the
saved default arm with stock PATH. Dev 26/61, everyday 42/80, pooled 68/141.

The complete 26-file frozen data package also reproduces byte-for-byte:

```sh
PYTHONPATH=src .venv/bin/python tools/reproduce_distill_v3.py /tmp/whatisit-v3-fresh-repro
```

This reruns the existing builders/gates and seeded sample, verifies all rebuilt
labels/lineage/counts, then reuses immutable model judgments and man/scratch
review evidence. It does not rerun model judgment. The command refuses an
existing directory; `full-package-reproduction.json` records every matching hash.



## Data and model review

v2 has 1,091 rows; v3 has 1,149, a net increase of 58. Sixty command labels
are recovered (42 clusters with 3 votes, 17 with 4, one with 5). All 60 have
multiple exact strings; 131 strings were read in model merge review. No remaining
meaning-changing pair was found. Conservative guards corrected zip patterns,
quote-sensitive expansions/redirections, relative roots, trailing slashes and
last-wins options; deviations and the low-recovery investigation are in
[v3-relabel-protocol.md](v3-relabel-protocol.md). Existing exact-majority strings
remain unchanged and pinned amendments do not go stale. One newly recovered
author-abstain command conflict is excluded and listed in the base side file.

The 902 commands and 247 abstentions give 21.5% abstention versus v2's 22.7%.
There are 21 new corpus tool/flag signatures and zero new repeated exact-command
rows. Seven hard-hit IDs exclude 10 whole-family rows; historical quarantines
apply equally to recovered rows. All 36 authored additions enter repair, with
27 retained after whole-family exclusions. Category/agreement counts and every
data hash are in the frozen manifest.

Model review is a census of all 60 recovered rows: 51 OK, 8 wrong, 1 debatable.
Precision 85.0%, Wilson 95% 73.9–91.9%. The interval is descriptive because this
is a census and judgments are from a model. The inclusive gate passes exactly
at nine non-OK. Failures include invented metadata attributes, incompatible or
misused BSD options, a Git reflog expression answering a different question,
non-stock Xcode dependence and an unsupported global-network-service query.
Known wrong/debatable labels remain documented; this is not human-certified data.
The 23 scratch read checks ran with stock PATH; generated writes, deletes,
sudo and network changes were not executed. Review results and all merge strings
are in the frozen data folder.

## Scores (correct = pass + abstain-ok)

| arm | precision | dev / 61 | everyday / 80 | pooled / 141 | paired vs default wins / losses | accepted wrong | rejected | abstain-missed |
|---|---|---|---|---|---|---|---|---|
| default | Q4_K_M | 26 | 42 | 68 | — | 40 | 29 | 4 |
| v3 seed 42 | Q8_0 | 29 | 53 | 82 | 24 / 10 | 39 | 19 | 1 |
| v3 seed 43 | Q8_0 | 27 | 44 | 71 | 21 / 18 | 36 | 34 | 0 |
| v3 seed 42 | Q6_K | 29 | 54 | 83 | 24 / 9 | 42 | 15 | 1 |
| v3 seed 43 | Q6_K | 27 | 46 | 73 | 21 / 16 | 36 | 32 | 0 |
| v3 seed 42 | Q4_K_M | 27 | 45 | 72 | 4 / 0 | 38 | 29 | 2 |
| v3 seed 43 | Q4_K_M | 27 | 42 | 69 | 1 / 0 | 39 | 30 | 3 |

Per-case labels are in [v3-arm-labels.json](v3-arm-labels.json). Every per-case
flip versus default and same-precision v2, including before/after labels, is in
[v3-training-reports/screening-results.json](v3-training-reports/screening-results.json).
Rejected combines empty output and harness rejection. Correctness-paired wins
and losses do not count wrong↔rejected flips; the full label-flip lists do.

| precision | seed 42 vs default | seed 43 vs default | registered screen |
|---|---|---|---|
| Q8_0 | PASS | PASS | PASS |
| Q6_K | FAIL: accepted-wrong increases | PASS | FAIL |
| Q4_K_M | PASS | PASS | PASS |

Both passing precisions improve pooled correct, regress neither development
split, and increase neither accepted-wrong nor abstain-missed for either seed.
Seed spread is 11 pooled cases at Q8, 10 at Q6 and 3 at Q4. This experiment
provides no basis for selecting the better seed after seeing results.

## Attribution versus v2 seed 42

| precision | v2 dev / everyday / pooled | v3 seed | v3 pooled | delta | paired wins / losses |
|---|---|---|---|---|---|
| Q8_0 | 27 / 54 / 81 | 42 | 82 | +1 | 7 / 6 |
| Q8_0 | 27 / 54 / 81 | 43 | 71 | -10 | 6 / 16 |
| Q6_K | 28 / 54 / 82 | 42 | 83 | +1 | 7 / 6 |
| Q6_K | 28 / 54 / 82 | 43 | 73 | -9 | 7 / 16 |
| Q4_K_M | 27 / 43 / 70 | 42 | 72 | +2 | 2 / 0 |
| Q4_K_M | 27 / 43 / 70 | 43 | 69 | -1 | 0 / 1 |

Attribution rule: **FAIL**. Both Q8 seeds must reach at least 84 and have more
paired wins than losses. Seed 42 reaches 82 with 7/6 wins/losses; seed 43 reaches
71 with 6/16. No re-labelling-benefit claim is made. v2 has one measured seed at
higher precision; the two v3 seeds reveal substantial run/quantization variation.

File baselines additionally reproduce v2 f16 = Q8 at 81, Q6 at 82, Q5 at 80,
and zero-update f16 at 68. v2 f16 and Q8 per-case files are byte-identical.
Teacher majority is 88/141, mean single-sample correct 84.1%, best-of-five oracle
128/141. No teacher sampling or re-scoring with a new voting rule was performed.

## Coverage

Coverage requires every non-trivial stage of the reference to have its exact
tool/subcommand and sorted flag set somewhere in training; operands are ignored
only for this reporting key. The voting key retains operands. Trivial echo-only
references have their own bucket. Actual training-partition coverage removes
validation rows and verifies val_ids against both saved training reports.
There are 415 v2 and 433 v3 trained-partition signatures. The full label corpus
has 431 and 452 respectively. Both views are reported because grouped validation
changes which existing commands receive gradients.

Cells below are **v3 correct (delta versus default / delta versus same-precision v2)**.

Actual training partitions:

| arm | both (n=58) | new_in_v3 (n=4) | v2_only (n=1) | neither (n=65) | abstention (n=12) | trivial_reference (n=1) |
|---|---|---|---|---|---|---|
| s42-Q8_0 | 39 (+9 / -2) | 3 (+1 / +0) | 1 (+0 / +0) | 28 (+1 / +2) | 11 (+3 / +1) | 0 (+0 / +0) |
| s43-Q8_0 | 36 (+6 / -5) | 2 (+0 / -1) | 1 (+0 / +0) | 20 (-7 / -6) | 12 (+4 / +2) | 0 (+0 / +0) |
| s42-Q6_K | 40 (+10 / -3) | 3 (+1 / +1) | 1 (+0 / +0) | 28 (+1 / +2) | 11 (+3 / +1) | 0 (+0 / +0) |
| s43-Q6_K | 37 (+7 / -6) | 2 (+0 / +0) | 1 (+0 / +0) | 21 (-6 / -5) | 12 (+4 / +2) | 0 (+0 / +0) |
| s42-Q4_K_M | 32 (+2 / +1) | 2 (+0 / +0) | 1 (+0 / +0) | 27 (+0 / +0) | 10 (+2 / +1) | 0 (+0 / +0) |
| s43-Q4_K_M | 30 (+0 / -1) | 2 (+0 / +0) | 1 (+0 / +0) | 27 (+0 / +0) | 9 (+1 / +0) | 0 (+0 / +0) |

Full label corpora (including rows later assigned to validation):

| arm | both (n=61) | new_in_v3 (n=2) | neither (n=65) | abstention (n=12) | trivial_reference (n=1) |
|---|---|---|---|---|---|
| s42-Q8_0 | 42 (+9 / -2) | 1 (+1 / +0) | 28 (+1 / +2) | 11 (+3 / +1) | 0 (+0 / +0) |
| s43-Q8_0 | 39 (+6 / -5) | 0 (+0 / -1) | 20 (-7 / -6) | 12 (+4 / +2) | 0 (+0 / +0) |
| s42-Q6_K | 43 (+10 / -2) | 1 (+1 / +0) | 28 (+1 / +2) | 11 (+3 / +1) | 0 (+0 / +0) |
| s43-Q6_K | 40 (+7 / -5) | 0 (+0 / -1) | 21 (-6 / -5) | 12 (+4 / +2) | 0 (+0 / +0) |
| s42-Q4_K_M | 35 (+2 / +1) | 0 (+0 / +0) | 27 (+0 / +0) | 10 (+2 / +1) | 0 (+0 / +0) |
| s43-Q4_K_M | 33 (+0 / -1) | 0 (+0 / +0) | 27 (+0 / +0) | 9 (+1 / +0) | 0 (+0 / +0) |

Newly covered cases in the training partition: `e058, m018, m036, m078`.
Newly covered cases in the full corpus: `m036, m078`.

The original teacher-right/f16-student-wrong set contains 30 cases. Counts of
currently fixed cases include fixes already present at a different precision;
new/lost columns compare with same-precision v2 and prevent crediting those to v3.
All case IDs are retained in the machine-readable results.

| arm | now fixed / 30 | newly fixed vs v2 | v2 fixes lost |
|---|---|---|---|
| s42-Q8_0 | 5 | 5 | 0 |
| s43-Q8_0 | 5 | 5 | 0 |
| s42-Q6_K | 6 | 4 | 0 |
| s43-Q6_K | 5 | 5 | 2 |
| s42-Q4_K_M | 7 | 0 | 0 |
| s43-Q4_K_M | 7 | 0 | 0 |

## Latency and server memory

| arm | dev p50 s | everyday p50 s | sampled peak RSS bytes |
|---|---|---|---|
| default | 0.21 | 0.24 | recorded baseline 1,178,468,352 |
| s42-Q8_0 | 0.22 | 0.24 | 1,873,461,248 |
| s43-Q8_0 | 0.23 | 0.21 | 1,873,559,552 |
| s42-Q6_K | 0.20 | 0.21 | 1,499,398,144 |
| s43-Q6_K | 0.21 | 0.20 | 1,499,545,600 |
| s42-Q4_K_M | 0.20 | 0.20 | 1,218,314,240 |
| s43-Q4_K_M | 0.20 | 0.20 | 1,213,054,976 |

The locked budget is recorded default RSS + 64 MiB = **1,245,577,216 bytes**.
Q6 seed 42: 1,499,398,144 bytes, **253,820,928 bytes (242.06 MiB) above budget**.
Q6 seed 43: 1,499,545,600 bytes, **253,968,384 bytes (242.20 MiB) above budget**.

RSS was sampled at approximately 0.1 s intervals, matching the recorded workload
and sampling method; these are sampled peaks, not OS high-water marks. p50 values
are the existing harness's rounded per-split medians, not a pooled latency estimate.
Serving is the existing Mac llama.cpp b10333 (08659901c); quantization is pinned
GPU b11565. The exact Mac environment/harness hashes are in mac-environment.json.

## Artifacts and publication

| model | SHA-256 |
|---|---|
| s42-Q8_0 | `6cc58dab48df4c9772072c39e108307c04a66b8401de99f6306ec2137280e5d1` |
| s43-Q8_0 | `f229c14fa7540016355c58532316fce314ac7c7efb69282a7f40aab75be9f31c` |
| s42-Q6_K | `ecc6004199fa8fbcd7907107d4f698e35aa5f74479f1afe8c3c6c650f8c0fafe` |
| s43-Q6_K | `470eeef67c0e870e80cfa70b8ea957d445e926b5f1b7f47de7a0629ede8ceaf4` |
| s42-Q4_K_M | `0075cc8eef253e78d73e8147151cf21db62053fbe0058f07483cfb41dae44002` |
| s43-Q4_K_M | `e2e331be42a3d48c100a329585f05e0aa8d89aa4a2d82c55dd90f482f3c37c7f` |

Unmerged adapter weight SHA-256:

- Seed 42: `7a717e58f6c9478a131725b6402f75677464ae892549cc24cfefeb50fdbc9dad`.
- Seed 43: `412fb400005c7b33f1f691bcd1ab3affeb9fdd4035bb719672922a714b611dac`.

Adapters, LICENSE and NOTICE are retained locally in
`~/.local/share/whatisit/finetune/v3/adapter-seed42/` and `adapter-seed43/`.
Seed-42 quantized files are at that v3 root; seed-43 files are under `seed43/`.
All six copies match the GPU hashes. rsync delta transfer reused read-only v2
Q8 and preserved partial Q6 files; no baseline model was modified. Both reports,
f16/adapter/quantized hashes, transfer verification, label flips and source hashes
are in [v3-training-reports/manifest.json](v3-training-reports/manifest.json);
SHA256SUMS externally hashes the manifest. Large models were not committed or published.

Dataset publication is one HF commit in a new stage2-v3 folder:
[5a62bf3f3a98aa0d2f03b2fe6630f33d7883f72e](https://huggingface.co/datasets/imaadd05/whatisit-macos-roihu-teacher-labels/commit/5a62bf3f3a98aa0d2f03b2fe6630f33d7883f72e).
The README recommends v3 and keeps v2 history; existing folders are unchanged.
Re-downloaded train.jsonl matches the registered hash. Branch `data/v3-relabel`
starts at `eval/teacher-ceiling` (8452bec). Protocol/code/tests were committed at
6e76208 before the first real-corpus rebuild. Corrected data freeze: 634a733;
trainer change/pre-registered result rules: 67d2cfc; active EQUALS guard: 655f7d2; long-option/path-role guards: 88e99ac.
Draft PR: [#30](https://github.com/imaddde867/whatisit-macos/pull/30), against main.
Commits use an honest Codex co-author trailer; no Claude-session attribution is invented.

## Not done

- Frozen + held-out final gate: deliberately not run. Protected contents are read only by the existing leakage gate; protected hashes are historical manifest values, never freshly hashed or uploaded.
- Shipped model changes, serving-code changes, adapter serving path, and PR merge.
- Human review; all new label/code reviews are explicitly model review.
- New teacher sampling, voting-rule/hyperparameter selection from development scores, and lint false-positive fixes.
