# Stage-2 v4 campaign status — revision 20261021-r3 (pass 1 in progress)

Runbook: [protocol.md](protocol.md). Rubric: [../LABEL.md](../LABEL.md). Machine-readable record:
[campaign-20261021-r3.json](campaign-20261021-r3.json), with r2 kept for the stop history.
Prior revisions are archived under [superseded/](superseded/).

**Status: pass 1 in progress. `b00`–`b21` accepted (5,006 candidate verdicts); `b22`
pending. No confirm, no build, no training.**

## Completed

- Pool built from base commit `d2bce9fb` (issue #35 merged): 23 batches, 2,062 items,
  5,111 candidates, 65 injected controls (25 expected-correct, 40 expected-incorrect),
  1,252 excluded candidates. Pool outputs are committed here and were byte-identical on
  a repeated build.
- r2 controls re-derived after the semantic audit: 11 replacements, 2 disputed controls
  retained (`ct0006`, `ct0022`), 54 lines unchanged
  ([control-audit-r2-20261020.json](control-audit-r2-20261020.json)).
- Pass 1 accepted for `b00`–`b04` by `gpt-6.1-sol-medium`, one fresh session per batch,
  all controls correct (`verdicts/b00.json`…`b04.json`, 1,169 candidate verdicts:
  843 correct / 284 incorrect / 42 unsure).
- **`b05` accepted 2026-10-21** by the main-session judge (`dsh-main-20261021-b05-a1`):
  237 verdicts, 211 correct / 26 incorrect, and all three live controls correct
  (`ct0022` incorrect, `ct0024` incorrect, `ct0057` correct). Verdict SHA-256
  `9c9e08d4…` in [campaign-20261021-r3.json](campaign-20261021-r3.json).
- **`b06` accepted 2026-10-22** by the main-session judge (`dsh-main-20261022-b06-a1`):
  228 verdicts, 182 correct / 46 incorrect; `ct0054` and `ct0002` matched, and the
  contested `ct0018` was judged correct without being compared to its expectation.
- **`b07` accepted 2026-10-22** by the main-session judge (`dsh-main-20261022-b07-a1`):
  233 verdicts, 197 correct / 36 incorrect; `ct0020` and `ct0043` matched.
- **`b08` accepted 2026-10-22** by the main-session judge (`dsh-main-20261022-b08-a1`):
  207 verdicts, 162 correct / 45 incorrect; `ct0047`, `ct0023` and `ct0016` matched.
- **`b09` accepted 2026-10-22** by the main-session judge (`dsh-main-20261022-b09-a1`):
  220 verdicts, 187 correct / 33 incorrect; `ct0041`, `ct0003` and `ct0028` matched.
- **`b10` accepted 2026-10-22** by the main-session judge (`dsh-main-20261022-b10-a1`):
  232 verdicts, 190 correct / 42 incorrect; `ct0031`, `ct0032` and `ct0056` matched.
- **`b11` accepted 2026-10-22** by the main-session judge (`dsh-main-20261022-b11-a1`):
  228 verdicts, 197 correct / 31 incorrect; `ct0035`, `ct0052` and `ct0038` matched.
- **`b12` accepted 2026-10-22** by the main-session judge (`dsh-main-20261022-b12-a1`):
  237 verdicts, 208 correct / 29 incorrect; `ct0050`, `ct0044` and `ct0037` matched.
- **`b13` accepted 2026-10-22** by the main-session judge (`dsh-main-20261022-b13-a1`):
  234 verdicts, 209 correct / 25 incorrect; `ct0065` and `ct0026` matched.
- **`b14` accepted 2026-10-22** by the main-session judge (`dsh-main-20261022-b14-a1`):
  223 verdicts, 196 correct / 27 incorrect; `ct0006`, `ct0008` and `ct0042` matched.
- **`b15` accepted 2026-10-22** by the main-session judge (`dsh-main-20261022-b15-a1`):
  217 verdicts, 180 correct / 37 incorrect; `ct0059`, `ct0025` and `ct0005` matched.
- **`b16` accepted 2026-10-22** by the main-session judge (`dsh-main-20261022-b16-a1`):
  244 verdicts, 219 correct / 25 incorrect; `ct0033`, `ct0061` and `ct0049` matched.
- **`b17` accepted 2026-10-22** by the main-session judge (`dsh-main-20261022-b17-a1`):
  239 verdicts, 212 correct / 27 incorrect; `ct0017`, `ct0060` and `ct0036` matched.
- **`b18` accepted 2026-10-22** by the main-session judge (`dsh-main-20261022-b18-a1`):
  187 verdicts, 173 correct / 14 incorrect; `ct0030`, `ct0045` and `ct0009` matched.
- **`b19` accepted 2026-10-22** by the main-session judge (`dsh-main-20261022-b19-a1`):
  241 verdicts, 215 correct / 26 incorrect; `ct0004`, `ct0048` and `ct0012` matched.
- **`b20` accepted 2026-10-22** by the main-session judge (`dsh-main-20261022-b20-a1`):
  216 verdicts, 189 correct / 27 incorrect; `ct0046`, `ct0034` and `ct0039` matched.
- **`b21` accepted 2026-10-22** by the main-session judge (`dsh-main-20261022-b21-a1`):
  214 verdicts, 195 correct / 19 incorrect; `ct0011`, `ct0063` and `ct0029` matched.
- **Live controls adjudicated** before `b05` as a pilot gate:
  [control-adjudication-r3-20261021.json](control-adjudication-r3-20261021.json) —
  52 live controls, 51 verified, 1 contested (`ct0018`, in `b06`; its "incorrect"
  expectation is unsupported by the request). Verified controls are gated as before;
  a contested control still needs a verdict but is not compared to its expectation.

## How the stop was resolved

`b05` had failed twice and the pre-registered retry budget says stop:

1. Strata `qwen3.8-flash-next-iq3_s` attempt 1 (`strata-runs/b05-a1/`) hit the local
   controller's 32-round limit with no verdict.
2. Attempt 2 (`strata-runs/b05-a2/`) produced a complete 237-verdict batch, but 2 of 3
   controls disagreed (`ct0024`, `ct0022`: both expected incorrect, judged correct).
   The verdict is archived at [`superseded/r2-strata-b05-a2.json`](superseded/r2-strata-b05-a2.json).

Post-mortem: [strata-runs/b05-a2/diagnosis.json](strata-runs/b05-a2/diagnosis.json) —
evidence supports a permissive judge, not missing input or transport failure. The same
judge was 89% correct on b05 candidates versus 72% for the accepted Sol batches, and it
accepted two commands it had itself identified as defective. Recommendation recorded
there: do not retry the unchanged Strata model; qualify any replacement judge on
examples disjoint from the campaign controls before revising the retry plan.

## Already-visible value (why the campaign is worth resuming)

Of the 269 no-majority requests judged in `b00`–`b04`, 232 (86%) have at least one
judged-correct candidate; 7 of 181 v3 targets would be dropped. Extrapolated over the
pool this roughly doubles command labels (v3: 902) — it addresses the label-coverage
limit documented in [docs/teacher-ceiling.md](../../../../docs/teacher-ceiling.md).

## Resume conditions (met for b05)

1. A calibration set was built and frozen ([calibration/](calibration/)); two judges
   failed it, and the failure review found ~8% error in the accepted labels themselves
   (see below). The gate was corrected by adjudicating the live controls instead.
2. The retry plan was revised in `r3`: main-session judge, per-batch verified controls,
   same failure caps.
3. `b05` was re-judged once as a pilot and passed.

Acceptance after pass 1 is unchanged: deterministic 20% confirm by independent sessions,
`build_verified_dataset.py`, a human spot check of at least 30 retained rows, quality
report, and a byte-identical rebuild. The quality report must state the measured label
error, not "100% verified".

## Remaining

- `b22`: 1 batch, ~170 candidates. The contested-control exemption is now
  wired into both the confirm and the build (`--adjudication`).
- Then the deterministic 20% confirm, the build, the 30-row human spot check, the
  quality report and the byte-identical rebuild.

## Judge qualification attempts

- **2026-10-21, attempt 1 — DSH subagent judge: failed.** 10/13 spent controls and 8 false
  accepts of 35; the same permissive pattern as the Strata attempts (correct flags, wrong
  semantics). No campaign batch was re-judged, no confirm was produced, and the retry
  budget is untouched. Details:
  [calibration/attempts/dsh-subagent-20261021-a2/ATTEMPT.md](calibration/attempts/dsh-subagent-20261021-a2/ATTEMPT.md).
- **2026-10-21, attempt 2 — main-session judge: failed the agreement bar, and the review
  found reference errors.** 81/103 accepted verdicts reproduced, 17 false accepts of 34.
  Disagreement review verified at least 8 accepted labels that are demonstrably wrong
  (`stat %p`, `plutil -p -`, `lsof -F`, `say -v '?'` columns, `git submodule --cached`,
  `plutil … xml1 | sed`, `tmutil latestbackup`) and about 6 of the judge's own verdicts
  that were wrong. Conclusion: the accepted pass-1 labels carry roughly 8% error, so a
  100%-per-batch control gate built from the same audit material cannot be passed by an
  honest independent judge. Details:
  [calibration/attempts/main-session-20261021/ATTEMPT.md](calibration/attempts/main-session-20261021/ATTEMPT.md).

## What this commit contains

Campaign records (original, consensus, r2, r3), control audits, the control adjudication,
the 65 controls, the semantic audit and its evidence, the frozen calibration set and both
failed attempts, pool outputs, the accepted verdicts (`b00`–`b05`), the rejected b05
evidence and its diagnosis, the read-only evidence snapshots, the archived prior
campaigns, and the local judge controller (`tools/judge_v4_local.py`,
`tests/test_judge_v4_local.py`). `confirm-verdicts/` is intentionally absent (pass 2 has
not run).
