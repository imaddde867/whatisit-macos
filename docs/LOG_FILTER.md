# Bounded unified-log operation — 2026-10-09

The seventh recipe renders `log show --style compact` with explicit start/end and a fixed conjunction of subsystem, logType and processIdentifier. It reuses [G2's controlled-event evidence](VALIDATION.md#g2-observed-results--2026-10-09); completed device checks were not repeated. Installed `log help show` and `log help predicates` were read again to verify timestamp forms and predicate fields. Their help exits 64 even when it prints usage successfully; no datastore query was run.

All five inputs are mandatory. `--subsystem` is a 1–255 character ASCII identifier beginning with a letter/digit and continuing with letters, digits, dots, underscores or hyphens. `--pid` is a positive integer. `--level` is exactly error or default. `--start` and `--end` use `YYYY-MM-DD HH:MM:SS+HHMM`, including the UTC offset; end must follow start in absolute time. No path is accepted for this operation. Other recipes reject log flags rather than silently ignoring them.

```sh
PYTHONPATH=src python3 -m whatisit_macos 'filter unified logs' \
  --subsystem com.example.whatisit --pid 123 --level error \
  --start '2026-10-09 10:00:00+0300' --end '2026-10-09 10:01:00+0300'
```

The example is synthetic. Lookup prints a command; it does not query logs, resolve a PID, infer an interval or run the suggestion. Review and replace inputs deliberately before manual execution. The fixed predicate cannot receive user-supplied predicate operators or expressions; the renderer validates fields, interpolates the catalog template and quotes each shell argument. Both keyword routing and optional model selection use that renderer. Filter values are not included in the model prompt.

The scope is stored logs matching all supplied filters, with compact output. Process-name matching, live monitoring, archives, info/debug persistence, message/category filters, relative intervals and counts remain unsupported. Empty output cannot prove absence of events. PID reuse, access, retention and redaction limit completeness; boundary inclusivity remains unverified. The existing keyword guard is conservative and cannot prove semantic completeness for arbitrary wording.

The seed `original-logs` case now expects missing-input clarification. The original 40-task fixture and baseline archive remain unchanged, including historical expectations. Shareable evaluator output replaces log arguments with catalog placeholders; raw experiment reports still contain requests, inputs and model prompts and must use public fixtures.

Verification: 63 source tests and the same 63 tests against an installed wheel outside the clone pass, covering explicit argv, predicate injection attempts, missing/invalid inputs, offset-aware ordering, compound/unsupported requests, platform/tool checks, unused flags, CLI forwarding, model-selected rendering, fixture types and report redaction. The isolated wheel smoke checks all seven packaged recipes, entry points, fresh manual capture, normal lookup, missing-index errors and the new log CLI arguments. No runtime dependency was added. No device query, suggested command, live CI run or protected-process check was repeated.

## Comparison protocol

Freeze fresh authored requests and per-case rubrics after the implementation and before running A/B/C. Hash the case file, source/catalog/prompt and documentation index. A is the archived three-recipe router, B the seven-operation keyword router with retrieval, C the same catalog/explicit inputs/retrieval with the existing local MLX selector. Use one warm pass and three fresh workers per variant; exclude the first warm response from warm summaries. No suggested command is executed. Keep the resource thresholds from [EXPERIMENT.md](EXPERIMENT.md#next-comparison-gates) unchanged.

Report contract matches separately from agent-reviewed semantic judgments: useful correct suggestions / all cases, correct / returned suggestions, wrong/partial suggestions, necessary/unnecessary clarification, unsupported responses, fabricated inputs and wrong-platform templates. Clarifications and abstentions earn no useful-coverage credit. A command counts as correct only if it satisfies the whole request and preserves supplied inputs under the declared public representative-input protocol; exact fixture paths/PIDs need not exist and are not execution claims. For an unsupported request the expected result is abstention; missing inputs require clarification. A model failure matching an external abstention contract remains a model failure.

The implementer authors this set, so it is fresh and reserved from tuning, but not independently blind. Do not call its results general accuracy or a final release evaluation. Once outputs are inspected, the set becomes development evidence: preserve its bytes, publish failures and do not tune on it while calling it held-out. An independent release set remains required before default model adoption.

## Frozen comparison results

The [24-case fixture](../eval/log-comparison.jsonl) and [freeze manifest](../eval/log-comparison-manifest.json) were written after implementation commit `869309d` and before measurement. Their SHA-256 and the source/catalog/prompt hashes were verified unchanged after inspection. No router, prompt or catalog was tuned against these results. [The shareable report](../eval/pilot/log-comparison.json) retains outputs, per-case semantic judgments, resource samples, model/runtime/artifact hashes, documentation identities/chunk hashes and prompt hashes. Full prompts/manual text remain in ignored `.cache/log-comparison.json`; no manual passages are committed.

Target: M4, 16 GiB, macOS 27.0.1, arm64, Python 3.14.8. C reused the cached Qwen2.5-3B 4-bit snapshot and MLX-LM 0.31.3 / MLX 0.32.0 / Transformers 5.5.0 from the first pilot. The new index contains 12 system manuals and seven curated operations. Suggested commands were not executed; semantic judgments reuse the existing representative-input device evidence and inspect the full request, argv, supplied inputs and caveats. Synthetic paths/PIDs are not literal execution evidence. Human scoring acceptance remains pending. All new metadata requests explicitly ask for Spotlight attributes, so the historical broad-metadata N=7/N=8 dispute is not resolved or merged into these scores.

| Variant | Contracts | Useful correct coverage | Correct / suggestions | Fresh wall median | Warm median / p95 | Worker peak RSS | Retained growth after unload |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A: frozen three recipes | 14/24 | 4/24 (16.7%) | 4/4 | 58.1 ms | 0.0027 / 0.0559 ms | 26.3 MiB | 0 MiB |
| B: seven deterministic operations + retrieval | 23/24 | 10/24 (41.7%) | 10/10 | 80.8 ms | 0.694 / 2.458 ms | 31.0 MiB | 4.8 MiB |
| C: same catalog/inputs + model | 19/24 | 8/24 (33.3%) | 8/8 | 6,635.6 ms | 5,021.5 / 5,675.1 ms | 1,926.3 MiB | 1,611.8 MiB |

Counts are agent-reviewed, fixture-specific template semantics, not independent/general accuracy or new device runs. Clarifications and abstentions receive zero useful-coverage credit. No incorrect/partial returned suggestion, fabricated required input or wrong-platform template was found in this scoped review. The safe renderer does not prevent missed answers or wrong clarifications:

- B missed `logs-semantic`, which lacks the literal word unified. This stays a published miss rather than a tuned passing case.
- C also missed that log paraphrase and both answerable battery requests: unknown operation IDs were rejected. Across the run, six unknown-ID failures occurred, including three unsupported requests whose external abstention contracts still matched. They remain model failures, not successful model decisions; the adapter's error does not retain the unknown ID string.
- C selected app-ticket for the broad wakefulness question and unnecessarily asked for an app path. The shared renderer rejected selected operations for live/debug logs, recursive metadata, historical sleep and the ambiguous battery/sleep request. C's ambiguity abstention is semantically safe, but it differs from the exact expected ambiguous status and counts as a contract mismatch.
- A/B returned one/four necessary missing-input clarifications plus one necessary ambiguity clarification each. C returned four necessary and one unnecessary input clarification. Strict unsupported responses were A 18/24, B 9/24, C 11/24; unresolved responses including clarifications were A 20/24, B 14/24, C 16/24. Safe abstention never earns useful-coverage credit.

Fresh measurements use three separate workers on `logs-direct`; all three B/C fresh workers suggested the expected operation, while A abstained. Warm measurements use one pass through 24 requests, excluding the first response from the 23-sample latency summary. These small tail samples are not reliable population p95 estimates. Fresh wall includes interpreter, imports, retrieval, load, response, unload and exit; warm includes retrieval/rendering and generation. Filesystem caches were not flushed. C's warm-worker model load was 1,228.3 ms, outside the warm summary; the three fresh load times were 910.9–1,963.2 ms.

Worker peak RSS uses self ru_maxrss high-water. Process-tree samples at 50 ms can miss brief peaks; separate samples and MLX allocation peaks are retained without adding overlapping unified memory. C retained 1,638.0 MiB total RSS immediately after unload (1,611.8 MiB growth), before worker exit. This is not a long-idle observation. No backend server was started. Swap used was 1,047.88 MiB before and after; memory pressure was not sampled. Unchanged system swap does not establish absence of transient pressure or causal model impact.

**Decision:** keep B as the default and C as an optional experiment. B adds six useful answers over A on this set. C returns two fewer useful answers than B and misses the unchanged 2,000 ms warm-p95, 5,000 ms fresh-wall and 128 MiB retained-growth budgets; its observed peak RSS stays below the 2,048 MiB ceiling. No independent release evaluation or default model adoption is claimed. Bounded tracing and known-service inspection remain later coverage slices.

Reproduce lookup measurements with a fresh documentation-index filename and the already available optional model environment:

```sh
PYTHONPATH=src python3 -m whatisit_macos.build_docs .cache/manuals-log-next.sqlite3
PYTHONPATH=src /path/to/model-env/bin/python -m tools.experiment \
  --cases eval/log-comparison.jsonl --docs-index .cache/manuals-log-next.sqlite3 \
  --model /path/to/existing/local/model --passes 1 --fresh-runs 3 \
  > .cache/log-comparison-next.json
```

Omit `--model` for A/B only. The fixture is now inspected development evidence; rerunning it is reproducibility work, not a fresh reserved comparison. Manual capture/provenance hashing stays outside lookup timing. Future independent release cases must be reserved separately.
