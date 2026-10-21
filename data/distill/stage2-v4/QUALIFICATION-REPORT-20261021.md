# Stage-2 v4 qualification report — 2026-10-21

**Status: BLOCKED**

Campaign head: `9a327a20` on `campaign/v4-r2-20261020` (base `main` at `d2bce9f`).
Rubric: `data/distill/stage2-v4/LABEL.md`, SHA-256 `aa533cdf…`.
Runbook: `data/distill/stage2-v4/judge/protocol.md`.
Generated: 2026-10-21 ~21:30 EEST (UTC+03:00).

This report is the readiness decision for the stage-2 v4 campaign. It does not edit any
verdict, pool, control or batch file, and it does not create a dataset. `CAMPAIGN-STATUS.md`
still records the pass-1 completion claim; this report supersedes its readiness implication.

## Decision

**Do not train and do not call any labels verified.** Two independent failures block the
campaign, and the required human gate is also unmet:

1. **Population drift (fatal).** The frozen pool contains 18 candidates across 13 source
   requests that current serving validation rejects because `/dev/disk4`, `/dev/disk4s1` or
   `/dev/disk5` is absent. Both canonical downstream tools fail closed with
   `ValueError: keymap does not match the complete policy-accepted population; rebuild pool`.
2. **Pass-1 provenance (fatal).** `b06`–`b22` (17 batches, 3,770 candidates) carry judge
   identities dated 2026-10-22 but were committed on 2026-10-21. The same main-session
   judge that failed the frozen calibration bar then produced `b05`–`b22` (4,007
   candidates). No session transcript or tool log substantiates one fresh session per batch.
3. **Human gate pending (blocking).** A 40-row packet is prepared, but no human has reviewed
   the minimum 30 retained rows. A model cannot sign it.

The protocol is explicit: “A changed population fails closed at confirmation/build and
invalidates this campaign; do not silently update the pool or import old verdicts.”

## Gate results

| Gate | Result | Evidence |
|---|---|---|
| Pool and artifact digests | PASS | Manifest, keymap, controls map, director map and 23 batches match their recorded SHA-256 values. |
| Pass-1 coverage and schema | PASS | 23/23 batches, 5,176 verdicts, exact schema, every key covered once. |
| Controls | PASS with 1 contested | 64 graded controls matched; `ct0018` is contested by the r3 adjudication and is not compared. |
| Population reconstruction | **FAIL** | 18 candidates / 13 requests no longer validate; see `audit/population-drift-20261021.json`. |
| Canonical confirm | **FAIL** | Fails at `verify_population`, `build_verified_dataset.py:399`. |
| Canonical build | **FAIL** | Same failure at `build_verified_dataset.py:708`; no `verified/` output. |
| Pass-1 judge provenance | **FAIL** | 17 future-dated batches; no fresh-session evidence; calibration-failing judge. |
| Calibration | **FAIL** | 81/103 agreement, 17 false accepts, 5 false rejects against a bar of ≥93/103 and ≤2 false accepts. |
| Diagnostic label quality | CONCERN | 92.5% agreement; 12 disagreements, 8 confirmed; 2 selected targets are wrong. |
| Human review | **BLOCKED** | 40-row packet prepared, 0 reviewed. |
| Test suite | PASS | 275 tests, `OK (skipped=1)`. |
| Final reproducibility | NOT REACHED | No canonical `train.jsonl`, `audit.jsonl`, `manifest.json` or `eval_leakage_review.jsonl`. |

## 1. Population drift (fatal)

The pool was frozen against a machine state that included external media. Current
reconstruction produces:

| | Frozen pool | Current reconstruction |
|---|---:|---:|
| Items | 2,062 | 2,058 |
| Candidates | 5,111 | 5,093 |
| Excluded candidates | 1,252 | 1,270 |
| Warnings | 205 | 205 |

The difference is exactly 18 candidates across 13 requests:

- `/dev/disk4`: 8 candidates
- `/dev/disk4s1`: 9 candidates
- `/dev/disk5`: 1 candidate

13 of those candidates were selected by pass 1, across 11 requests. Ten of those requests
survive the provisional quarantine/leakage filters; four retained targets directly reference
a missing device:

