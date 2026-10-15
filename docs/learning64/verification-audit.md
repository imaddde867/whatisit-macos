# Learning64 Verification and Scoring Audit

**Branch:** `fix/learning64-verification-audit`
**Based on:** `origin/diagnostic/learning64` (commit `4af13c5`)
**Date:** 2026-10-15
**Status:** COMPLETE — reference verification executed on macOS; verification and semantic-scoring defects repaired; base + adapter rejections fully reviewed.

## Executive Summary

This audit repaired critical verification and scoring deficiencies in the
Learning64 diagnostic and re-evaluated model outputs using **macOS execution
evidence**, not static analysis alone. Headline results:

1. **Native macOS reference verification: 136/144 declared checks reproduce
   exactly.** The 8 exceptions are all `stat -f %A` permission checks whose
   frozen `check.stdout_octal` string carries a leading zero (`"0600"`); BSD
   `stat -f %A` emits three digits without it (`"600"`). This is a frozen-dataset
   *labeling* discrepancy — the reference command is correct — and it shows the
   original "144/144" claim was achievable only because the old verifier never
   enforced `stdout_octal`. The check is **not** weakened and the frozen dataset
   is **not** modified.
2. **Verifier defects repaired** (7 classes) with 28 regression tests; the
   verifier now enforces every declared check type exactly.
3. **Semantic adjudication corrected.** The previous agent's adapter
   adjudications contained several wrong verdicts (c04, c10, c12, c13, and the
   literal-`grep` cases). All 128 base and 18 adapter rejections were re-judged
   against macOS behavior.
4. **Three-state scoring** (correct / incorrect / unresolved) replaces the
   previous "unresolved = incorrect" behavior, so no false improvements or
   regressions are produced. The scorer validates adjudications and rejects
   duplicates, unknown ids, double-counted (allowlist-accepted) cases, mismatched
   model/group, contradictions, and malformed verdicts.

**Corrected lower-bound semantic scores:**
Base **115/208** (range 115–121); Adapter **198/208** (range 198–198).
Composition gains **+4 confirmed improvements** and **−4 confirmed regressions**
(c08, c09, c13, c14).

## 1. Git Commit and Dataset Provenance

- Isolated worktree: `/tmp/whatisit-learning64`, branch
  `fix/learning64-verification-audit`, base `4af13c5`.
- The primary worktree `/home/imad/GitHub/experiments/whatisit-macos` was left
  completely untouched (its unrelated modifications/untracked files are intact).
- **Frozen dataset verified unmodified.** SHA-256 of every file under
  `data/diagnostic-learning64/` matches `manifest.json` both before and after
  the audit (`git status` clean for that path; manifest check `all_match: true`
  in the macOS report).

## 2. Verifier: defects found and repaired

`tools/verify_references.py` was rewritten to enforce every declared check. The
prior agent had added most checks, but re-inspection confirmed these genuine
defects, each now fixed with a focused regression test:

| # | Defect | Repair |
|---|--------|--------|
| 1 | `stdout_stat_fields` accepted a field value appearing *anywhere* in stdout | Requires the requested fields to be the **only** whitespace tokens, **in order** |
| 2 | `stdout_inode_of` matched by substring (false-positives when the inode digits embed in a larger number) | Inode must appear as a **whole token** |
| 3 | `stdout_lines_unordered` used a `set` (lost duplicate multiplicity) | **Multiset** (`Counter`) comparison |
| 4 | `no_extra_files` only inspected regular files (`is_file`) | Detects stray **files, directories, and symlinks** |
| 5 | `apply_modes` silently skipped a declared-but-missing fixture path | Missing path is a **hard error** (`FixtureError`) |
| 6 | Fixture/check paths were not containment-validated (path traversal risk) | `safe_join` rejects absolute/`~`/`..` escapes; guards files, dirs, symlinks, modes, and check paths |
| 7 | The report's output directory might not exist before writing | `main()` creates parent directories before writing |

