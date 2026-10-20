# Calibration attempt 2 — main-session judge (2026-10-21)

**Result: FAILED against the frozen agreement bar — and the failures show the reference
labels are noisy, not only the judge. No `b05` attempt was consumed.**

## Setup

The first calibration set had already been read during the attempt-1 post-mortem, so it
could not be reused for a blind run. A **fresh** set was built from accepted `b00`–`b04`
cases that had not been inspected, with the same construction rule and a new seed
(`20261022`): 40 cases, 103 candidates (34 accepted-incorrect, 69 accepted-correct), split
into two blind batches. Bar frozen before judging: agreement ≥ 93/103, false accepts ≤ 2
of 34, unsure ≤ 2.

Inputs, key and verdicts are in this directory. All candidates were judged with man-page
and command-output evidence; no candidate command was executed.

## Score

| Metric | Required | Observed |
|---|---|---|
| Accepted verdicts reproduced | ≥ 93 / 103 | **81 / 103** |
| False accepts (accepted-incorrect → correct) | ≤ 2 / 34 | **17 / 34** |
| False rejects (accepted-correct → incorrect) | — | 5 / 69 |
| Unsure | ≤ 2 | 0 |

By the pre-registered bar this is a clear failure. The disagreement review, however,
splits into three groups.

## Disagreements where the accepted label is demonstrably wrong

Verified on this Mac:

- `k09a` `stat -f "%p %Su %z %n"` — `%p` prints `100644`; that is the file mode. Accepted
  verdict: incorrect.
- `k2bd7` `plutil -p -` — `-` reads stdin; verified with a piped plist. Accepted: incorrect.
- `k5a27` `lsof -Fpcfn …` — field output is `p<pid>`, `c<cmd>`, `f<fd><mode>`, `n<name>`;
  the awk parses it correctly. Accepted: incorrect.
- `k61a`, `k88a` `say -v '?' | awk '$2 ~ /^en/ …'` — the listing is
  `Name<space>locale<space># comment`; `$2` is the locale. Accepted: incorrect.
- `k890` `git submodule status --cached -- project/` — `--cached` is documented for
  `status`. Accepted: incorrect.
- `kf456` `plutil -extract RecentFiles xml1 -o - … | sed …` — verified to print the
  string values. Accepted: incorrect.
- `k473` `tmutil latestbackup` — documented verb that prints the latest backup path
  (on this Mac it warns about mounting a destination; the verb is still valid).
  Accepted: incorrect.
- `kccef` `lsof -w report.pdf | awk 'NR==1 || $4 ~ /[wu]$/'` — valid lsof flags and FD
  filter. Accepted: incorrect.

That is 8–9 demonstrable errors in a 103-item random sample (≈8%), before counting the
debatable ones.

## Disagreements where my verdict was wrong

- `k0f1` `lsof -a -d w report.pdf` — `-d w` selects write-only descriptors; a
  read-write descriptor has mode `u` and is missed. The accepted "incorrect" is right.
- `kd9d` `find test-keys -maxdepth 1 …` — the request reads as recursive; the accepted
  "incorrect" is defensible.
- `k1b10`, `k3aed`, `kd75b` — "check whether Tool.app has the get-task-allow entitlement"
  is a presence question, so a key-presence grep is correct; I over-read it as a value
  check.
- `k5d29`, `k632e` — if "a literal square bracket" means `[`, matching only `[` is
  correct; I required both brackets.

## Disagreements that are genuinely debatable

`k62f`, `k8f8`, `kcc7` (awk range matches `START` anywhere in a line), `k7a96`
(`arp -a | grep en0` is loose), `kf5bc` (`grep -A100` prints much more than the
entitlement), `k971` (`-d w,u` versus `-d w`).

## What this means

- The bar as frozen (≈100% on 34 hard negatives) cannot be met by an independent judge
  when the reference itself contains ~8% errors. This is not a judge-selection result;
  it is a **label-quality result for the accepted pass-1 verdicts**.
- The campaign's live control gate is built from the same audit-derived material. A
  strict per-batch 100% gate will fail honest judges on contested controls — which is
  consistent with the two Strata failures, the subagent failure, and this run.
- The pass-1 labels are still far better than the exact-string majority they replace
  (which produced no label at all for 31% of cases), but "verified" overstates them.

## Disposition

- No `b05` attempt was consumed; the retry budget is untouched.
- The 20% confirm pass, if it ever runs, is the designed instrument for measuring this
  error rate; it cannot run until pass 1 is complete.
- Recommended before more judging: either adjudicate the live controls with hard evidence
  and let the gate tolerate contested items, or change the label protocol to require two
  independent judges per selected label with adjudication of disagreements.