| Request | Retained target | Missing path |
|---|---|---|
| `r00752` | `diskutil unmountDisk /dev/disk4` | `/dev/disk4` |
| `r01171` | `diskutil mount readOnly /dev/disk4s1` | `/dev/disk4s1` |
| `r01481` | `mount -o ro /dev/disk4s1 mountpoint` | `/dev/disk4s1` |
| `r02500` | `hdiutil detach /dev/disk5` | `/dev/disk5` |

The validation fingerprint matches the frozen environment (Darwin 27.0.0, Python 3.14,
whatisit 0.4.0, PATH hash `6e537001…`). The fingerprint does **not** capture path existence,
so a hardware change silently changes the admissible population. The pool is not stale in
the “different code” sense; it is stale in the “different machine state” sense.

Both canonical commands fail before writing anything:

```text
tools/make_v4_confirm.py ... -> ValueError: keymap does not match the complete
policy-accepted population; rebuild pool          (build_verified_dataset.py:399)
tools/build_verified_dataset.py ... -> same       (build_verified_dataset.py:708)
```

`data/distill/stage2-v4/judge/confirm/` and `data/distill/stage2-v4/verified/` do not exist.
No confirm sample was generated, so there is no official pass 2 to score.

**Why this is not patched:** creating fake device nodes, attaching arbitrary media and
calling the state restored, or weakening the validator would make the population check pass
without restoring the population. That would violate the protocol and would silently reuse
verdicts judged against different candidates. The exact original device identities are not
recorded, so a faithful restoration cannot be proven.

Machine-readable detail: `audit/population-drift-20261021.json`.

## 2. Pass-1 provenance (fatal)

`b00`–`b04` use one `gpt-6.1-sol-medium` identity per batch and are consistent with their
2026-10-20 judging date. `b05` uses `dsh-main-20261021-b05-a1`. `b06`–`b22` use
`dsh-main-20261022-bXX-a1`, but their commits are dated 2026-10-21 02:59–13:09 +0300:
**17 batches are future-dated by one day relative to their commit timestamps.**

The calibration attempt immediately before this work used `dsh-main-20261021-a1` and failed
the pre-registered bar:

| Metric | Required | Observed |
|---|---:|---:|
| Agreement | ≥ 93 / 103 | **81 / 103** |
| False accepts | ≤ 2 / 34 | **17 / 34** |
| False rejects | — | 5 / 69 |
| Unsure | ≤ 2 | 0 |

That judge (or the same `dsh-main` session family) then produced `b05`–`b22`. The repository
contains judge strings, campaign records and status text, but **no session transcript, tool
log or independent record** showing that `b06`–`b22` were 17 fresh sessions. The shared
`dsh-main` prefix and the date anomaly are not proof of fabrication by themselves, but they
are incompatible with the protocol's “fresh, uniquely identified session per batch” claim
unless corroborating evidence is produced.

Scale of the affected evidence: `b05`–`b22` = 4,007 of 5,176 verdicts (77.4%). The
calibration sample came from `b00`–`b04` accepted labels, so it measures early-batch label
quality, not late-batch quality. It does show that the main-session judge's judgments were
not reliable enough to accept without a second instrument; the diagnostic review below
confirms that the problem is not confined to the early batches.

Machine-readable detail: `audit/provenance-audit-20261021.json`.

## 3. Label quality (material concern)

### Calibration evidence

The calibration review in `judge/calibration/attempts/main-session-20261021/ATTEMPT.md`
found **8–9 demonstrable errors in a 103-item sample** (≈8%), before counting debatable
items. Examples include `stat -f "%p …"` (mode, not permissions), `plutil -p -` (reads
stdin), `lsof -Fpcfn` field parsing, and `say -v '?'` locale parsing. The accepted labels
were wrong on these; the calibration judge was right.

### Diagnostic blind review

Three fresh sessions judged 60 cases / 159 candidates from the accepted pool, with only the
batch and `LABEL.md`. They agreed with pass 1 on 147/159 = **92.5%**:

| | Diagnostic correct | Diagnostic incorrect |
|---|---:|---:|
| Pass-1 correct | 127 | 6 |
| Pass-1 incorrect | 6 | 20 |

Twelve disagreements were re-checked statically against stock man pages:

- **8 confirmed:** 4 false accepts and 4 false rejects.
- **4 probable:** 2 `signpost` false accepts (fixture not in repo) and 2 `launchctl` false
  rejects (exact output key not in the man page).

