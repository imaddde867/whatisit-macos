# Pilot label review result

Reviewers: two independent model reviewers (Claude Opus 5.5 and Claude Sonnet 5.5), each verifying flags/keys with man pages and read-only introspection on this Mac. **This is a model review, not a human review.** The 30 rows are in `pilot_review_sheet.md` / `pilot_review_sample_reviewed.jsonl` (pre-removal sample; the sheet is kept as reviewed).

| reviewer | OK | ALT | BAD | UNSURE |
|---|---|---|---|---|
| Opus 5.5 | 27 | 0 | 3 | 0 |
| Sonnet 5.5 | 28 | 0 | 2 | 0 |

BAD rows (both flagged r00057 and r00006; only Opus flagged r00005):
- r00057 `ps ... -o thcount`: no such keyword on macOS; correct: `ps -M -p <pid> | tail -n +2 | wc -l`.
- r00006 `mdls -all f`: not an option; correct: `mdls f`.
- r00005 `df -h -t apfs`: works but deprecated (man df); documented form is `-T`.

Estimated label precision: 27/30 = 90% (strict, lower reviewer). All three rows are now in `quarantine_ids.txt` and excluded from `pilot_train.jsonl`.

Gaps this exposed in the gates (two wrong labels passed lint, deletion guard and 3-of-5 agreement):
- `ps -o` keywords are now validated against `ps -L` on the host (fixed in maclint).
- Tools with whole single-dash options (`mdls -name/-raw`) accept `-all` through the combined-short-flag path. A general fix broke valid references (scutil --nwi, qlmanage -o, afconvert -f/-d), so it was not applied. Known limit; 3 eval references are already false positives for the same reason.

A human spot-check of these rows is still recommended before this set is treated as final; the full run will repeat the review on a fresh sample.