Additional hardening preserved/added: exact `stdout`; exact `stdout_octal`;
unknown-check-key detection; nonzero-exit enforcement; dataset-hash verification
against the manifest; and a provenance block (platform, python version, stock
PATH, run UTC, verifier hash, dataset hashes) in the JSON report.

`tests/test_verify_references.py` now runs **28 tests** (was 13), covering every
repaired defect (e.g. `test_inode_not_matched_as_substring`,
`test_unordered_preserves_duplicates`, `test_stat_fields_not_just_substring_anywhere`,
`test_no_extra_files_detects_directory`, `test_no_extra_files_detects_symlink`,
`test_apply_modes_missing_path_errors`, `test_safe_join_rejects_traversal`,
`test_output_directory_created`). All pass on Linux (logic) — the behavioral
reference proof runs on macOS below.

## 3. Native macOS Reference Verification

**Environment:** MacBook Pro M4, macOS Golden Gate **27.0.1 (26A434)**, Darwin
27.0.0 arm64, `/bin/zsh 5.9`, Python 3.9.6 (`/Library/Developer/CommandLineTools/usr/bin/python3`).
PATH for reference commands: `/usr/bin:/bin:/usr/sbin:/sbin` (stock).
The macOS `/usr/bin/python3` currently returns exit 69 (Xcode/CLT license not
accepted) and cannot run scripts; the CLT framework Python was used for the
harness only — reference commands run under stock `zsh -f` and are unaffected.

**Result: `{"total": 144, "passed": 136, "failed": 8, "all_passed": false}`**

Dataset: 208 cases deduplicated to **144 unique (reference, fixture)** combos,
each run in a fresh `/private/tmp` sandbox with no user-data access.

**The 8 failures are all `stat -f %A` permission checks:**

| id | reference | expected (`check.stdout_octal`) | actual (macOS) |
|----|-----------|----------------------------------|----------------|
| l64-005 | `stat -f %A private.txt` | `0600` | `600` |
| l64-006 | `stat -f %A shared.txt` | `0640` | `640` |
| l64-007 | `stat -f %A script.sh` | `0755` | `755` |
| l64-008 | `stat -f %A readonly.txt` | `0444` | `444` |
| l64-005-o | `stat -f %A secret.txt` | `0644` | `644` |
| l64-006-o | `stat -f %A group.txt` | `0660` | `660` |
| l64-007-o | `stat -f %A runner.sh` | `0700` | `700` |
| l64-008-o | `stat -f %A locked.txt` | `0400` | `400` |

Verified directly on the Mac: for a `chmod 0600` file, `stat -f %A` prints
`600` — BSD never emits a leading zero. The permission bits are therefore
correct; only the frozen `check.stdout_octal` literal is over-padded by one
character. Per audit policy the check is **not** relaxed and the dataset is
**not** edited, so the report faithfully records 136/144. This is itself an
audit finding: the historical 144/144 was overstated because `stdout_octal` was
among the checks the old verifier skipped.

The full per-case report (stdout/stderr/exit, per-check results, provenance,
dataset + verifier hashes) is committed at
`docs/learning64/reference-verification.json`.

## 4. Semantic evidence harness

`tools/compare_candidates.py` (macOS) recreates each rejected command's frozen
fixture in a disposable `/private/tmp` sandbox, runs the reference and then the
generated command under `zsh -f`, and records stdout/exit/stderr and resulting
file state. Safety: only commands passing a strict allowlist + deny-list scan
execute (case-insensitive path/tool checks, quote-aware pipeline split); wrong
operand / `/System` / `/etc` / wrong-tool (`shortcuts`, `man`, `history`) /
destructive commands are reported for static adjudication and never run. All
146 rejections were considered; output is committed at
`docs/learning64/candidate-comparison.json`.

## 5. Corrected semantic adjudications

