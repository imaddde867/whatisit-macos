# Stage-2 v4 campaign status — revision 20261020-r2 (stopped)

Runbook: [protocol.md](protocol.md). Rubric: [../LABEL.md](../LABEL.md). Machine-readable record:
[campaign-20261020-r2.json](campaign-20261020-r2.json). Prior revisions are archived under
[superseded/](superseded/).

**Status: stopped at the retry-budget gate. No judge is running. The dataset is not built.**

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
  843 correct / 284 incorrect / 42 unsure). Verified verdict SHA-256 values are in
  `campaign-20261020-r2.json` → `accepted_pass1`.

## Stopped

`b05` failed twice and the pre-registered retry budget says stop:

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

## Resume conditions (all required)

1. A replacement judge is identified and qualified on a disjoint calibration set
   (frozen before any campaign batch is re-judged), with read-only man-page tools and
   no candidate execution. The set and its bar live in [calibration/](calibration/):
   13 spent controls (13/13 required), 112 accepted verdicts (≥101 required, ≤2 false
   accepts, ≤2 unsure).
2. The retry plan is explicitly revised in a new revision (`r3`): provider amendment,
   judge identity, budget reset under the same caps (one fresh retry per failed batch,
   stop at three failed attempts, stop when a retry fails).
3. `b05` is then re-judged once with that judge as a pilot; the remaining batches follow.

Acceptance after pass 1 is unchanged: deterministic 20% confirm by independent sessions,
`build_verified_dataset.py`, a human spot check of at least 30 retained rows, quality
report, and a byte-identical rebuild.

## Judge qualification attempts

- **2026-10-21, attempt 1 — DSH subagent judge: failed.** 10/13 spent controls and 8 false
  accepts of 35; the same permissive pattern as the Strata attempts (correct flags, wrong
  semantics). No campaign batch was re-judged, no confirm was produced, and the retry
  budget is untouched. Details:
  [calibration/attempts/dsh-subagent-20261021-a2/ATTEMPT.md](calibration/attempts/dsh-subagent-20261021-a2/ATTEMPT.md).

## What this commit contains

Everything under `data/distill/stage2-v4/judge/` except transient state: campaign records
(original, consensus, r2), control audits, the 65 controls, the semantic audit and its
evidence, pool outputs, the five accepted verdicts, the rejected b05 evidence and its
diagnosis, the read-only evidence snapshots, the archived prior campaigns, and the local
judge controller (`tools/judge_v4_local.py`, `tests/test_judge_v4_local.py`).
`confirm-verdicts/` is intentionally absent (pass 2 never ran).
