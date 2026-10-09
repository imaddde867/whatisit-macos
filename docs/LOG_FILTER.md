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

Verification: 63 source tests pass, covering explicit argv, predicate injection attempts, missing/invalid inputs, offset-aware ordering, compound/unsupported requests, platform/tool checks, unused flags, CLI forwarding, model-selected rendering, fixture types and report redaction. Installed-wheel validation and the new comparison are recorded below when complete.

## Comparison protocol

Freeze fresh authored requests and per-case rubrics after the implementation and before running A/B/C. Hash the case file, source/catalog/prompt and documentation index. A is the archived three-recipe router, B the seven-operation keyword router with retrieval, C the same catalog/explicit inputs/retrieval with the existing local MLX selector. Use one warm pass and three fresh workers per variant; exclude the first warm response from warm summaries. No suggested command is executed. Keep the resource thresholds from [EXPERIMENT.md](EXPERIMENT.md#next-comparison-gates) unchanged.

Report contract matches separately from agent-reviewed semantic judgments: useful correct suggestions / all cases, correct / returned suggestions, wrong/partial suggestions, necessary/unnecessary clarification, unsupported responses, fabricated inputs and wrong-platform templates. Clarifications and abstentions earn no useful-coverage credit. A command counts as correct only if it satisfies the whole request and preserves supplied inputs under the declared public representative-input protocol; exact fixture paths/PIDs need not exist and are not execution claims. For an unsupported request the expected result is abstention; missing inputs require clarification. A model failure matching an external abstention contract remains a model failure.

The implementer authors this set, so it is fresh and reserved from tuning, but not independently blind. Do not call its results general accuracy or a final release evaluation. Once outputs are inspected, the set becomes development evidence: preserve its bytes, publish failures and do not tune on it while calling it held-out. An independent release set remains required before default model adoption.
