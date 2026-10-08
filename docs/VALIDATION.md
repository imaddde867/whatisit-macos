# macOS task and wheel validation — 2026-10-08

Baseline source: `3ce854895f9af48fbf961542cca8818ec3ab65d8` on `fix/macos-routing-validation`, preserving all pre-existing local implementation, fixtures and measurements. Parent default-branch commit: `40ddbb9b0f80b2c7e1fe258aec6240823b852f45`. No repository AGENTS.md existed initially; the supplied instructions apply. GitNexus subsequently generated local guidance during indexing.

Target: macOS 27.0.1 (26A434), arm64; Python 3.14.8. Baseline: 28 tests pass with `PYTHONPATH=src python3 -m unittest discover -s tests -v`. A bare invocation before installation failed to import all five test modules; this was environment setup, not a passing result. Original claims about Python 3.12/3.13 in MEASUREMENTS.md are historical, not new runs.

```sh
PYTHONPATH=src python3 tools/evaluate.py --docs-index .cache/manuals.sqlite3
PYTHONPATH=src python3 -m tools.benchmark --docs-index .cache/manuals.sqlite3
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Original eight disagreements

These are the frozen fixture's expected behavior, not command execution evidence. The six partial suggestions are routing errors for unsupported scope. No required input was invented. Expectations and split labels remain unchanged.

| Task ID | Original expected | Baseline actual | Diagnosis and evidence | Follow-up |
| --- | --- | --- | --- | --- |
| battery-health | unsupported | power report suggestion | `system_profiler(8)` supports `-json`, but the fixed argv omits it; capacity presence is unverified. Partial answer. | unsupported |
| battery-number | unsupported | power report suggestion | `system_profiler(8)` produces a report, not scalar extraction. A numeric-only command needs output/schema validation. | unsupported |
| metadata-paraphrase | needs-input, file-metadata | unsupported | `mdls(1)` describes attributes associated with supplied files; Spotlight attributes fit the same one-file recipe. Missing path remains required. | needs-input; synonym regression |
| metadata-attribute | unsupported | unfiltered mdls suggestion | `mdls(1)` requires `-name` for selection; current argv has no selection. | unsupported |
| metadata-recursive | unsupported | one-path mdls suggestion | `mdls(1)` accepts files but does not document recursive traversal; a traversal/input policy is absent. | unsupported |
| sleep-paraphrase | suggestion, sleep-assertions | unsupported | **Expectation too broad:** `pmset(1)` says assertions may prevent sleep; it does not promise every cause of a computer remaining awake. The existing recipe explicitly limits completeness. An assertion snapshot is only one diagnostic step. | retained unsupported, justified disagreement; original fixture unchanged |
| sleep-history | unsupported | assertion snapshot suggestion | `pmset(1)` separates assertion summary, assertion event logging and power history. Snapshot cannot reconstruct 24 hours. | unsupported |
| sleep-live | unsupported | assertion snapshot suggestion | `pmset(1)` separates `assertions` from `assertionslog`; one snapshot is not continuous monitoring. | unsupported |

Regression tests exercise real routing, qualifier paraphrases, positive basic reports, missing/supplied paths, shell quoting and unsupported compound requests. The root causes were ignoring qualifiers and requiring the exact word metadata. No new command recipe or retrieval ranking change was needed. Known qualifier checks remain lexical; arbitrary natural language completeness is not guaranteed.

The original held-out set has now informed development. Keep its bytes and scores for comparison, but obtain a fresh uninspected release set for #4. Do not call the 39/40 result independent accuracy.

## All 40 dispositions

Review date for every row: 2026-10-08; target version/build as above. Manuals were freshly rendered from the installed `/usr/share/man` tree using `man -M /usr/share/man SECTION TOOL | col -b`. Full tool/source paths are listed in MEASUREMENTS.md; hashes below identify this review. No manual corpus, device logs or private files are committed.

“Unverified” means flags/arguments reviewed but **no human device execution**. “Unsupported” means abstention is appropriate for the current three-recipe catalog, even if a command could be added later. “Needs input” validates a clarification or boundary rejection, not a runnable placeholder. The ambiguous row validates asking for one task. Observed behavior in this review is router status/argv only; no task command was run.

| Task ID | Disposition | Manual / privileges | Inputs, completeness and limitation; manual check |
| --- | --- | --- | --- |
| battery-report | unverified | system_profiler(8); user | B1; confirm SPPowerDataType and battery Cycle Count exist on device. Full report, no scalar extraction. |
| battery-cycles | unverified | system_profiler(8); user | B1; same report; no numeric value fabricated. |
| metadata-missing | needs input | mdls(1); user, searchable/readable target | Explicit file `--path` required; no placeholder command. M1 after supplying fixture. |
| metadata-file | unverified | mdls(1); user | M1; supplied authored path may not exist; check actual fixture and null/unindexed attributes. |
| sleep-assertions | unverified | pmset(1); user for query | S1; owners/current assertions only; not all sleep causes. |
| sleep-blockers | unverified | pmset(1); user for query | S1; same snapshot; no claim of historical coverage. |
| filesystem-pid | unsupported | fs_usage(1); root | T1 candidate only; PID 1234 is authored, not a verified live process. Needs explicit real PID, visibility/privacy review. |
| launchd-owner | unsupported | launchctl(1); procinfo root, print queries user | L1; PID context is not guaranteed owner label/config mapping. Need domain and service identity; unstable debug output. |
| unified-filter | unsupported | log(1); access depends on log store | G1 candidate; missing process/subsystem/severity/start/end; persistence/redaction limits. No empty filter invention. |
| app-audit | unsupported | codesign(1), spctl(8); user read/assessment | A1 candidate; explicit app required; signature, ticket evidence and local policy are distinct. No complete notarization claim. |
| bsd-stat | unsupported | stat(1); directory search permission | F1 candidate; file missing; BSD `-f`, not GNU `-c`. |
| bsd-find | unsupported | find(1); directory access | F1 candidate; choose explicit root, bounded scope; `-mtime -1` is age-based, not a calendar-day boundary. |
| bsd-sed | unsupported | sed(1); input read access | F1 candidate; missing expression/file; preview without `-i`, no edits. |
| bsd-du | unsupported | du(1); traversal access | F1 candidate; explicit directory absent; allocated and apparent size differ, APFS sharing may affect attribution. |
| mutate-metadata | unsupported | catalog scope; no execution | Mutation outside inspection scope. No manual command proposed. |
| mutate-sleep | unsupported | pmset(1); setters require root | Mutation outside scope; snapshot does not disable assertions. |
| compound | validated clarification | system_profiler(8), pmset(1); user | Both supported tasks detected; ask for one task; no partial answer. |
| empty | unsupported | no applicable manual | No request, no fabricated command. |
| linux | unsupported | fs_usage(1); root if future candidate | macOS alternative needs inputs/privileges; no Linux strace suggestion. Retrieval miss retained. |
| unknown | unsupported | no applicable manual | Coffee request outside catalog. |
| battery-health | unsupported | system_profiler(8); user | B1/B2 candidate; `-json` absent from recipe; capacity fields need device validation. |
| battery-number | unsupported | system_profiler(8); user | B1; report is not a scalar; no speculative field parser. |
| battery-phrase | unverified | system_profiler(8); user | B1; basic report paraphrase; battery/device limitation unchanged. |
| metadata-paraphrase | needs input | mdls(1); target access | Missing document path requested; M1 only after explicit input. |
| metadata-spaces | unverified | mdls(1); target access | M1; quoting verified by tests; actual file/metadata availability pending. |
| metadata-shell | unverified | mdls(1); target access | M1/M2; metacharacters are one literal argument; no shell execution; fixture existence pending. |
| metadata-attribute | unsupported | mdls(1); target access | M3 candidate needs `-name kMDItemContentType`; all-attribute recipe incomplete. |
| metadata-recursive | unsupported | mdls(1), find(1); traversal access | Missing traversal policy/root validation; no directory substituted for complete recursive output. |
| sleep-paraphrase | unsupported; expectation disputed | pmset(1); user | S1 only a diagnostic step; broad causal question cannot be certified by snapshot. Frozen mismatch remains. |
| sleep-history | unsupported | pmset(1); user for query | No 24-hour assertion history in snapshot; event logging is not retroactive recovery. |
| sleep-live | unsupported | pmset(1); user for query | S2 candidate; continuous assertion logging distinct from snapshot; stop with Ctrl-C. |
| trace-missing | unsupported | fs_usage(1); root | Missing PID; T1 only after user selects a live test process; protected activity visibility unverified. |
| launchd-label | unsupported | launchctl(1); queries user | L1; explicit domain/label absent; no invented service target. |
| logs-missing | unsupported | log(1); store access | G1; subsystem/time missing; no real logs captured. |
| signature-only | unsupported | codesign(1); user read access | A1; app path absent; verification is not ticket/policy proof. |
| gatekeeper-only | unsupported | spctl(8); user assessment | A1; app path absent; policy/network/cache/version dependent. No policy mutation. |
| notarization-only | unsupported | ticket tool not in captured 12 manuals | App/tool missing; ticket-validation flags/device behavior unverified; absent ticket does not establish absent notarization. |
| linux-stat | unsupported | stat(1); directory search permission | GNU `--printf` not in installed BSD synopsis; F1 uses BSD syntax. |
| irrelevant-path | needs input | system_profiler(8); user | Reject irrelevant `--path`; ask user to remove it. |
| metadata-newline | needs input | renderer boundary; mdls(1) | Reject control characters before command output; no execution needed to verify rejection. |

Counts: 8 command suggestions unverified; 4 input responses; 27 unsupported; 1 validated clarification. **Zero command tasks manually executed/validated.** All 40 have a disposition; #2's device-validation work remains incomplete.

Current suggestion rate: 8/40 (20%); abstention/unresolved rate: 32/40 (80%, includes missing input and ambiguity). Useful correct coverage and answer accuracy are **unmeasured**, not 20% and not 39/40. At most 8/40 can be correct at this stage. Static inspection finds zero wrong-platform command templates among eight suggestions (0/40); this is not a device success rate. Unnecessary clarification and independent semantic review remain unmeasured.

## Manual commands for the user

These commands are prepared, **not run**. Run individual groups after review. Keep raw reports local; record only task ID, command shape, success/failure, whether required fields were present, privileges, limitations, macOS build and date. Do not paste serial numbers, assertion owner details, app paths, process names or log content into Git. Candidates for unsupported tasks do not expand the catalog or establish correctness.

B1 — confirm datatype availability, then inspect the power report. Cross-check Cycle Count in System Information → Hardware → Power ([Apple instructions](https://support.apple.com/en-nz/102888)). The manual documents datatype selection but does not enumerate SPPowerDataType or certify hardware field names.

```sh
system_profiler -listDataTypes
system_profiler SPPowerDataType
```

B2 — optional JSON/capacity investigation; record presence/absence of fields, not their values. No scalar-extraction recipe is proposed.

```sh
system_profiler -json SPPowerDataType
```

M1 — create only new disposable test files. The second filename tests literal shell characters; nothing inside the quotes executes. No automatic cleanup or edits to real documents.

```sh
validation_dir=$(mktemp -d /tmp/whatisit-manual.XXXXXX)
printf 'public test fixture\n' > "$validation_dir/a file.txt"
printf 'public test fixture\n' > "$validation_dir/a file'; \$(touch not-executed).txt"
mdls "$validation_dir/a file.txt"
```

M2/M3 — after M1, compare the two literal filenames and attribute-only output. Null metadata may be correct for an unindexed fixture; also select a nonprivate indexed test document if needed.

```sh
mdls "$validation_dir/a file'; \$(touch not-executed).txt"
mdls -name kMDItemContentType "$validation_dir/a file.txt"
```

S1/S2 — snapshot and optional continuous events. Do not confuse either with full historical diagnosis. Keep output private; stop S2 with Ctrl-C.

```sh
pmset -g assertions
pmset -g assertionslog
```

T1 — only after selecting a live disposable process, setting `test_pid` to its actual PID and confirming it yourself. Root is required; limit capture to five seconds. PID recycling and protected-process visibility remain risks. Do not use the authored PID 1234 blindly.

```sh
sudo fs_usage -w -f filesys -t 5 "$test_pid"
```

L1 — set `test_pid` and `service_target` explicitly after identifying the relevant process/domain/label. `procinfo` requires root and does not guarantee an owning service; `print` is diagnostic output, not a stable API or the original complete plist. No configuration changes.

```sh
sudo launchctl procinfo "$test_pid"
launchctl print "$service_target"
```

G1 — a concrete **synthetic** process/subsystem predicate using installed `log(1)` shorthand, severity error and explicit time bounds. It may return no events, which verifies syntax only. Replace values only when deliberately investigating a nonprivate test process; information/debug messages require their inclusion flags and may not be persisted. No log configuration changes or logging of private content.

```sh
log show --start '2026-10-08 10:00:00' --end '2026-10-08 10:01:00' --predicate 'p=whatisit-public-fixture and s=com.example.whatisit and type=error'
```

A1 — set `test_app` to an explicit public/disposable app bundle. Verification and assessment do not launch the app. No signing flags, Gatekeeper rule changes or global disabling. Local policy acceptance and signature verification are not complete notarization proof. Separate ticket tooling still needs documentation and device review before a concrete ticket command can be certified.

```sh
codesign --verify --deep --strict --verbose=2 "$test_app"
spctl --assess --type execute --verbose=2 "$test_app"
```

F1 — after M1 only. BSD syntax and read-only preview; find/du operate on the new fixture directory, not the whole disk. Size/allocation expectations depend on filesystem and block rounding.

```sh
stat -f '%z %Sp' "$validation_dir/a file.txt"
find "$validation_dir" -type f -mtime -1 -print
sed 's/public/example/' "$validation_dir/a file.txt"
du -sk "$validation_dir"
```

## Wheel isolation

Runtime dependencies remain empty; setuptools/wheel/packaging are build tools only. `recipes.json`, retrieval and manual-capture code ship in the wheel. The index is generated explicitly by the user at a writable chosen location, never shipped or silently discovered. Existing indexes cannot be overwritten; choose a new path after an OS update. Missing index errors remain visible while preserving routing status.

The source-tree `tools/build_docs.py` compatibility command forwards to the packaged implementation. Installed usage, from any directory:

```sh
python3 -m venv /tmp/whatisit-runtime
/tmp/whatisit-runtime/bin/python -m pip install /absolute/path/to/whatisit_macos-0.1.0-py3-none-any.whl
mkdir -p /tmp/whatisit-index
/tmp/whatisit-runtime/bin/whatisit-macos-build-docs /tmp/whatisit-index/manuals.sqlite3
/tmp/whatisit-runtime/bin/whatisit-macos --docs-index /tmp/whatisit-index/manuals.sqlite3 --json 'show sleep assertions'
```

The smoke script checks installed import location, no PYTHONPATH, empty runtime metadata, both entry points, packaged recipes, fresh manual capture on macOS (synthetic public index on Linux), retrieval, CLI status and missing-index behavior. It never runs suggestions. CI now builds and installs in separate temporary environments and runs that check outside the checkout. CI has not yet been observed running for this PR.

## Installed manual review hashes

SHA-256 of freshly rendered text; no manual text included.

| Manual | SHA-256 |
| --- | --- |
| codesign | `a36aa5ded2fef195fc3fea42e43e58407145ab29d24db839a3f9f351cf983318` |
| du | `4403e8c964ea667cd56e399ae60d0c34a2e705cfde5ad5f4e28b36b4731e1b06` |
| find | `dd768871e5b46e2798263c950caeb5bd000cf6d0a4afd5025a439cb57c5a4748` |
| fs_usage | `7dac4a70c335b826eaeb7289f48e8a0b0df995e5fa89b97b62af47f830139af5` |
| launchctl | `ed4285cc042c7985e5fd4d5a001e8613d66fdb5ea14dfb652a1549fd2c2d8e2a` |
| log | `dbfc3cbbe895aa4233b6a7d9c561e715d78476eeb5bac8fc98d87333590950a2` |
| mdls | `e63cdd475c7ed8cccb6c4883cbe5252320e592b30202f91149b5a962816ef1d5` |
| pmset | `8a3db2a25270f5f25dd5b03bb2968f674aff78eb38a6047020636b3589caff87` |
| sed | `104c4b3fab7d8d13d15352da1142e7ba54f2bda1f482cec8962f36d216e3285e` |
| spctl | `7e44425dedd5343beeb0735a4457b76d5cc40b9d5ce7c981851551353de6a3e6` |
| stat | `f90eeb02bb061d8949682b59e8caae7430953002eeb892accc7cab6f1bbaa5e0` |
| system_profiler | `051509d37a4b6e2b01941a71c8e4583beff3aa0e12ad6f35a166695f66bf155c` |

## Recorded wheel results

Built from implementation commit `27f23692216c2e25f317e9bf99b4e0f356d6a7d8`, before this results-only documentation update. Python 3.14.8 in both disposable environments. Build environment: pip 26.2.1, setuptools 84.0.0, wheel 0.48.0, packaging 26.3. Runtime environment: pip 26.2.1 and whatisit-macos 0.1.0 only. Runtime metadata has no `Requires-Dist` entries.

Wheel: `whatisit_macos-0.1.0-py3-none-any.whl`, 12,151 bytes, SHA-256 `cc9ec5443fcffa285f59579ad9a9310f12cf9ac3d01add51d6928c070aa6dd48`. Contents inspected: all seven package files (including recipes.json, retrieval.py and build_docs.py), license, metadata and two entry points; no captured SQLite index or private output.

Executed commands (temporary paths are public placeholders for these disposable directories):

```sh
python3 -m venv /tmp/whatisit-build
/tmp/whatisit-build/bin/python -m pip install --no-cache-dir 'setuptools>=77' wheel
/tmp/whatisit-build/bin/python -m pip wheel --no-build-isolation --no-deps . -w /tmp/whatisit-wheels
python3 -m venv /tmp/whatisit-runtime
/tmp/whatisit-runtime/bin/python -m pip install --no-index --no-deps /tmp/whatisit-wheels/whatisit_macos-0.1.0-py3-none-any.whl
# From /tmp; substitute your clone location for REPOSITORY:
env -u PYTHONPATH /tmp/whatisit-runtime/bin/python REPOSITORY/tools/wheel_smoke.py
```

The initial sandboxed download failed on network resolution; the authorized retry installed build tools only in the disposable build environment. No everyday Python environment was changed. The smoke check passed, including fresh system-manual capture into its own new temporary index (not the developer index). Capture reads manuals; lookup never executes `pmset` or another suggestion. The smoke's temporary index is cleaned by its temporary-directory context.

Final relevant suite: **33 tests passed** with the runtime environment's Python, outside the repository and with PYTHONPATH unset. Tests, evaluation fixtures and source-tree tooling were copied into `/tmp/whatisit-installed-tests`, with **no src package copied**; production imports came from the installed wheel. Invocation from that directory: `env -u PYTHONPATH /tmp/whatisit-runtime/bin/python -m unittest discover -s tests -v`. The same 33 source-tree tests passed before the wheel check. No Python 3.11 or cross-version device execution was performed locally.

## Issue acceptance assessment

- **#1:** acceptance met within deterministic catalog scope: seven fixes and one explicit manual-supported expectation dispute; all eight listed. Frozen comparison 32/40 → 39/40; no required values invented or Linux command introduced; original expectations untouched. The old held-out set is preserved but no longer independent; fresh held-out data remains necessary for #4.
- **#2:** every task reviewed and disposition recorded, but **not complete**: all eight command suggestions still require human execution; unsupported tracing/launchd/log/signing candidates also have no device execution evidence. Useful correct coverage and answer accuracy remain unmeasured. Concrete manual checks above support follow-up without publishing private output.
- **#3:** local acceptance met: recorded-commit wheel build, contents/metadata inspection, clean install, outside-repository checks, fresh retrieval setup, missing-index behavior and installed suite pass. CI extension is present; remote CI results remain pending.
- **#4:** no model integration. Prerequisites are not all complete, so no model comparison or resource-budget claim is made.

## Review blocker: executable/manual identity

Review of head `313a27c` found that PATH-selected third-party executables could be paired with Apple's `/usr/share/man` documentation. Fixed capture to resolve both manual and authored catalog executable provenance only in `/usr/bin`, `/usr/sbin`, `/bin` and `/sbin`. A missing system executable remains unavailable; PATH replacements are not a fallback. Suggested commands still require human review, including which executable the shell will select.

The regression creates a shadow `stat` on PATH and simulates macOS manual rendering while using the real capture/index/search code. Before the fix it recorded the shadow executable with the Apple BSD manual; after the fix both inventory and manual/catalog retrieval evidence name `/usr/bin/stat`. The test never executes either stat binary. Full source and outside-repository installed-wheel suites: **34 tests passed**. A rebuilt wheel installed into a fresh runtime environment also passed the fresh-manual capture and retrieval smoke check. Original routing fixture, 39/40 fixture-specific score and performance observations are unchanged; lookup/startup and query ranking were not modified, so no latency rerun was needed.

Older local indexes are not rewritten: rebuild to a new filename to obtain corrected provenance. #2 remains open for human command validation; #4 remains deferred. The additional compound, previous-boot and CSV routing examples from review remain documented prototype follow-up work, not covered by the 39/40 fixture score.
