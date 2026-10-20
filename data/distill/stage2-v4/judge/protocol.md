# Stage-2 v4 verified-label judge protocol (pre-registered)

Stage2-v4 keeps stage2-v3 rows whose target passes the shared serving policy and a strict blind judge, and adds
no-majority corpus requests whose teacher samples include a judged-correct command
(`tools/build_verified_dataset.py`). The director builds the pool, dispatches one batch per
fresh judge, then runs the confirm and build commands. Labels come from two blind passes:
every candidate (pass 1), then a deterministic 20% sample of the selected labels (pass 2,
confirm). **Model review; not human-certified.** The rubric is the single source for
judgments: `data/distill/stage2-v4/LABEL.md`; this protocol is the runbook.

## Inputs

| Input | Path | Use |
|---|---|---|
| Corpus requests | `data/corpus/requests.jsonl` | 2,520 requests; request text for no-majority items |
| Raw teacher samples | `data/teacher/roihu_full_raw_samples.jsonl` | per-request samples; no-majority candidates, serving-validated at pool time |
| v3 train | `data/distill/stage2-v3/train.jsonl` | 1,149 rows, 902 with a command target (`v3_kept` items) |
| v3 requests | `data/distill/stage2-v3/requests.jsonl` | request text for v3 items |
| Controls | `data/distill/stage2-v4/judge/controls.jsonl` | 65 director-built controls: 25 expected-correct, 40 expected-incorrect; values never revealed |
| Rubric | `data/distill/stage2-v4/LABEL.md` | the only judgment rubric |

Historical pool scale before issue #35 (requires regeneration; these are not current-policy counts), as built with `--batch-size 90 --controls-per-batch 3 --control-seed 13`:
902 v3 items + 1,275 no-majority requests with admissible candidates = 2,177 items,
5,640 candidates, 25 batches (`b00`–`b24`). 1,398 corpus ids outside v3 are considered;
19 candidate pairs (9 requests) fail serving validation and are excluded at pool time
(`manifest.json` `excluded_candidates`; judges never see them), and requests with no
admissible candidates are skipped with a manifest warning. All 65 controls are injected:
every batch contains at least one expected-correct and one expected-incorrect control.
25 non-v3 requests are quarantined: the pool does not pre-filter them (they are judged when
they have candidates; `r00849` has no admissible candidate), and the builder drops each one
with a selected target at build time (`drop_quarantine`; 24 in the current pool).

Issue #35 applies the same bounded parser, lint, upstream DANGER, placeholder and
lexical deletion checks to every non-empty v3 target and new candidate. Validation
receives request text and the structured `path` separately; the explicit-inputs line
is formatting for judge/training prompts only. Unsupported shell syntax fails closed.
Rejected v3 targets are excluded from the pool and audit-dropped from the final build,
never changed into abstentions. Existing empty v3 targets remain unchanged.

Pool `excluded_candidates` records bounded, escaped validation reasons, including v3
exclusions; `counts.v3_policy_rejected` counts rejected historical commands. Pool,
confirm and final manifests carry the validation code and environment fingerprint.
The fingerprint hashes local validation code, Python/platform, PATH (digest only),
and upstream distribution version; upstream source is hashed only inside the task
workspace or outside `/home`. A home-installed dependency outside the workspace is
marked `source_outside_task_workspace`, so its local source edits are not detected.
Confirm and final stages reject stale fingerprints and reconstruct the complete
policy-accepted candidate population and exclusion list before sampling or building.
Regenerate the pool, judgments and confirmation after any policy/environment change;
historical source datasets and campaign artifacts remain immutable. No new campaign
counts or acceptance claim are established by the code update.

The expected-correct controls `ct0061`–`ct0065` come from audited PR #33
items that passed both the original blind pass and the independent pass-2 review:
`x0283`, `x0509`, `x0520`, `x0540`, `x0571` in `docs/eval-audit/items.json`. Their
`provenance` fields name the exact pass-2 file, marker, key and verdict (for example
`docs/eval-audit/pass2-opus/r0.json m012 x0283 correct (pass1 b07 correct)`). The
consensus replacements described below carry the same provenance format; unchanged
controls retain their original source references.

## Commands

Pool (director, before pass 1):