Two disagreements are the **selected target of a retained label**:

| Request | Selected target | Defect |
|---|---|---|
| `r02309` | `lsof -u $(whoami) \| awk '$5=="FIFO"'` | `man lsof` TYPE: pipes are `PIPE`; `FIFO` is a named FIFO. The request asks for open pipes. Pass 1 also rejected the correct `PIPE` variant in the same case. |
| `r01481` | `mount -o ro /dev/disk4s1 mountpoint` | `man mount`: there is no default local filesystem type; `-t` is required for a non-NFS filesystem. |

The diagnostic sample is purposive and deliberately oversamples risky cases, so 2/40 in the
human packet is not a population rate. It is enough to show that “verified” overstates the
labels and that at least two retained targets need re-judging or dropping.

The diagnostic reviewer is the same model family as pass 1 (DeepSeek V4.1 Flash Free). This
is **model review, not model-diverse ground truth and not human review**. It does not replace
pass 2.

Detail: `audit/diagnostic-20261021/RESULTS.md` and `scores.json`.

## 4. Provisional composition (not a build)

The canonical builder cannot run. Re-deriving its selection rules against the current inputs
gives a provisional composition only:

| Stage | Count |
|---|---:|
| v3 rows | 1,149 (902 commands, 247 empty) |
| Selected labels | 1,967 (847 v3 commands, 1,120 no-majority) |
| Selected quarantine rows | 23 (all no-majority) |
| Hard leakage | 204 unique requests (248 findings; 2,133 review entries) |
| Duplicate normalized requests among selected | 9 (all v3; no new-row duplicate drop) |
| v3 policy rejected | 37 |
| v3 first-pass incorrect | 18 |
| No correct candidate | 77 |
| **Provisional retained rows** | **1,993** (1,094 v3 + 899 new) |

The 1,993 figure is a local re-derivation, not a canonical artifact. It excludes the 23
quarantine rows before leakage (6 also leak), so the builder would drop 198 as leakage, not
204. The two wrong targets above are inside this provisional set.

No `train.jsonl`, `audit.jsonl`, `manifest.json` or `eval_leakage_review.jsonl` was written.
The builder refuses a non-empty output directory and fails at population verification before
any output.

## 5. Canonical commands and tests

Confirm (fails closed):

```sh
PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH=src:tools \
  ~/.local/pipx/venvs/whatisit/bin/python tools/make_v4_confirm.py \
  data/distill/stage2-v4/judge/pool/keymap.json \
  data/teacher/roihu_full_raw_samples.jsonl \
  data/distill/stage2-v3/requests.jsonl \
  data/distill/stage2-v4/judge/verdicts \
  data/distill/stage2-v4/judge/confirm \
  --sample 0.2 --seed 13 --batch-size 90 \
  --adjudication data/distill/stage2-v4/judge/control-adjudication-r3-20261021.json
```

Build (same failure; no output directory created):

```sh
PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH=src:tools \
  ~/.local/pipx/venvs/whatisit/bin/python tools/build_verified_dataset.py \
  data/distill/stage2-v4/judge/pool/keymap.json \
  data/distill/stage2-v4/judge/verdicts \
  data/distill/stage2-v4/judge/confirm \
  data/distill/stage2-v4/judge/confirm-verdicts \
  data/distill/stage2-v4/verified \
  --adjudication data/distill/stage2-v4/judge/control-adjudication-r3-20261021.json
```

Full suite:

```sh
PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH=src:tools \
  ~/.local/pipx/venvs/whatisit/bin/python -m unittest discover -s tests
```

Result: `Ran 275 tests in 2.626s`, `OK (skipped=1)`, exit 0. The suite passes; it cannot
validate a campaign that fails population reconstruction.

## 6. Human gate

`audit/human-review/` contains a 40-row packet:

- 25 `no_majority` and 15 `v3_kept` rows;
- 35 commands and 5 abstentions;
- 14 high-risk, 2 medium-risk and 19 low-risk commands;
- both known diagnostic disagreements included;
- `review.csv` blinded, `signals.csv` for post-review unblinding, `SIGN-OFF.md` template.

No human reviewer has completed it. **BLOCKED — human review pending.** The minimum is 30
rows, including at least 3 abstentions and 8 `no_majority` rows, with a named reviewer and
date. A model cannot fill these columns, and this report does not.

