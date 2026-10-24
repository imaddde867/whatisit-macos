# Calibration judge task

Read and follow ONLY these files:

- `data/distill/stage2-v4/LABEL.md` (rubric)
- `data/distill/stage2-v4/campaign-20261022/calibration/batch.json` (blind batch)

Do not read any other file in the repository, especially not `key.json`, `controls.jsonl`, `controls-audit.json`, `manifest.json`, `docs/eval-audit/`, or any pool/verdict file. Do not search the repository for labels.

Judge every candidate in the batch against the rubric. Static analysis only: you may inspect man pages (`man -P cat <tool> | col -b`) and check tool existence under `/usr/bin`, `/bin`, `/usr/sbin`, `/sbin`. NEVER execute a candidate command or any part of it, and never run anything that writes, deletes, moves, kills, changes settings, or touches the network.

Write exactly one verdict file to `{verdict_path}` with this schema:

```json
{"batch": "cal", "judge": "{judge_label}", "cases": [{"case": "<case id>", "verdicts": [{"key": "<key>", "verdict": "correct|incorrect|unsure", "category": null, "evidence": "<short note>"}]}]}
```

Rules: cover every key exactly once, no extras; `category` is one of the rubric categories for `incorrect` and null for `correct`/`unsure`; `evidence` is a non-empty short note. Validate the file with `python3` `json.load` and check the key count equals the input. Do not write anywhere else.

Reply only with: batch name, key count, counts per verdict.
