# Evaluation seed

`cases.jsonl` preserves the original seven task types and adds paraphrases, ambiguity, and mutation requests. It is an authored seed set, not a held-out benchmark. `expected_status` describes today's prototype behavior; `expected_recipe` is present only for a supported task.

The tests use a simulated Darwin platform and tool availability. They check output contracts, not whether the command works on a Mac. The four unsupported original tasks are planned coverage, not correct answers earned by abstaining.

Before adding an LLM, expand the set and report:

| Measure | Definition |
| --- | --- |
| Useful correct coverage | Fully correct, sufficiently complete suggestions / all tasks. |
| Answer accuracy | Fully correct suggestions / tasks answered. |
| Abstention rate | Unsupported or unresolved responses / all tasks. |
| Wrong-platform rate | Suggestions using unsupported platform tools/flags / all tasks. |
| Clarification quality | Required inputs requested rather than invented; unnecessary questions recorded separately. |
| Resource cost | Cold/warm wall time and peak/resident RSS, with OS, hardware, model hash, and settings. |

Manually review semantics; exact command strings alone are not a correctness oracle. Multiple equivalent commands can work, and a familiar executable can still carry wrong flags. Record operation effects, output usefulness, permissions, and version constraints. Never execute arbitrary generated commands in the scorer on the everyday workstation.

## Target macOS set

`macos.jsonl` contains 40 independently worded, authored tasks (20 dev, 20 held-out), separate from the historical seed behavior in `cases.jsonl`. Fields are `id`, `split`, `request`, optional `path`/`expected_recipe`, `expected_status`, `expected_docs`, `rubric`, and `manual_validation`. All manual reviews are pending. The split is an authored development holdout, not an independently sourced external benchmark. Routing and ranking were not tuned against its outcomes; future tuning should use dev only and obtain a fresh release set if held-out cases influence implementation.

Expected statuses are catalog scope/completeness requirements, not snapshots of what the router happens to return. A number-only or historical request must not be counted as solved by a full report or a current snapshot. The runner reports these disagreements without failing or executing a suggestion. It uses the actual host platform and PATH; unit tests simulate macOS tooling.

```bash
PYTHONPATH=src python3 tools/evaluate.py --docs-index .cache/manuals.sqlite3
PYTHONPATH=src python3 -m tools.benchmark --docs-index .cache/manuals.sqlite3
```

The evaluator reports contract matches, suggestion/clarification/abstention counts, per-case mismatches, and expected-tool hit@3. Retrieval eligibility excludes cases with no selected local reference; a hit means any expected tool among the top three chunks, not all required tools or a relevant passage. Counts are separated by split. Neither contract matches nor documentation hits establish command correctness; useful correct coverage and answer accuracy remain unmeasured until manual review.

The benchmark measures five passes through all 40 tasks and ten fresh CLI processes per mode. Fresh processes query sleep assertions without executing that command. It reports wall time including interpreter startup, median/p95/maximum peak RSS, index size, Python/SQLite versions and hashes. It uses macOS `time -l`; OS caches are not flushed, so fresh process does not mean cold filesystem. A restricted sandbox may deny `time` access to resource counters; run the same measurement in a terminal with those counters available.

Raw local reports are ignored under `eval/results/`; a shareable summary is in [MEASUREMENTS.md](../docs/MEASUREMENTS.md). Keep manual corpora and machine-specific/private output out of version control. To validate a recipe, copy and review the displayed command, run it yourself, and record its useful output, permissions, macOS build, limitations and validation date. Do not add automatic execution to the scorer.
