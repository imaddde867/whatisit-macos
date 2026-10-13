# Stage-2 data v3 equivalence re-label

Model review; not human-certified. Uses the registered voting rule, unchanged
serving filters, pinned v2 amendments, 36 authored additions and source families.
Original exact-majority strings are preserved; recovered labels record exact
`teacher_votes`, `vote_mode` and `cluster_votes` in the audit.

Retained: 1149 rows (902 commands, 247 abstentions).
Recovery/coverage counts and grouped split:

```json
{
  "abstention_share_after": 0.21496953872932986,
  "abstention_share_before": 0.22731439046746105,
  "grouped_split": {
    "fraction": 0.05,
    "train_rows": 1092,
    "val_ids": [
      "r00037",
      "r00105",
      "r00112",
      "r00189",
      "r00200",
      "r00231",
      "r00246",
      "r00288",
      "r00397",
      "r00399",
      "r00519",
      "r00594",
      "r00646",
      "r00651",
      "r00686",
      "r00791",
      "r00840",
      "r00883",
      "r00972",
      "r01017",
      "r01053",
      "r01067",
      "r01128",
      "r01227",
      "r01295",
      "r01317",
      "r01391",
      "r01425",
      "r01463",
      "r01469",
      "r01479",
      "r01486",
      "r01564",
      "r01668",
      "r01673",
      "r01674",
      "r01694",
      "r01699",
      "r01711",
      "r01753",
      "r01889",
      "r01974",
      "r02008",
      "r02092",
      "r02096",
      "r02099",
      "r02100",
      "r02107",
      "r02160",
      "r02163",
      "r02198",
      "r02243",
      "r02248",
      "r02393",
      "r02405",
      "r02421",
      "r02469"
    ],
    "val_rows": 57,
    "validation_commands_in_training": 0
  },
  "new_repeated_exact_command_rows": 0,
  "new_tool_flag_signatures": 21,
  "overlapping_tool_flag_signatures": 431,
  "recovered_base_rows": 60,
  "recovered_by_agreement": {
    "3": 42,
    "4": 17,
    "5": 1
  },
  "recovered_by_category": {
    "archives-and-media": 4,
    "disk-and-storage": 6,
    "files-and-folders": 8,
    "git-and-dev": 3,
    "macos-tools": 3,
    "network": 8,
    "power-and-hardware": 2,
    "processes-and-ports": 2,
    "search": 9,
    "security-and-apps": 3,
    "system-info": 8,
    "text-processing": 4
  },
  "recovered_excluded_by_repair": 0,
  "recovered_multistring_rows": 60,
  "recovered_rows": 60,
  "tool_flag_signatures": 452,
  "v2_tool_flag_signatures": 432
}
```

Leakage: 7 hard-hit ids, 10 whole-family
rows excluded. Historical quarantine lists apply to all families. Hard-hit details
are in `leakage-hits.jsonl`; 964 report-only overlap pairs remain.
Frozen/heldout contents are read only by the existing leakage gate. Their hashes
are the historical v2 manifest values, not fresh reads. Development scores are
not consulted. Repeated commands remain grouped in validation.

Actions: `{"clarified_request": 12, "corrected_target": 10, "exclude": 21, "explicit_path": 24, "keep": 998, "model_authored_addition": 27, "natural_abstain": 78}`. Model-authored additions retained:
27 after exclusions.
Model review and pinned-tokenizer preflight must pass before publication/training.
No generated command was executed against user data. No teacher sampling.

Reproduce with the same PATH as historical builders into a fresh directory:

```sh
PYTHONPATH=src .venv/bin/python tools/repair_distill_dataset.py --base-labels data/distill/v3-base/train.jsonl --out-dir /tmp/whatisit-v3-repro
```

Training SHA-256: `c8f9661db1cadf79d81c58f0fd8f0628ad3461c61c0a5f97c6b20f195ec06550`. Every artifact is hashed in the
manifest; the manifest itself has an external checksum. A fresh build must match
byte-for-byte. Model review is recorded separately and has no human certification.

Model review: 51/60 OK (85.0%; Wilson 95% 73.9–91.9%), 8 wrong and 1 debatable. Inclusive gate passes with 9 non-OK. This is a census of the 60 recovered command rows. All 60 merged clusters (131 distinct strings) were read; no meaning-changing pair remains. See review-result.md and merge-audit.md.
