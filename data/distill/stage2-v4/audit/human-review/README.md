# Human review packet — stage-2 v4 (prepared 2026-10-21, unreviewed)

This packet supports the human gate in issue #36: **at least 30 retained rows must be
spot-checked by a human** before a v4 dataset can be called training-ready. It is prepared
but **not reviewed**. No `human_verdict` or `human_notes` value has been filled in.

## Files

- `review.csv` — the blinded review sheet. Fill `human_verdict` and `human_notes`.
- `signals.csv` — pass-1 and diagnostic signals, joined by `review_id`. Do not open this
  until the 40 verdicts are written; it is included for the later disagreement review.
- `SIGN-OFF.md` — the sign-off template.

## Sample

40 retained rows: 25 `no_majority` (new v4) and 15 `v3_kept`; 35 commands and 5
abstentions; 14 high-risk, 2 medium-risk and 19 low-risk commands. The sample is
**purposive**, not random: it deliberately includes the two known diagnostic disagreements
(`r02309`, `r01481`), device-dependent labels, destructive commands, compound commands and
five abstentions. It is a semantic spot-check, not a population error-rate estimate.

Every row is a label that survived pass-1 selection and the provisional quarantine/leakage
filters. The canonical builder cannot currently run (population drift), so these are
**provisional** retained rows, not a `verified/train.jsonl`.

## How to review

1. Read `request`, then `target_command` (or `kind=abstain`). Judge only from the frozen
   rubric: `data/distill/stage2-v4/LABEL.md`.
2. **Never execute a candidate command or any part of it.** Use `man -P cat <tool> | col -b`,
   `ls` under the stock PATH, and read-only probes only. Some commands delete or overwrite.
3. Write one verdict per row:
   - `correct` — the command does exactly what the request asks on stock macOS, or (for an
     abstention) refusing/abstaining is the right behavior for a vague, destructive or
     unanswerable request.
   - `incorrect` — wrong syntax, wrong tool, missed constraint, wrong output, unsafe, or an
     abstention where a safe standard command clearly answers the request.
   - `unsure` — only if the request or fixture is genuinely insufficient; say what is
     missing in `human_notes`.
4. Keep notes short and concrete. If a row is wrong, do not edit the label; record the
   failing fact so the director can re-judge or drop it through the documented route.
5. Open `signals.csv` only after all verdicts are written. Record any disagreement with
   pass 1 / the diagnostic review in `SIGN-OFF.md`.

## Minimum gate

- Review at least **30 of 40** rows, including at least 3 abstentions and 8 no_majority rows.
- A named human reviewer signs `SIGN-OFF.md` with the date and the rows reviewed.
- Any `incorrect` verdict blocks READY until the label is re-judged or dropped and the
  report is updated.
- Model output must not fill these columns. A model may prepare the packet; it cannot be
  the human reviewer.

## Why this packet is not the official pass 2

The official pass 2 is the deterministic 20% blind confirmation in
`data/distill/stage2-v4/judge/confirm/`, judged by fresh sessions with a different identity
from pass 1. This packet is a human semantic check of already-selected labels. It does not
replace pass 2, and pass 2 cannot run until the population drift is resolved.