```sh
PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH=src:tools ~/.local/pipx/venvs/whatisit/bin/python tools/build_v4_pool.py data/corpus/requests.jsonl data/teacher/roihu_full_raw_samples.jsonl data/distill/stage2-v3 data/distill/stage2-v4/judge/pool --batch-size 90 --controls data/distill/stage2-v4/judge/controls.jsonl --controls-per-batch 3 --control-seed 13
```

Confirm (director, after pass 1; deterministic):

```sh
PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH=src:tools ~/.local/pipx/venvs/whatisit/bin/python tools/make_v4_confirm.py data/distill/stage2-v4/judge/pool/keymap.json data/teacher/roihu_full_raw_samples.jsonl data/distill/stage2-v3/requests.jsonl data/distill/stage2-v4/judge/verdicts data/distill/stage2-v4/judge/confirm --sample 0.2 --seed 13 --batch-size 90
```

Final build (director, after pass 2):

```sh
PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH=src:tools ~/.local/pipx/venvs/whatisit/bin/python tools/build_verified_dataset.py data/distill/stage2-v4/judge/pool/keymap.json data/distill/stage2-v4/judge/verdicts data/distill/stage2-v4/judge/confirm data/distill/stage2-v4/judge/confirm-verdicts data/distill/stage2-v4/verified
```

All three tools refuse a non-empty output directory. Move a previous run aside before
re-running. Final artifacts go under `verified/` because the stage2-v4 root already
contains the rubric and judge inputs.

## Blind identifiers

Every judge-visible case and candidate uses an opaque, uniform identifier: cases are
`c` + 12 lowercase hex digits and candidate keys are `k` + 12 lowercase hex digits. Real
items and controls use the same format. Identifiers are derived deterministically with
SHA-256 from `control-seed`, the item group and the source identity, so a rerun with the
same inputs and seed is byte-identical. Source ids (`r####`), control ids (`ct####`),
control labels (`CTL-##`) and groups never appear in a batch file.

Three director-only maps are written beside the batches:

- `keymap.json`: opaque real candidate key -> `{case, group, rid, command, count}`.
- `controls-map.json`: opaque control key -> `{case, expected, source, request, command,
  origin_case, origin_key, provenance?}`.
- `director-map.json`: opaque case -> true identity and, for controls, the expected value
  and provenance.

Judges receive only a batch file and `LABEL.md`. They never receive any of these maps.

## Frozen schemas

```json
keymap.json: {"k0123456789ab": {"case": "c0123456789ab", "group": "v3_kept" | "no_majority", "rid": "r00042", "command": "ls -la", "count": 1}}
batch file:  {"batch": "b00", "items": [{"case": "c0123456789ab", "request": "<text>", "candidates": [{"key": "k0123456789ab", "command": "ls -la"}]}]}
verdict file: {"batch": "b00", "judge": "<unique session identity>", "cases": [{"case": "c0123456789ab", "verdicts": [{"key": "k0123456789ab", "verdict": "correct|incorrect|unsure", "category": null, "evidence": "<short note>"}]}]}
controls.jsonl line: {"key": "ct0001", "case": "CTL-01", "request": "<text>", "command": "<cmd>", "expected": "correct|incorrect", "source": "docs/eval-audit/items.json#<id>", "provenance": "<optional source evidence>"}
```

Verdict `category` is required (one of the rubric categories) for `incorrect` and must be
null for `correct` and `unsure`; `evidence` is always a non-empty string. A verdict file must
contain exactly `batch`, `judge`, `cases`; each case exactly `case`, `verdicts`; each verdict
entry exactly `key`, `verdict`, `category`, `evidence`. Every batch, case and candidate key is
covered exactly once with no unknown, misplaced, duplicated or missing entries.

## Pass 1 — pool verdicts (blind)

Each batch goes to a fresh judge that sees ONLY its batch file and `LABEL.md` — no scorer
labels, no source rows, no control or director maps. The `judge` field is a unique session
identity for that judging run (model plus a session suffix); an identity is never reused
across batches or passes. Output: one verdict file per batch,
`data/distill/stage2-v4/judge/verdicts/<batch>.json`, schema above. The director writes the
verdicts directory before the first judge and does not read a partial batch downstream.
Control verdicts are graded per batch: every control must match its expected value, so each
batch must contain at least one correct and one incorrect control and every control in the
batch must be graded correctly. A mismatched or missing control fails the build; the batch is
re-judged by a fresh judge.

