# Stage-2 v4 verified-label judge protocol (pre-registered)

Stage2-v4 keeps stage2-v3 rows whose target survives a strict blind judge and adds no-majority
corpus requests whose teacher samples include a judged-correct command
(`tools/build_verified_dataset.py`). The director builds the pool, dispatches one batch per
fresh judge, then runs the confirm and build commands. Labels come from two blind passes: every
candidate (pass 1), then a 20% sample of the selected labels (pass 2, confirm). **Model review;
not human-certified.** The rubric is the single source for judgments:
`data/distill/stage2-v4/LABEL.md`; this protocol is the runbook.

## Inputs

| Input | Path | Use |
|---|---|---|
| Corpus requests | `data/corpus/requests.jsonl` | 2,520 requests; request text for no-majority items |
| Raw teacher samples | `data/teacher/roihu_full_raw_samples.jsonl` | per-request samples; the no-majority candidate set |
| v3 train | `data/distill/stage2-v3/train.jsonl` | 1,149 rows, 902 with a command target (`v3_kept` items) |
| v3 requests | `data/distill/stage2-v3/requests.jsonl` | request text for v3 items |
| Controls | `data/distill/stage2-v4/judge/controls.jsonl` | director-built from the audited PR #33 items; expected values never revealed |

Pool scale (sanity): 902 v3 items + 1,398 no-majority requests considered (zero-candidate
requests are skipped), in 90-item batches with up to 3 controls appended per batch
(`b00`, `b01`, ...). 25 of the no-majority requests are quarantined: they are still judged; the
builder drops them at build time (`drop_quarantine`).

## Commands

Pool (director, before pass 1):

```sh
PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH=src:tools ~/.local/pipx/venvs/whatisit/bin/python tools/build_v4_pool.py data/corpus/requests.jsonl data/teacher/roihu_full_raw_samples.jsonl data/distill/stage2-v3 data/distill/stage2-v4/judge/pool --batch-size 90 --controls data/distill/stage2-v4/judge/controls.jsonl --controls-per-batch 3
```

Confirm (director, after pass 1; deterministic):

```sh
PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH=src:tools ~/.local/pipx/venvs/whatisit/bin/python tools/make_v4_confirm.py data/distill/stage2-v4/judge/pool/keymap.json data/teacher/roihu_full_raw_samples.jsonl data/distill/stage2-v3/requests.jsonl data/distill/stage2-v4/judge/verdicts data/distill/stage2-v4/judge/confirm --sample 0.2 --seed 13 --batch-size 90
```

Final build (director, after pass 2):

```sh
PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH=src:tools ~/.local/pipx/venvs/whatisit/bin/python tools/build_verified_dataset.py data/distill/stage2-v4/judge/pool/keymap.json data/distill/stage2-v4/judge/verdicts data/distill/stage2-v4/judge/confirm data/distill/stage2-v4
```

## Frozen schemas (verbatim)

```json
keymap.json: {"x0000": {"group": "v3_kept" | "no_majority", "rid": "r00042", "command": "ls -la"}}
batch file:  {"batch": "b00", "items": [{"case": "r00042", "request": "<text>", "candidates": [{"key": "x0000", "command": "ls -la"}]}]}
verdict file: {"batch": "b00", "judge": "<identity>", "cases": [{"case": "r00042", "verdicts": [{"key": "x0000", "verdict": "correct|incorrect|unsure", "category": null, "evidence": "<short note>"}]}]}
controls.jsonl line: {"key": "ct0001", "case": "CTL-01", "request": "<text>", "command": "<cmd>", "expected": "incorrect|correct", "source": "docs/eval-audit/items.json#<id>"}
```

## Pass 1 — pool verdicts (blind)

Each batch goes to a fresh judge that sees ONLY its batch file and `LABEL.md` — no scorer
labels, no source rows, no `controls-map.json`. Output: one verdict file per batch,
`data/distill/stage2-v4/judge/verdicts/<batch>.json`, schema above, every key exactly once.
A batch that is unparseable or misses/duplicates keys is redone; downstream steps never read a
partial batch.

## Pass 2 — confirm (blind)

`make_v4_confirm.py` re-derives the selected labels from the pass-1 verdicts (`v3_kept`: any
correct key; `no_majority`: the judged-correct candidates still `select()` a target), samples
20% and re-batches them with the same keys and request text. Each confirm batch goes to a
fresh judge with the same blindness and rubric; output:
`data/distill/stage2-v4/judge/confirm/<batch>.json`. A confirm verdict that is not correct
(`incorrect` or `unsure`) drops that label; the label is never re-selected and never replaced.

## Controls

Controls are graded director-side against `data/distill/stage2-v4/judge/pool/controls-map.json`;
expected values are never revealed to judges and control items carry no marker in batch files.
The audit's bar: 121/122 trap controls judged incorrect (1 unsure). A batch whose control
grading falls below that bar — at batch granularity, any mismatched control — is re-judged by a
fresh judge before its verdicts count.

## Provenance

Judge identity is recorded in the `judge` field of every verdict file; the pool and confirm
manifests, and the pool manifest sha256, are recorded with the campaign. This is model review,
not human certification, and is reported as such.

## Safety

Judges never execute candidate commands or any part of them, and never run anything that
deletes, writes (outside their verdict file), moves, kills, changes settings, or touches the
network. Some candidates are destructive; man pages and existence checks only (see `LABEL.md`).

## Failure handling

Superseded or redone batches are never edited in place: a fresh judge re-judges the batch, the
replacement file is written to the verdicts (or confirm) directory, and the previous file is
moved to `data/distill/stage2-v4/judge/superseded/` so the builder never mixes two judgments of
the same key. Re-judging a pool batch invalidates the confirm sample: re-run the confirm
command (deterministic) and re-judge the overlapping confirm batches. A judge that fails
mid-batch leaves no partial file; the batch is redone from scratch.