`tools/adjudicate_candidates.py` regenerates the two adjudication files
deterministically from the frozen results + the macOS evidence. Rule: a rejected
command is **correct** only if it is equivalent to the reference for *any*
admitted input (verified on macOS); **incorrect** if it differs or matches only
by a fixture coincidence; **unresolved** for the BSD `wc -l` count-padding
cases whose correctness is a grader-policy choice.

- **BASE** (128 rejects): 35 correct, 87 incorrect, 6 unresolved.
- **ADAPTER** (18 rejects): 8 correct, 10 incorrect, 0 unresolved.

Adjudicated rejects per group:

| group | base rejects (C/I/U) | adapter rejects (C/I/U) |
|-------|----------------------|-------------------------|
| fit | 36 → 11 / 22 / 3 | 0 → 0 / 0 / 0 |
| paraphrase | 39 → 9 / 30 / 0 | 2 → 1 / 1 / 0 |
| operand | 39 → 9 / 27 / 3 | 4 → 3 / 1 / 0 |
| composition | 14 → 6 / 8 / 0 | 12 → 4 / 8 / 0 |

### 5.1 Previously erroneous adapter judgments (now corrected with macOS evidence)

| case | old verdict | corrected | macOS evidence |
|------|-------------|-----------|----------------|
| l64-c04 | correct | **incorrect** | `sort -n -k 3 totals.txt` outputs whole lines, not extracted field 3; stdout differs |
| l64-c10 | incorrect | **correct** | `sort -u … \| grep 'WARN'` commutes with `grep \| sort -u`; identical output |
| l64-c12 | correct | **incorrect** | `find … -print0 \| sort -z`: `sort -z` exists on macOS 27 but emits **NUL**-delimited pathnames (`\x00`), not the newline list the request defines |
| l64-c13 | correct | **incorrect** | `stat -f %z %i object.bin` (unquoted) → `stat` treats `%i` as a filename: `stat: %i: No such file or directory`, exit 1 |
| l64-033-p / -033-o / -034-o / -035-o | incorrect | **correct** | `grep 'ERROR'`/`'disk'`/`'start'`/`'timeout'` — literal patterns with **no regex metacharacters**, so basic-regex == fixed-string for these; identical output (the task's "regex mode ≠ different matching behavior") |
| l64-c16 | correct | **correct** (re-confirmed) | `cut -d: -f2 … \| grep -c 'ready'` == `grep -Fc 'ready'` for the literal `ready` |

### 5.2 Base double-counting removed

The prior base audit adjudicated **c13 and c14 as "false negatives."** They were
in fact **allowlist-accepted** (the two base-composition accepts). Adjudicating
accepted outputs double-counts them, so they were removed from the
base-adjudications. The scorer additionally **rejects** any adjudication for a
case that was not rejected (regression-tested).

### 5.3 Unresolved (6 base cases)

`sed … | wc -l` count pipelines compute the **correct count**, but macOS BSD
`wc -l` right-pads the integer with leading spaces (`"       1"` vs reference
`"1"`). Whether that is acceptable is a grader-policy choice, so these are
`unresolved`: l64-037, l64-038, l64-040 (fit), l64-037-o, l64-039-o, l64-040-o
(operand). They are held out of any improvement/regression.

## 6. Scorer: three-state semantics

`tools/rescore_learning64.py` scores each case as **correct** (allowlist-accepted
or adjudicated correct), **incorrect** (adjudicated incorrect), or
**unresolved** (adjudicated unresolved, or rejected with no adjudication). Paired
base↔adapter comparisons are conservative:

- improvement ⇐ base confirmed **incorrect** AND adapter confirmed **correct**;
- regression ⇐ base confirmed **correct** AND adapter confirmed **incorrect**;
- if either side is unresolved the pair is reported separately and never counts.

The scorer rejects duplicate / unknown / missing-source / mismatched-model /
mismatched-group / contradictory / malformed verdicts (9 regression tests in
`tests/test_rescore_learning64.py`), and is deterministic across runs.

### Corrected scores by group (three-state)

| group | model | allowlist | +adjudicated | confirmed correct | incorrect | unresolved | range |
|-------|-------|-----------|--------------|-------------------|-----------|------------|-------|
| fit | base | 28/64 | +11 | 39/64 | 22 | 3 | [39, 42] |
| fit | adapter | 64/64 | 0 | 64/64 | 0 | 0 | [64, 64] |
| paraphrase | base | 25/64 | +9 | 34/64 | 30 | 0 | [34, 34] |
| paraphrase | adapter | 62/64 | +1 | 63/64 | 1 | 0 | [63, 63] |
| operand | base | 25/64 | +9 | 34/64 | 27 | 3 | [34, 37] |
| operand | adapter | 60/64 | +3 | 63/64 | 1 | 0 | [63, 63] |
| composition | base | 2/16 | +6 | 8/16 | 8 | 0 | [8, 8] |
| composition | adapter | 4/16 | +4 | 8/16 | 8 | 0 | [8, 8] |
| **overall** | base | 80/208 | +35 | **115/208** | 87 | 6 | [115, 121] |
| **overall** | adapter | 190/208 | +8 | **198/208** | 10 | 0 | [198, 198] |

### Confirmed paired changes

**Total: +81 improvements, −4 regressions, 6 unresolved pairs.**

Composition is the only group with regressions, all confirmed on macOS:

| case | base | adapter | why |
|------|------|---------|-----|
| l64-c08 | correct (`head -3 … \| grep 'ERROR'`) | incorrect (`grep -E 'ERROR'` scans whole file) | scope lost |
| l64-c09 | correct (`awk -F: 'NR>1 {print $2}'`) | incorrect (`cut -d: -f2` keeps header) | header not skipped |
| l64-c13 | correct (allowlist; `stat -f '%z %i'`) | incorrect (unquoted `stat -f %z %i`, exit 1) | stat quoting dropped |
| l64-c14 | correct (allowlist; sed + `shasum`) | incorrect (sed only, missing `shasum`) | checksum dropped |

Composition improvements: **c07, c10, c15, c16** (base incorrect → adapter correct).

## 7. What the corrected evidence establishes

1. **Fit is firmly established:** adapter 64/64 vs base 39/64 (lower bound).
2. **Generalization improved and is larger than the old report showed:** base's
   true lower bound is 115/208 (≈55%), not the 38.5% allowlist rate — the model
   produced many semantically correct variants (`head -3`, `<(...)`, `sed -n`
   ranges, literal `grep`) the strict allowlist rejected.
3. **Adapter regressions are now precisely characterised:** 4 confirmed
   composition regressions (c08, c09, c13, c14), all verified on macOS. The
   adapter dropped a scope limiter (c08/c09), dropped `shasum` (c14), and dropped
   `stat -f` format quoting (c13). These are genuine losses of correct behaviour,
   not artifacts of strict scoring.
4. **No false delta from uncertainty:** the 6 unresolved base cases are excluded
   from every improvement/regression, so +81/−4 are confirmed counts.

## 8. Reproduction

```bash
# 0) isolate a worktree (do not touch the primary worktree)
git worktree add /tmp/whatisit-learning64 fix/learning64-verification-audit
cd /tmp/whatisit-learning64

# 1) verifier regression tests (platform-agnostic logic)
python3 tests/test_verify_references.py          # 28 passed
python3 tests/test_rescore_learning64.py         # 9 passed

# 2) stage for the Mac (dataset + tools), transfer to /private/tmp/l64verify
scp tools/verify_references.py tools/compare_candidates.py \
    imadeddine@macbook-pro:/private/tmp/l64verify/tools/
scp data/diagnostic-learning64/*.jsonl dataset/manifest.json \
    imadeddine@macbook-pro:/private/tmp/l64verify/dataset/

# 3) execute references natively on the Mac (CLT python; stock PATH; zsh -f)
ssh imadeddine@macbook-pro \
  '/Library/Developer/CommandLineTools/usr/bin/python3 /private/tmp/l64verify/tools/verify_references.py \
   /private/tmp/l64verify/dataset /private/tmp/l64verify/reference-verification.json'
scp imadeddine@macbook-pro:/private/tmp/l64verify/reference-verification.json \
   docs/learning64/reference-verification.json

# 4) execute each rejected candidate on macOS fixtures for evidence
#    (candidates.json = the 146 rejected generated commands from the frozen results)
ssh imadeddine@macbook-pro \
  '/Library/Developer/CommandLineTools/usr/bin/python3 /private/tmp/l64verify/tools/compare_candidates.py \
   /private/tmp/l64verify/dataset /private/tmp/l64verify/candidates.json \
   /private/tmp/l64verify/candidate-comparison.json'
scp imadeddine@macbook-pro:/private/tmp/l64verify/candidate-comparison.json \
   docs/learning64/candidate-comparison.json

# 5) regenerate adjudications from frozen results + evidence, then rescore
python3 tools/adjudicate_candidates.py
python3 tools/rescore_learning64.py
```

### Test results
- `tests/test_verify_references.py` — 28 passed (verifier + repaired-defect regressions)
- `tests/test_rescore_learning64.py` — 9 passed (three-state, validation, determinism)
- `tests/test_eval_learning64.py`, `tests/test_eval_semantics.py` — 9 each, unchanged, OK

### Hashes
- Verifier used on macOS (`verify_references.py`):
  `b4a8f0120ef7d0f146c5ece9d3930c2416a558c26722128b3e2c5b5690e170f9`
  (matches `provenance.verifier_sha256` in `reference-verification.json`).
- Frozen dataset: all six files match `manifest.json` (unchanged); see
  `PROTOCOL.md`, `eval_*.jsonl`, `train.jsonl` digests in
  `docs/learning64/reference-verification.json` → `provenance.dataset_files_sha256`
  and `manifest_check`.

### Artifacts committed
`tools/verify_references.py`, `tools/compare_candidates.py`,
`tools/adjudicate_candidates.py`, `tools/rescore_learning64.py`,
`tests/test_verify_references.py`, `tests/test_rescore_learning64.py`,
`docs/learning64/semantic-adjudications.json`,
`docs/learning64/base-adjudications.json`,
`docs/learning64/rescored-detailed.json`,
`docs/learning64/reference-verification.json`,
`docs/learning64/candidate-comparison.json`, this report.

## 9. Limitations

1. **`stat -f %A` dataset labels:** 8 permission checks declare a leading-zero
   octal the platform does not emit. Recorded, not "fixed" (dataset frozen;
   check not weakened). If the dataset owner wants 144/144, the eight
   `check.stdout_octal` values should be corrected to the 3-digit BSD form.
2. **6 unresolved** base `wc -l` count cases (BSD padding) remain open pending a
   grader-policy decision on leading whitespace.
3. macOS runs used the `/Library/Developer/CommandLineTools/usr/bin/python3`
   interpreter (3.9.6) because `/usr/bin/python3` is license-blocked; this
   affects only the harness, not the reference commands.

## 10. Conclusion

The Learning64 verification system previously over-claimed 144/144 and
mis-scored several outputs. Against genuine macOS execution the corrected
verifier reports **136/144** (8 octal-label discrepancies surfaced), the
semantic audit establishes confirmed lower bounds of **base 115/208** and
**adapter 198/208**, and paired comparison confirms **+81 improvements and −4
regressions** (c08, c09, c13, c14) with 6 unresolved cases honestly excluded.
Fit is established and adapter generalization is strong, with precisely
characterised composition regressions. The path to 144/144 is a dataset-only fix
(remove the 8 leading zeros); nothing here weakens a check or hides uncertainty.