## Pass 2 — confirm (blind)

`make_v4_confirm.py` verifies the pool manifest, keymap, maps and artifact digests, strictly
re-loads pass 1, and re-derives the selected labels with the same rules as the builder
(`v3_kept`: any correct key; `no_majority`: the judged-correct candidates still `select()` a
target). It samples exactly `round(selected * 0.2)` labels with `random.Random(seed)`, sorts
the picked items by opaque case id, and writes `b00`, `b01`, ... plus `manifest.json` into
`data/distill/stage2-v4/judge/confirm/`. Confirm batches carry the same opaque ids, candidate
keys, requests and commands as the pool; director metadata (`group`, `rid`) is stripped. The
manifest records the exact selected and sampled identities and SHA-256 digests of the pool,
keymap, raw samples, v3 requests, both quarantine lists, pass-1 verdicts and generated
batches.

Each confirm batch goes to a fresh judge with the same blindness and rubric; its session
identity must differ from the pass-1 session that judged every case it confirms (the
builder fails on reuse and records the session sets and per-case pairing digest). Output:
`data/distill/stage2-v4/judge/confirm-verdicts/<batch>.json` — a sibling of `confirm/`, so
`load_verdicts()` never reads the batch inputs. A confirm verdict that is not correct
(`incorrect` or `unsure`) drops that label; the label is never re-selected and never replaced.
A missing confirm verdict, an extra verdict outside the sample, a changed confirm batch or a
manifest that does not recompute exactly from the pass-1 selection fails the build.

## Controls

Revision `20261020-r2` supersedes the historical-consensus checkpoint. Every control
must match its exact source request and command, have both historical audit passes
agree with its expected verdict, and have a request-based rationale supported by
the rubric and judges' permitted documentation. Historical agreement alone does
not settle unstated scope, interface, interaction or word-matching assumptions, or
undocumented output fields.

The director registered the selection rule and retry budget in
`control-audit-r2-20261020.json`. Eleven unsuitable controls are replaced; `ct0006`
and `ct0022` retain their expected-incorrect verdicts. For `ct0006`, a filename
containing a newline gives a concrete counting defect in `find . -type f | wc -l`;
this retention does not add an unstated direct-child scope to the request.
`ct0022` invents the operand `project_folder` without request support.

Control positions, case/key names and polarities stay fixed. Traverse unused
historical source IDs in ascending order separately per polarity, assigning them
to replaced controls in ascending control-key order. Exclude sources used in either
prior checkpoint and duplicate request/command pairs. Record each rejected source
and its rationale before selecting the next eligible source. Check only the new
replacements before freezing; do not repeat whole-control audits until a model
agrees. The audit records every old/new mapping and historical provenance.

The initial campaign and the consensus checkpoint are preserved under
`superseded/campaign-original-20261020/` and
`superseded/campaign-consensus-20261020-r1/`. Revision r2 regenerates the pool and
starts all pass-1 judgments with fresh sessions; no verdicts are reused. No control
edits occur in response to r2 judge failures. Allow one fresh retry per failed
batch. Stop if that retry fails or total failed attempts reach three. Count schema,
coverage, control and incomplete-attempt failures in r2; prior revisions do not
consume this budget. Stopping never relaxes the all-controls gate.

Before judging, verify byte-identical repeated pool generation and hold the
validation environment, including device/mount state, constant through confirmation
and final build. The fingerprint does not capture path existence. A changed
population fails closed at confirmation/build and invalidates this campaign; do
not silently update the pool or import old verdicts.

Controls are graded director-side against
`data/distill/stage2-v4/judge/pool/controls-map.json`; expected values are never revealed to
judges. The builder does not trust the maps' digests alone: it recomputes every control
entry (expected verdict, command, request, provenance, deterministic opaque case/key ids)
from `controls.jsonl` and the `control-seed`, and the director map from the keymap and
controls map. Any mismatch fails the build. Allocation is seeded and stratified: one
expected-correct and one expected-incorrect
control per batch, then the remaining controls are shuffled into the remaining per-batch
slots. Total controls must fit the pool capacity and both polarities must be sufficient for
every batch; over-capacity or under-supply fails, never warns. Every control is accounted for:
the pool manifest records `controls_total`, `controls_injected`, the polarity counts and the
per-batch summary, and the builder recomputes the per-batch summary from the batch files and
control map. A control whose verdict does not match its expected value fails the build. The
audited PR #33 review bar was 121/122 trap controls judged incorrect (1 unsure); v4 requires
every control in a batch to grade correctly before that batch counts.