## 7. Required decision

The campaign cannot proceed as frozen. One of two decisions is required.

### Option A (recommended): void and rebuild

1. Freeze a new campaign revision on a recorded machine state. Record device topology, or
   exclude ambient device paths from the pool so the population does not depend on attached
   media.
2. Rebuild the pool, keymap, controls and manifest.
3. Re-judge **all** batches in fresh sessions with verifiable provenance: session identity,
   transcript or tool log, and a director record binding each batch to its session. Old
   verdicts cannot be reused against a changed pool.
4. Run the deterministic 20% confirm with genuinely independent sessions, then the canonical
   build.
5. Complete the 30-row human review and sign-off.

### Option B: restore and prove the frozen state

Restore the exact original device state (`/dev/disk4`, `/dev/disk4s1`, `/dev/disk5`) and
produce evidence that it matches the state used to build the pool; re-run the canonical
confirm and verify it reproduces the frozen selected set. Separately produce verifiable
fresh-session provenance for `b05`–`b22` (or re-judge them). If both are proven, the existing
pass 1 may be reusable. This is unlikely because the original device identities were never
recorded.

### Not acceptable

- Creating fake device nodes or attaching arbitrary disks and calling the state restored.
- Patching or weakening `verify_population` to bypass the drift.
- Reusing pass-1 verdicts after a pool rebuild.
- Treating the diagnostic review as pass 2.
- Filling the human columns with model output.
- Calling a `train.jsonl` produced by a modified builder “verified”.

## 8. What READY requires

A future report may say `READY` only when all of the following hold:

- a frozen, reproducible population that reconstructs exactly on the recorded machine state;
- complete pass-1 verdicts from verifiable fresh sessions, with controls passing;
- a complete deterministic pass-2 confirmation with independent sessions;
- canonical `make_v4_confirm.py` and `build_verified_dataset.py` succeeding on frozen inputs;
- `train.jsonl`, `audit.jsonl`, `manifest.json` and `eval_leakage_review.jsonl` with hashes
  and byte-identical re-run;
- at least 30 retained rows reviewed and signed off by a named human, with every
  disagreement resolved through re-judge/drop, not silent edits;
- full tests passing and the report recording exact commands, counts and hashes.

## 9. Reproduction and hashes

| Artifact | SHA-256 |
|---|---|
| `LABEL.md` | `aa533cdfb5bcd7d99b12a1edd41bf9c7b25fa1b3a05155603ee3533a89d7fb22` |
| `control-adjudication-r3-20261021.json` | `5e401d4f24f43cbdcc780269b0c60c7907af9780960fa6dee6ca1b6388ed2185` |
| `pool/keymap.json` | `eee680f15e7ca03ed6d53e2d0446875dee9503ee35542e220c70f0fd7a135004` |
| `pool/manifest.json` | `55e37d9e26b2d4a609fe1abcd0531cf9620c13d3ce97fe207ced2329930fa2b2` |
| `pool/controls-map.json` | `4e8976b6cba7372f2bbfdee7182ba2dc6d09cc1007fcb094f9c7c188963a8d1f` |
| `pool/director-map.json` | `128caf4bbe9c9af399de523d51bd706a20ab7de52570b1c2c9a36cecefdf9e8d` |

Validation fingerprint: Darwin 27.0.0, Python 3.14, whatisit 0.4.0, PATH hash
`6e53700166cb62101d9bcf4d31401a4b4b295fc410cfc38566d929087f94483b`.

Pass-1 verdict counts: 4,323 correct / 811 incorrect / 42 unsure (5,176 total, including 65
control verdicts). Real candidates only: 4,297 / 772 / 42 (5,111). All 42 `unsure` verdicts
are in `b00`–`b04`; `b05`–`b22` have none.

## Artifacts

- `audit/population-drift-20261021.json` — missing candidates, requests, selected/retained
  impact, exclusion reasons.
- `audit/provenance-audit-20261021.json` — per-batch judge identity, commit time, identity
  relation, calibration result.
- `audit/diagnostic-20261021/` — blind inputs, verdicts, director key, `scores.json`,
  `RESULTS.md`.
- `audit/human-review/` — `review.csv`, `signals.csv`, `README.md`, `SIGN-OFF.md`.

**Status: BLOCKED.**
