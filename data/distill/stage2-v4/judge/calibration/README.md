# Judge calibration set (2026-10-21)

Frozen before any replacement judge reads it. Purpose: decide whether a replacement
pass-1 judge is strict and consistent enough to re-judge the campaign **without** burning
the 52 live v4 controls.

Built by `tools/build_v4_judge_calibration.py` from already-paid material; scored by
`tools/score_v4_judge_calibration.py`. The machine-readable record with input/output
hashes, counts and the pre-registered pass bar is [manifest.json](manifest.json).

## What is in it

| Set | Content | Why it is legitimate |
|---|---|---|
| `controls/` | The 13 controls injected into the accepted `b00`–`b04` batches (8 expected-incorrect, 5 expected-correct), re-blinded as one batch of 13 cases | Every control is injected once, so these are **spent**: no remaining batch will ever see them. They have the live gate's difficulty and polarity mix. |
| `agreement/` | 40 cases (117 candidates) sampled from accepted `b00`–`b04` verdicts: 4 hard cases (≥1 accepted-incorrect) and 4 positive cases (all accepted-correct) per batch | Tests that the replacement judge behaves like the judge whose labels it continues. These verdicts are already decided; no remaining campaign item is used. |

Blindness: every case and key id is re-hashed with a fixed salt, so the batch files
carry only `{case, request, candidates:[{key, command}]}` — no ids, labels, provenance
or expected values. Labels live only in `controls/key.json` and `agreement/key.json`.
A judge must never be shown either key file, `controls.jsonl`, `controls-map.json`, or
the accepted verdicts.

## Pre-registered pass bar (frozen)

- **Controls: 13/13.** Any mismatch, including `unsure`, fails.
- **Agreement: ≥ 106 of 117** accepted verdicts reproduced.
- **False accepts: ≤ 2 of the 35** accepted-incorrect verdicts judged `correct`.
- **Unsure: ≤ 2** across the whole set.

Passing this is necessary, not sufficient: the next step is a single `b05` pilot against
the live controls under the revised `r3` retry plan. Failing it means trying a different
judge, not editing this set or the bar.

## Running a judge

Give the judge only the rubric (`data/distill/stage2-v4/LABEL.md`) and the batch file.
Suggested instruction template:

```
Read data/distill/stage2-v4/LABEL.md and follow it exactly. Read only that rubric
and the batch file <batch>. Do not read any other file in the repository.
For every key, decide correct / incorrect / unsure with category and short evidence.
Write ONE verdict file to <output> with exactly:
{"batch": "<batch name>", "judge": "<unique session id>", "cases": [{"case": ..., "verdicts": [{"key": ..., "verdict": ..., "category": ..., "evidence": ...}]}]}
Cover every key exactly once, no extras; validate with python3 json.load and check the
key count before finishing. Static analysis only: man -P cat <tool> | col -b and
existence checks under /usr/bin, /bin, /usr/sbin, /sbin. NEVER execute any candidate
command or any part of it; never write, delete, move, kill or use the network.
```

Then:

```sh
PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH=src:tools ~/.local/pipx/venvs/whatisit/bin/python \
  tools/score_v4_judge_calibration.py data/distill/stage2-v4/judge/calibration <verdict dir> <report.json>
```

## Limitations

- This measures strictness and consistency with the accepted judge, not absolute
  correctness. The 13 spent controls were answered by that judge once; a new judge
  clearing them is evidence, not proof.
- The 35 accepted-incorrect verdicts are the reference even where the original judge may
  itself have been strict or wrong; a genuinely better judge can lose agreement points.
