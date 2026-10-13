# Roihu full-corpus label review

Teacher: Qwen3.8-Flash-Next-FP8 (rev 236dfdf2), vLLM 0.29.0, 2,520 requests x 5 samples. Builder output before review: 844 commands + 243 abstain = 1,087 rows; after review: 843 + 243 = 1,086 rows; after the original six additional held-out-intent exclusions: 837 + 243 = 1,080 rows. Applying the 15 request-level exclusions from the corpus quarantine list and removing invalid `r00006` (`mdls -null` fails on macOS) leaves 832 commands + 243 abstentions = **1,075 rows** (`roihu_full_train.jsonl`).

Reviewers: two independent model reviewers (Claude Opus 5.5 and Claude Sonnet 5.5), read-only, with man pages and harmless introspection. **This is a model review, not a human review.** Rows: the builder's 30-command sample (`roihu_full_review_sheet.jsonl`) plus 15 abstain rows chosen with `random.Random(7)` from the remaining abstains (the builder's sample contains no abstain rows). The 30-command sheet is a historical pre-exclusion sample, retained unchanged; it includes `r00177` and `r01612`, which are excluded from the final training set.

| | Opus 5.5 | Sonnet 5.5 |
|---|---|---|
| commands (30) | 27 OK, 1 ALT, 1 UNSURE, 1 BAD | 29 OK, 1 BAD |
| abstains (15) | 7 RIGHT, then the run was cut off by an API safeguard (rows 38-45 not reviewed) | 15 RIGHT |

- BAD (both reviewers): r01612 `ps -o pgid= -p $$` should use `tpgid` (foreground group). Quarantined in `roihu_full_quarantine_ids.txt`.
- Opus ALT r00273 (`sed` comment stripping also cuts `#` inside values) and UNSURE r01122 (`chmod` on a directory vs its contents) were kept; Sonnet rated both OK.
- Strict precision: 27/30 = 90% (lower reviewer), 29/30 = 97% (higher). Abstain correctness 15/15 (Sonnet), 7/7 reviewed (Opus). Samples are small; no population claim beyond roughly 90%.
- Request-level held-out paraphrase exclusions from the shared corpus quarantine are now applied. The old label-specific exclusions were not carried over automatically because they refer to the earlier teacher's labels; `r00006` was independently revalidated and quarantined because `mdls -null` fails on macOS. Report-only tool+flag overlap with held-out remains large (355 rows) and is not gated.
- A human spot-check is still recommended before the set is treated as final.

## Default model on the training requests (no eval set involved)

`docs/default-on-training-requests.json` records per-request results from the prior harness run, filtered to the final 1,075 training requests; the model was not rerun. Lint harness: of 832 commands the default matches the teacher exactly on 61 and on tool+flags on 14 (9%), differs on 506, returns no command on 251; of 243 abstain rows it abstains on 108 and answers on 135. Model-only: 61 exact, 15 normalized, 751 different, 5 no-command; abstains on 13 of 243. "Different" is not necessarily wrong, so this is an upper bound on label disagreement, not an error rate.
