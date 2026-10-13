# Roihu full-corpus label review

Teacher: Qwen3.8-Flash-Next-FP8 (rev 236dfdf2), vLLM 0.29.0, 2,520 requests x 5 samples. Builder output before review: 844 commands + 243 abstain = 1,087 rows; after review: 843 + 243 = **1,086 rows** (`roihu_full_train.jsonl`).

Reviewers: two independent model reviewers (Claude Opus 5.5 and Claude Sonnet 5.5), read-only, with man pages and harmless introspection. **This is a model review, not a human review.** Rows: the builder's 30-command sample (`roihu_full_review_sheet.jsonl`, taken from the build before r01612 was removed) plus 15 abstain rows chosen with `random.Random(7)` from the remaining abstains (the builder's sample contains no abstain rows).

| | Opus 5.5 | Sonnet 5.5 |
|---|---|---|
| commands (30) | 27 OK, 1 ALT, 1 UNSURE, 1 BAD | 29 OK, 1 BAD |
| abstains (15) | 7 RIGHT, then the run was cut off by an API safeguard (rows 38-45 not reviewed) | 15 RIGHT |

- BAD (both reviewers): r01612 `ps -o pgid= -p $$` should use `tpgid` (foreground group). Quarantined in `roihu_full_quarantine_ids.txt`.
- Opus ALT r00273 (`sed` comment stripping also cuts `#` inside values) and UNSURE r01122 (`chmod` on a directory vs its contents) were kept; Sonnet rated both OK.
- Strict precision: 27/30 = 90% (lower reviewer), 29/30 = 97% (higher). Abstain correctness 15/15 (Sonnet), 7/7 reviewed (Opus). Samples are small; no population claim beyond roughly 90%.
- Known gap: the 27B-era author quarantine list was not applied (it names that teacher's rows). Report-only tool+flag overlap with held-out is large (355 rows) and is not gated.
- A human spot-check is still recommended before the set is treated as final.
