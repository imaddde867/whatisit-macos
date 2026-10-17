# Semantic audit of dev + everyday scoring (2026-10-18)

Question: how far is the regex `accept` score from whether a command actually
does the job on stock macOS? **Model review, not human review.**

## Method

- Pool: every distinct command from default + 16 runtime-LoRA adapters
  (`docs/runtime-lora-8seed/*-detail.json`), all 705 teacher samples
  (`data/teacher/eval-ceiling/raw_samples.jsonl`, after serving lint), and each
  case's `traps` as negative controls. 883 unique (case, command) items.
- Re-labelled with current `eval/*.jsonl` first (reproduces A 78.5 / B 82.0;
  default 65, the remaining point vs 66 is `m016` `cat input.txt | cut -d: -f3`).
- Pass 1: 10 blind Sonnet reviewers (no scorer label, no source). Rubric in
  `INSTRUCTIONS.md`: correct = runs on stock macOS as typed and does exactly what
  was asked. Candidates were never executed.
- Pass 2: every item where pass 1 disagreed with the scorer (167) re-checked
  blind by Opus with man-page evidence (`RECHECK.md`). A label changes only if both passes agree;
  15 split/unsure items keep the scorer label.
- Controls: 121/122 trap commands judged incorrect (1 unsure).

## Result

148 of 883 items change label: 66 regex passes are actually broken, 82 regex
"wrong" commands actually work. The regex is wrong in both directions.

| Run | Regex correct / 141 | Audited correct / 141 |
|---|---|---|
| default | 65 | 58 |
| A mean (8 seeds) | 78.5 | 74.0 |
| B mean (8 seeds) | 82.0 | 76.1 |
| best audited adapter (B-s7) | 84 | 81 |
| best regex adapter (B-s2) | 86 | 80 |
| teacher, mean per sample | 116 | 130 |
| teacher, best of 5 | 126 | 136 |

- Student flips are mostly downward (61 down, 26 up): regexes accept broken
  commands that contain the right tool/flag.
- Teacher flips are mostly upward (53 up, 5 down): regexes reject valid
  alternative phrasings.
- Student error categories over 16 adapters: wrong_output 245, missed_constraint 141,
  hallucinated_flag 134, wrong_operand 104, wrong_tool 84, linux_syntax 21,
  other 20, unsafe 18, should_abstain 17.

## What it means

- The student is further from 90% (127/141) than the regex showed: best ≈ 57%.
- The teacher is not capped at 88. One teacher sample is right ≈ 92% of the
  time. The 88 came from the exact-string 3-of-5 label vote, which dropped 41 cases.
- The teacher is not the bottleneck. Reaching 90% is not shown: the 1.5B
  student still has to learn the labels, and Learning64 shows composition
  does not transfer.
- The same exact-string vote built the training set: of 2,520 teacher-sampled
  requests, 1,207 (48%) were dropped as `no_majority`
  (`data/distill/roihu_full_quality_report.md`); v3 recovered 60.
- The runtime-LoRA gain survives the audit: default 58 -> A 74 / B 76.
- The regex scorer is not a reliable metric. Frozen/held-out were written the
  same way and probably share the problem; they were not opened.

## Not covered

- Pass 1 was light: Sonnet reviewers made 4-7 tool calls each and one batch
  used no man pages. The 578 items where pass 1 agreed with the regex were
  never re-checked, so scores carry an unmeasured error.
- Reviewer case flags (possibly broken cases): m040, m114, m118, m120, e029,
  e047, e052, e071, e080.
- Lint-rejected outputs (about 10 per run) were not saved, so not audited. They
  already count as incorrect, so auditing them can only raise student scores.
- 15 unresolved items keep the regex label.
- No `eval/*.jsonl` change is made here.

Reproduce: `scripts/build_pool.py` (pipx whatisit python, stock PATH, `PYTHONPATH=src`),
then `scripts/final.py <audit dir> <pool.json>`. With pass 2 removed it
reproduces the regex numbers (65 / 78.5 / 82.0, teacher 116 / 126).
