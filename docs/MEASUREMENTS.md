# Target Mac capture and lookup measurements

Measured 2026-10-08 on macOS 27.0.1 (build 26A434), arm64 Mac16,1, Apple M4, 16 GiB RAM. Python 3.14.8; SQLite 3.53.4 with FTS5. No model or suggested command was run. Hardware facts were read with `sysctl`; only manual-rendering utilities and the project lookup CLI were invoked for capture and measurement.

## Installed tools and manuals

All 12 selected tools and their system manuals were available:

| Tool | Executable | Manual under `/usr/share/man` |
| --- | --- | --- |
| system_profiler | /usr/sbin/system_profiler | man8/system_profiler.8 |
| pmset | /usr/bin/pmset | man1/pmset.1 |
| mdls | /usr/bin/mdls | man1/mdls.1 |
| fs_usage | /usr/bin/fs_usage | man1/fs_usage.1 |
| launchctl | /bin/launchctl | man1/launchctl.1 |
| log | /usr/bin/log | man1/log.1 |
| codesign | /usr/bin/codesign | man1/codesign.1 |
| spctl | /usr/sbin/spctl | man8/spctl.8 |
| stat | /usr/bin/stat | man1/stat.1 |
| find | /usr/bin/find | man1/find.1 |
| sed | /usr/bin/sed | man1/sed.1 |
| du | /usr/bin/du | man1/du.1 |

The explicit capture contains these 12 manuals and three authored catalog entries. Local capture time: 2026-10-08T18:01:23Z. Index size: 487,424 bytes (476 KiB). Rendered manual content stays in ignored `.cache/manuals.sqlite3`; no copied manual corpus is committed.

Manual review findings, with device execution still pending:

- `pmset(1)` documents the dedicated assertion snapshot and distinguishes continuous assertion logging. Snapshot output cannot satisfy history/continuous requests.
- `mdls(1)` documents file attributes and a named-attribute option. The current all-attributes template cannot satisfy an attribute-only request or directory traversal.
- `system_profiler(8)` documents datatype selection and JSON reporting. The manual does not enumerate `SPPowerDataType` or certify a Cycle Count field on this device; the recipe still needs manual output validation.
- `fs_usage(1)` documents PID/command filtering and root requirements. A traced process must be explicitly selected; protected-process visibility still needs device validation.
- `launchctl(1)` distinguishes domain/service targets and PID diagnostics. It warns that printed output is not a stable API; no parser or PID-to-service guarantee was added.
- `log(1)` documents predicates, process filters, time bounds and information/debug inclusion. These need explicit values before a filtered recipe is useful.
- `codesign(1)` distinguishes signature verification from signing. `spctl(8)` documents policy assessment separately and deprecates rule/global-state modification operations from macOS 15. Neither alone establishes the complete signing/notarization/policy task.
- Local BSD `stat(1)` and `sed(1)` document different format/in-place syntax from common GNU examples. No GNU substitution was introduced.

## Authored evaluation

The original seed remains unchanged. The expanded set contains 40 tasks, 20 per split. No routing or retrieval tuning was performed after inspecting these results.

| Metric | Dev | Held-out | Total |
| --- | ---: | ---: | ---: |
| Tasks | 20 | 20 | 40 |
| Catalog contract matches | 20 | 12 | 32 |
| Suggestions | 5 | 9 | 14 |
| Unsupported | 13 | 9 | 22 |
| Needs input | 1 | 2 | 3 |
| Ambiguous | 1 | 0 | 1 |
| Expected-tool hits / eligible tasks | 15/16 | 19/19 | 34/35 |

Six suggestions fail completeness requirements: `battery-health`, `battery-number`, `metadata-attribute`, `metadata-recursive`, `sleep-history`, and `sleep-live`. Two supported paraphrases are missed: `metadata-paraphrase` and `sleep-paraphrase`. The Linux `strace` task is correctly unsupported but retrieval misses its macOS reference (`fs_usage`). No new command recipes were added to conceal these gaps.

Contract matches include abstentions and are not command accuracy. The 14/40 suggestion rate is not useful correct coverage. All 40 manual rubrics remain pending. Expected-tool hit@3 is a weak lexical metric: it does not validate passages, flags, inputs or multi-step completeness. Evidence retrieval does not change the baseline commands or statuses.

## Latency and memory

| Mode | Samples | Median wall/lookup time | p95 | Maximum peak RSS |
| --- | ---: | ---: | ---: | ---: |
| Fresh CLI, catalog | 10 | 47.02 ms | 50.79 ms | 24.66 MiB |
| Fresh CLI, catalog + documentation | 10 | 57.29 ms | 70.12 ms | 28.66 MiB |
| Repeated catalog lookup | 200 | 0.039 ms | 0.099 ms | — |
| Repeated documentation search | 200 | 0.184 ms | 0.258 ms | — |
| Repeated catalog + documentation | 200 | 0.224 ms | 0.348 ms | — |

Fresh CLI measurements include Python startup, JSON output and the `time` wrapper, using one sleep-assertion request. Peak RSS is per child process from macOS `time -l` (bytes converted to MiB); median peaks are 24.58 MiB and 28.45 MiB respectively. Repeated timings use five passes over the 40-task set, including each SQLite open/query/close. The warm benchmark process peaks at 30.63 MiB across all modes; that value cannot be attributed to one mode. OS caches were not flushed, no persistent index/model server runs, and command runtime is excluded. These are observations on one machine, not release budgets.

Measurement time: 2026-10-08T18:04:36Z. Index SHA-256: `250e2b7984e1a4c861e18396742ac675bc009b9d4a433e3665bbbb0983eef4ea`. Case-set SHA-256: `25a74bad2d4db725dc9599f4f2afa3b6f20c318f9983f165e97a6c73bdd79158`.

Reproduce from the repository root using the commands in [eval/README.md](../eval/README.md). Index rebuilding changes capture timestamps and therefore its hash. The first sandboxed resource run failed because `time` could not read `kern.clockrate`; the reported run used available macOS counters. Manual command validation, cross-version testing, independent evaluation review and original-model/config capture remain outstanding.

Validation: the full 28-test suite passes on installed Python 3.12, 3.13 and 3.14. A real-index JSON CLI check returns unsupported plus local evidence for unified logs. The offline wheel-build check could not run because installed Python environments lack `setuptools.build_meta`; no build dependencies were installed. Python 3.11 and other macOS releases were not tested locally.
