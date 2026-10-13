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

Training and screening results pending.
