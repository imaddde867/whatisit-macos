# Evaluation seed

`cases.jsonl` preserves the original seven task types and adds paraphrases, ambiguity, and mutation requests. It is an authored seed set, not a held-out benchmark. `expected_status` describes today's prototype behavior; `expected_recipe` is present only for a supported task.

The tests use a simulated Darwin platform and tool availability. They check output contracts, not whether the command works on a Mac. The remaining unsupported original tasks are planned coverage, not correct answers earned by abstaining.

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

`macos.jsonl` contains 40 independently worded, authored tasks (20 dev, 20 held-out), separate from the historical seed behavior in `cases.jsonl`. Fields are `id`, `split`, `request`, optional `path`/`expected_recipe`, `expected_status`, `expected_docs`, `rubric`, and `manual_validation`. All tasks have linked routing, execution and semantic dispositions in [VALIDATION.md](../docs/VALIDATION.md). Bounded device checks cover the three supported recipe shapes and selected unsupported candidates; remaining unverified cases are explicit. The original authored held-out split has informed routing fixes and is now development evidence, not an independent benchmark. Preserve its bytes for historical comparison and obtain a fresh uninspected set before model comparison.

Expected statuses are catalog scope/completeness requirements, not snapshots of what the router happens to return. A number-only or historical request must not be counted as solved by a full report or a current snapshot. The runner reports these disagreements without failing or executing a suggestion. It uses the actual host platform and PATH; unit tests simulate macOS tooling.

```bash
PYTHONPATH=src python3 tools/evaluate.py --docs-index .cache/manuals.sqlite3
PYTHONPATH=src python3 -m tools.benchmark --docs-index .cache/manuals.sqlite3
```

The evaluator reports contract matches, suggestion/clarification/abstention counts, per-case mismatches, and expected-tool hit@3. Retrieval eligibility excludes cases with no selected local reference; a hit means any expected tool among the top three chunks, not all required tools or a relevant passage. Counts are separated by split. Neither contract matches nor documentation hits establish command correctness; provisional agent-reviewed useful correct coverage and suggestion accuracy are reported in [SUGGESTION_REVIEW.md](../docs/SUGGESTION_REVIEW.md), pending Imad's final judgments and protocol acceptance.

The benchmark measures five passes through all 40 tasks and ten fresh CLI processes per mode. Fresh processes query sleep assertions without executing that command. It reports wall time including interpreter startup, median/p95/maximum peak RSS, index size, Python/SQLite versions and hashes. It uses macOS `time -l`; OS caches are not flushed, so fresh process does not mean cold filesystem. A restricted sandbox may deny `time` access to resource counters; run the same measurement in a terminal with those counters available.

Raw local reports are ignored under `eval/results/`; a shareable summary is in [MEASUREMENTS.md](../docs/MEASUREMENTS.md). Keep manual corpora and machine-specific/private output out of version control. To validate a recipe, copy and review the displayed command, run it yourself, and record its useful output, permissions, macOS build, limitations and validation date. Do not add automatic execution to the scorer.

## Follow-up comparison

Keep `macos.jsonl` unchanged for the historical before/after comparison. Seven original disagreements are fixed; `sleep-paraphrase` remains a justified disagreement because an assertion snapshot cannot diagnose every cause of wakefulness. Its original expectation is retained, not counted as a new passing case. The inspected held-out split is now development evidence; reserve a fresh, uninspected set before model comparison.

Reports replace supplied file paths with `<path>` and log-filter values with catalog placeholders and omit request text and retrieved manual passages. Use only authored, sanitized case IDs and tool names. The report contains no device logs or command execution results; it must not be used as a script to execute commands. Original artifacts in ignored `.cache/` and `eval/results/` remain local.
# App-check and model development pilot

`app-checks.jsonl` adds 11 development contracts for distinct signature/policy/ticket checks, missing paths and abstention. It does not replace or rewrite the original 40-case fixture. `baseline/` retains the original engine/catalog and their provenance, including both N=7/N=8 provisional scoring interpretations. `pilot/app-checks.json` records the initial A/B/C resource comparison, prompt hashes and retrieved-context identities. Exact prompts remain in the local ignored report. See [the experiment protocol](../docs/EXPERIMENT.md) for commands, measurement scopes and limits; contract matches do not establish semantic accuracy. A fresh set is still required before final comparison.

## Bounded log slice

`log_filter` is an optional object containing only `subsystem` (string), `pid` (integer), `level` (string), `start` (string) and `end` (string). Fields may be omitted/null for clarification cases. The loader validates types; the renderer validates values. The frozen A router receives only its original inputs; B/C share identical explicit filters. The seed log request now expects `needs-input`. The original 40-case fixture remains unchanged. See [LOG_FILTER.md](../docs/LOG_FILTER.md) for the new slice and comparison protocol.

`log-comparison.jsonl` freezes 24 post-implementation requests, inputs and semantic rubrics at implementation commit `869309d`, with identities and budgets in `log-comparison-manifest.json`. The `heldout` split means reserved from tuning for this run; the author is the implementer, so it is not independently blind. After inspecting outputs it becomes development evidence. Preserve the bytes and report misses rather than tuning on them under a held-out label. An independent release comparison remains pending.
