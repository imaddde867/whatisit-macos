# Stage-2 dataset repair v2

Source: 1075 historical rows plus 36 authored additions; retained: 1091 (843 commands, 248 abstentions, 22.7%).
Actions: `{"clarified_request": 12, "corrected_target": 10, "exclude": 20, "explicit_path": 24, "keep": 940, "model_authored_addition": 27, "natural_abstain": 78}`. Only `keep` rows are unchanged teacher evidence. `explicit_path`, `natural_abstain` and `clarified_request` keep the teacher target for a rewritten request the teacher never saw; `clarified_request` rows are command requests reworded to state the scope of the existing command. Corrected targets record votes for the new target (`teacher_votes`) and the old one (`original_target_votes`). Every training and request row carries `source_id` so family derivatives remain grouped when the trainer reads `train.jsonl` alone.

Training SHA-256: `91431de67f15232d3ec83361bd8fe6b176e10d21617b4611089de8db238081aa`.
All input, output and evaluation-gate hashes are in `manifest.json`; per-source actions, reasons and valid stopped teacher vote counts are in `audit.jsonl`. The amendments pin the exact old request and target. Historical stage-1 files are unchanged.

Review method: amendments were reviewed individually and additions were targeted samples with recorded provenance, reason and verification. This does not certify every retained row or provide a measured precision estimate. No command was executed against user data. Unresolved semantics remain excluded or abstained.

v2 supersedes the published stage2-v1: v1 dropped leaked rows but kept their family's abstention siblings and labeled command clarifications as abstentions.

Missing-input abstentions were rewritten individually to ordinary underspecified requests while preserving the missing slot. Safety and impossible-task examples were retained. The diagnostic lexical-cue count (without/wihtout/haven't/unnamed/unspecified/unidentified) changed from 101 to 28; this regex is a report, not a label rule. Remaining cues include legitimate permission/safety language. No class proportion was chosen from evaluation scores.

Explicit-path examples move a named operand into the serving `path` field and retain the teacher command. Original corpus rows had no path field: their prompts already matched serving with path=None. This repairs coverage, not a universal prompt mismatch. `requests.jsonl` is stage-2 lineage metadata (includes optional path), not an input to the original exact-schema corpus checker.

The existing evaluation leakage gate hit 6 rows; their whole source families (9 rows) are excluded. Frozen and heldout were used only for leakage detection, never scored or used to tune repairs. 916 report-only overlap pairs remain. Exact duplicate requests are excluded; 11 extra rows share an exact command across distinct requests. These are retained paraphrases; the trainer's grouped split also joins rows that share a command or a near-duplicate request. Validation loss is still not evidence of task improvement.

Limitations: synthetic phrasing, one teacher, small corpus, majority-vote selection bias and incomplete semantic verification remain. New sampling should collect natural missing-input requests paired with answerable counterparts, varied explicit paths, and realistic usage weighting. Repairs alone cannot establish deployment frequency or model gain. No training, evaluation scoring, or publication was performed.

Reproduce into a fresh directory from repository root:

```sh
PYTHONPATH=src .venv/bin/python tools/repair_distill_dataset.py --out-dir /tmp/whatisit-stage2-repro
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
```

Compare `train.jsonl`, `requests.jsonl`, `audit.jsonl`, and `manifest.json` byte-for-byte. No network, teacher sampling or GPU is required.