## Audit

The final builder writes `audit.jsonl` with one entry per considered id. Action values:

- `keep_v3` — v3 row kept (including an empty target, kept unchanged).
- `drop_v3_policy_rejected` — non-empty v3 target fails current serving policy; reason recorded.
- `drop_v3_first_pass_incorrect` — v3 target judged not correct in pass 1.
- `drop_v3_second_pass_rejected` — v3 target rejected in the pass-2 confirm sample.
- `drop_second_pass_rejected` — selected no-majority label rejected in pass 2.
- `drop_no_correct` — no candidate judged correct in pass 1.
- `drop_quarantine` — request on a quarantine list (after candidate selection).
- `drop_duplicate_request` — normalized request already used by an earlier accepted row;
  `duplicate_of` names the first accepted id.
- `drop_eval_leakage` — hard eval leakage; does not reserve a duplicate identity.
- `add_verified` — new row with a selected judged-correct target.

Review-level leakage findings (request similarity 0.5–0.7 or shared tool+flags) are preserved
in `eval_leakage_review.jsonl` and repeated in the final manifest; hard-leakage rows are
dropped and audited as `drop_eval_leakage`. Leakage is evaluated once over all preliminarily accepted candidates
before the duplicate seen-set is updated, so a hard-leaked duplicate cannot suppress a later
clean row with the same normalized request.

## Provenance

Each verdict file records a unique judge-session identity in `judge`. The pool manifest
records SHA-256 digests of the corpus, raw samples, v3 train/requests and controls inputs plus
every generated pool artifact (keymap, controls map, director map, each batch). The confirm
manifest records the exact selected/sample identities and digests of the pool, keymap, raw
samples, v3 requests, both quarantine lists, pass-1 verdicts and confirm batches. The final
build re-verifies all of those digests, the control coverage, the recomputed controls and
director maps, the exact 20% sample, and the pass-1/pass-2 session independence before writing
anything, and its own manifest records the SHA-256 of every input (including pass-1/confirm
verdict files, both quarantine lists and all four eval splits), the judge-session sets with a
per-case pairing digest, and the SHA-256 of its outputs (`train.jsonl`, `audit.jsonl`,
`eval_leakage_review.jsonl`). Identical frozen
inputs, seed and judgments produce byte-identical outputs. This is model review, not human
certification, and is reported as such.

## Safety

Judges never execute candidate commands or any part of them, and never run anything that
deletes, writes (outside their verdict file), moves, kills, changes settings, or touches the
network. Some candidates are destructive; man pages and existence checks only (see `LABEL.md`).

## Failure handling

The director creates `data/distill/stage2-v4/judge/verdicts/`,
`data/distill/stage2-v4/judge/confirm-verdicts/` and `data/distill/stage2-v4/judge/superseded/`
before they are first written to. Superseded or redone batches are never edited in place: a
fresh judge re-judges the batch, the replacement file is written to the verdicts (or
confirm-verdicts) directory, and the previous file is moved to
`data/distill/stage2-v4/judge/superseded/` so the builder never mixes two judgments of the
same key. Re-judging a pool batch invalidates the confirm sample: re-run the confirm command
(deterministic) and re-judge the overlapping confirm batches. A judge that fails mid-batch
leaves no partial file; the batch is redone from scratch.

The final builder is fail-closed: it refuses stale or tampered pool artifacts, changed
inputs, incomplete verdict coverage, duplicate/unknown keys, malformed verdict schema,
control mismatches, a controls or director map that does not recompute from `controls.jsonl`,
a confirm case judged by its own pass-1 session, a quarantine list changed after confirmation,
a confirm batch or manifest that does not recompute exactly, missing or
extra confirm verdicts, an empty confirmation sample, a non-empty output directory, a pool
without controls, or an unverifiable output. Any re-run writes into a fresh or emptied
directory — `pool/`, `confirm/`, `verdicts/` and `confirm-verdicts/` alike — so stale
`bXX.json` files are never read as current.
