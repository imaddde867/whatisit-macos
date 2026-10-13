# Stage-2 data v3 equivalence re-label

Model review; not human-certified. Uses the registered voting rule, unchanged
serving filters, pinned v2 amendments, 36 authored additions and source families.
Original exact-majority strings are preserved; recovered labels record exact
`teacher_votes`, `vote_mode` and `cluster_votes` in the audit.

Retained: 1153 rows (906 commands, 247 abstentions).
Recovery/coverage counts and grouped split:

```json
{
  "abstention_share_after": 0.2142237640936687,
  "abstention_share_before": 0.22731439046746105,
  "grouped_split": {
    "fraction": 0.05,
    "train_rows": 1096,
    "val_ids": [
      "r00037",
      "r00142",
      "r00189",
      "r00200",
      "r00242",
      "r00342",
      "r00389",
      "r00519",
      "r00644",
      "r00647",
      "r00650",
      "r00651",
      "r00685",
      "r00863",
      "r00871",
      "r00877",
      "r00887",
      "r00893",
      "r00976",
      "r00989",
      "r01046",
      "r01131",
      "r01147",
      "r01165",
      "r01169",
      "r01209",
      "r01224",
      "r01247",
      "r01253",
      "r01349",
      "r01449",
      "r01469",
      "r01484",
      "r01498",
      "r01518",
      "r01564",
      "r01615",
      "r01618",
      "r01669",
      "r01674",
      "r01697",
      "r01704",
      "r01761",
      "r01815",
      "r01989",
      "r02005",
      "r02031",
      "r02045",
      "r02047",
      "r02143",
      "r02243",
      "r02248",
      "r02252",
      "r02284",
      "r02320",
      "r02467",
      "r02484"
    ],
    "val_rows": 57,
    "validation_commands_in_training": 0
  },
  "new_repeated_exact_command_rows": 0,
  "new_tool_flag_signatures": 22,
  "overlapping_tool_flag_signatures": 431,
  "recovered_base_rows": 64,
  "recovered_by_agreement": {
    "3": 44,
    "4": 18,
    "5": 2
  },
  "recovered_by_category": {
    "archives-and-media": 4,
    "disk-and-storage": 6,
    "files-and-folders": 11,
    "git-and-dev": 3,
    "macos-tools": 3,
    "network": 8,
    "power-and-hardware": 2,
    "processes-and-ports": 2,
    "search": 10,
    "security-and-apps": 3,
    "system-info": 8,
    "text-processing": 4
  },
  "recovered_excluded_by_repair": 0,
  "recovered_multistring_rows": 64,
  "recovered_rows": 64,
  "tool_flag_signatures": 453,
  "v2_tool_flag_signatures": 432
}
```

Leakage: 7 hard-hit ids, 10 whole-family
rows excluded. Historical quarantine lists apply to all families. Hard-hit details
are in `leakage-hits.jsonl`; 972 report-only overlap pairs remain.
Frozen/heldout contents are read only by the existing leakage gate. Their hashes
are the historical v2 manifest values, not fresh reads. Development scores are
not consulted. Repeated commands remain grouped in validation.

Actions: `{"clarified_request": 12, "corrected_target": 10, "exclude": 21, "explicit_path": 24, "keep": 1002, "model_authored_addition": 27, "natural_abstain": 78}`. Model-authored additions retained:
27 after exclusions.
Model review and pinned-tokenizer preflight must pass before publication/training.
No generated command was executed against user data. No teacher sampling.

Reproduce with the same PATH as historical builders into a fresh directory:

```sh
PYTHONPATH=src .venv/bin/python tools/repair_distill_dataset.py --base-labels data/distill/v3-base/train.jsonl --out-dir /tmp/whatisit-v3-repro
```

Training SHA-256: `798217962db57e72c37ff8ac6ac656f9aa558fd6353fbe4c4731e113b2a2e576`. Every artifact is hashed in the
manifest; the manifest itself has an external checksum. A fresh build must match
byte-for-byte. Model review is recorded separately and has no human certification.

Model review gate passed: 52/60 OK, 1 debatable, 7 wrong; conservative precision 86.7%, Wilson 95% [75.8%, 93.1%]. See review-result.md for all IDs and failure modes. All 1,153 rows passed the pinned-tokenizer prefix/end-of-turn/512 checks (maximum 243). The registered low-recovery alarm was investigated; 64 command rows were recovered rather than weakening semantic guards toward the original hypothesis. Final merge audit read all 64 clusters (141 distinct strings), with no remaining meaning-changing pair.
