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

## All 40 initial dispositions (before device checks)

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

These commands were initially prepared without execution. The core and remaining-candidate outcomes are recorded below; root tracing/process-context and controlled log-event semantics remain incomplete. Run individual groups after review. Keep raw reports local; record only task ID, command shape, success/failure, whether required fields were present, privileges, limitations, macOS build and date. Do not paste serial numbers, assertion owner details, app paths, process names or log content into Git. Candidates for unsupported tasks do not expand the catalog or establish correctness.

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

## Initial issue acceptance assessment (before device checks)

- **#1:** acceptance met within deterministic catalog scope: seven fixes and one explicit manual-supported expectation dispute; all eight listed. Frozen comparison 32/40 → 39/40; no required values invented or Linux command introduced; original expectations untouched. The old held-out set is preserved but no longer independent; fresh held-out data remains necessary for #4.
- **#2:** every task reviewed and disposition recorded, but **not complete**: all eight command suggestions still require human execution; unsupported tracing/launchd/log/signing candidates also have no device execution evidence. Useful correct coverage and answer accuracy remain unmeasured. Concrete manual checks above support follow-up without publishing private output.
- **#3:** local acceptance met: recorded-commit wheel build, contents/metadata inspection, clean install, outside-repository checks, fresh retrieval setup, missing-index behavior and installed suite pass. CI extension is present; remote CI results remain pending.
- **#4:** no model integration. Prerequisites are not all complete, so no model comparison or resource-budget claim is made.

## Review blocker: executable/manual identity

Review of head `313a27c` found that PATH-selected third-party executables could be paired with Apple's `/usr/share/man` documentation. Fixed capture to resolve both manual and authored catalog executable provenance only in `/usr/bin`, `/usr/sbin`, `/bin` and `/sbin`. A missing system executable remains unavailable; PATH replacements are not a fallback. Suggested commands still require human review, including which executable the shell will select.

The regression creates a shadow `stat` on PATH and simulates macOS manual rendering while using the real capture/index/search code. Before the fix it recorded the shadow executable with the Apple BSD manual; after the fix both inventory and manual/catalog retrieval evidence name `/usr/bin/stat`. The test never executes either stat binary. Full source and outside-repository installed-wheel suites: **34 tests passed**. A rebuilt wheel installed into a fresh runtime environment also passed the fresh-manual capture and retrieval smoke check. Original routing fixture, 39/40 fixture-specific score and performance observations are unchanged; lookup/startup and query ranking were not modified, so no latency rerun was needed.

Older local indexes are not rewritten: rebuild to a new filename to obtain corrected provenance. #2 remains open for human command validation; #4 remains deferred. The additional compound, previous-boot and CSV routing examples from review remain documented prototype follow-up work, not covered by the 39/40 fixture score.


## Authorized core device checks — 2026-10-08

Checked reviewed implementation `1602dea` on macOS 27.0.1 (26A434), arm64, Python 3.14.8, around 18:43 UTC (21:43 Helsinki). The user explicitly authorized these selected checks after clearing the provenance blocker. Commands were invoked individually through fixed argument lists; the evaluator was not changed and does not execute suggestions. No root privileges were used. Raw battery/owner/metadata output was inspected in memory for the conditions below and was not printed, saved or committed.

| Check | Command shape | Observed outcome | Scope and remaining limitation |
| --- | --- | --- | --- |
| B1 datatype | `/usr/sbin/system_profiler -listDataTypes` | Exit 0; SPPowerDataType present. | Confirms the selected datatype on this Mac only. |
| B1 report | `/usr/sbin/system_profiler SPPowerDataType` | Exit 0; Battery Information section, numeric Cycle Count and capacity field present; no stderr. | Validates basic report availability for battery-report/battery-cycles/battery-phrase. Actual field values and identifying information omitted. GUI cross-check, scalar extraction and JSON/capacity task completeness not validated. |
| M1 basic metadata | `/usr/bin/mdls <disposable-file-with-spaces>` | Initial sandbox attempt: exit 1, could not find an existing fixture. Outside sandbox: exit 0, metadata attributes present, no stderr. Original /tmp spelling also succeeds outside sandbox. | Confirms successful one-file inspection in an unrestricted user process; sandbox access is a real limitation. Uses a new public text fixture, not the frozen nonexistent PDF input. |
| M2 literal metacharacters | `/usr/bin/mdls <disposable-file-with-literal-shell-characters>` | Outside sandbox: exit 0, metadata attributes present, no stderr; no unexpected touch file created. | Public fixture with spaces, quote and literal command-substitution characters remains one argument. Frozen fixture quoting is covered by tests; actual PDF fixture was not created or inspected. |
| M3 named attribute | `/usr/bin/mdls -name kMDItemContentType <disposable-file>` | Outside sandbox: exit 0; requested attribute present and non-null. | Confirms the prepared candidate's flag on the public text fixture; catalog still abstains on attribute-only requests. |
| S1 snapshot | `/usr/bin/pmset -g assertions` | Exit 0; system-wide assertion summary and owning-process section present; no stderr. No Kernel Assertions section in this capture. | Validates snapshot output availability for sleep-assertions/sleep-blockers. No assertion-owner data committed. Does not prove historical, continuous or exhaustive sleep diagnosis; absence of a kernel section is not an output failure. |

A new index was built with corrected capture code at ignored `.cache/manuals-system-1602dea.sqlite3`, retaining the original measurement index unchanged. It contains 15 documents, is 487,424 bytes, and all recorded executables are in Apple system directories. SHA-256: `ccde0ec0869cb49406041e342f9bbc2b9b9db50cae68f85a60d389dec7bd0a7d`. No older index was overwritten or deleted.

These are successful device checks of the three core recipe command shapes with explicit public test inputs. They do not convert the frozen 39/40 routing contract score into measured answer accuracy. The initial 40-task table and zero-execution counts above are historical, before these checks; metadata success here uses substituted public text fixtures. Independent human semantic review and exact-fixture evaluation are still outstanding. #2 remains open for remaining manual validation (including tracing, launchd, logs, signing/policy/tickets and broader limitations); #4 remains deferred.

Continuous assertions logging, optional battery JSON, and the unsupported task command groups were not run. No code, fixture expectation or routing change was needed, so tests and timing measurements were not rerun for this documentation-only update. The preceding code head has 34 passing tests and both CI runs green.

## Remaining candidate checks and semantic review — 2026-10-08

PR #5 was marked ready and merged at `fbdcb10b289001baf2c0e444bb963e421262a4fd` after verifying both CI runs on `e943287` were green. Follow-up evidence is recorded separately on `docs/remaining-macos-validation`. Same target macOS 27.0.1 (26A434), arm64, Python 3.14.8. These are user-authorized individual checks; no evaluator execution path or new recipe was added. Only public system files and new disposable fixtures were selected. Raw logs, owner details and private files were neither published nor saved.

| Task IDs / check | Device evidence | Semantic disposition |
| --- | --- | --- |
| bsd-stat / F1 | BSD `/usr/bin/stat -f '%z %Sp' <public-file>` exits 0 and reports the known 20-byte fixture size and expected mode. | Candidate validated for a regular file. Search permission, symlink handling and arbitrary file access still depend on input. Router remains unsupported; GNU flags were not tested as BSD flags. |
| bsd-find / F1 | `/usr/bin/find <new-fixture-directory> -type f -mtime -1 -print` exits 0 and identifies the fixture. | Candidate validated for bounded recent-file discovery. “Last day” here means age under 24 hours, not the preceding calendar day; caller must supply root. No deletion flag. |
| bsd-sed / F1 | `/usr/bin/sed 's/public/example/' <public-file>` exits 0 with expected preview; source bytes unchanged. | Candidate validated for the supplied expression. No `-i`, file rewrite or general expression validation. |
| bsd-du / F1 | `/usr/bin/du -sk <new-fixture-directory>` exits 0 with numeric allocation summary. | Command/output shape validated, not exact APFS space attribution. Output is allocation in KiB, not apparent file length. |
| battery-health / B2 | `/usr/sbin/system_profiler -json SPPowerDataType` exits 0; JSON parses; selected datatype, cycle and capacity keys present. | Device availability confirmed. Existing recipe still omits JSON and does not guarantee the requested maximum-capacity schema; original unsupported expectation retained. No numeric extraction added. |
| sleep-live / S2 | Outside sandbox, `pmset -g assertionslog` remained running for three seconds with output and no stderr/failure markers; its monitoring process was then terminated. No creation/release event markers observed. | Starting monitoring does not establish complete event capture; creation/release semantics and absence of missed events remain conditional on observed events. No retroactive 24-hour history claim. |
| signature-only / A1 | `/usr/bin/codesign --verify --deep --strict --verbose=2 /System/Applications/Utilities/Terminal.app` exits 0 outside sandbox; valid-on-disk and designated-requirement messages present. Initial sandbox attempt exits 1. | Signature candidate validated for the explicit Apple system bundle only. No app launch or signing operation. Not a notarization result and not a test of every third-party bundle. |
| gatekeeper-only / A1 | `/usr/sbin/spctl --assess --type execute --verbose=2 /System/Applications/Utilities/Terminal.app` exits 0 outside sandbox; accepted with Apple System source. Initial sandbox attempt exits 1. | Local policy candidate validated for Apple system code. Does not establish Developer ID notarization, offline availability, ticket presence or acceptance on another Mac. |
| app-audit, notarization-only | Installed CLT stapler(1) reviewed; user-selected iTerm2 stable artifact checks recorded below. | Signature, local policy and ticket validation pass for the exact public artifact. This does not establish general app-audit coverage or future/offline policy outcomes. |
| unified-filter, logs-missing / G1 | Synthetic process/subsystem/error predicate with explicit one-minute bounds exits 0 outside sandbox; only header output, no matching events. Initial sandbox attempt exits 64. | Syntax/access validated; matching/nonmatching process, subsystem, severity and time behavior **unverified** without controlled events. Empty output is not semantic proof. No log emission/configuration changes. |
| launchd-label / L1 | `/bin/launchctl print system/com.apple.logd` exits 0; public on-disk plist origin is readable, its Label matches the requested service and program configuration is present. | Validates explicit domain/label inspection. Missing label/domain tasks still abstain. Runtime debug output is not a stable API or complete substitute for original configuration. |
| launchd-owner / L1 | `sudo -n launchctl procinfo <live-disposable-pid>` exits 1: authentication required. No process diagnostic output obtained. | **Blocked** on human root check; PID→service ownership still unverified and not guaranteed by procinfo even if it succeeds. |
| filesystem-pid, trace-missing / T1 | `sudo -n fs_usage -w -f filesys -t 5 <live-disposable-pid>` exits 1: authentication required. No trace events obtained. Disposable process only read a new public fixture and was stopped afterward. | **Blocked** on human root check. PID filtering, useful event visibility and protected-process limitations remain unverified. No password requested or collected. |

All candidates above remain outside the three-recipe catalog; successful tool invocations do not change fixture expectations or make unsupported tasks answered. Initial and latest outcomes are separated. Useful correct coverage and full answer accuracy remain unmeasured; #2 stays open and #4 stays deferred.

### Root checks remaining under human control

Run in your terminal after review. Create a fresh public fixture and a live disposable reader; do not use a stale PID from this session. The reader lasts about 20 seconds. Stop only that reader if still alive after the checks. Do not share the raw trace or procinfo output; report exit status, whether the expected PID's file operations were visible, and whether process context sufficed to identify an owner (including when it did not).

```sh
trace_dir=$(mktemp -d /tmp/whatisit-trace-manual.XXXXXX)
printf 'public test fixture\n' > "$trace_dir/public.txt"
python3 -c 'import pathlib,sys,time; p=pathlib.Path(sys.argv[1]); [(p.read_bytes(),time.sleep(.05)) for _ in range(400)]' "$trace_dir/public.txt" &
test_pid=$!
sudo fs_usage -w -f filesys -t 5 "$test_pid"
sudo launchctl procinfo "$test_pid"
kill "$test_pid" 2>/dev/null
```

For a chosen public Developer ID bundle, the installed stapler(1) supports the read-only candidate below. The manual says validation may contact the ticket service; distinguish network failure, missing/invalid ticket and successful validation. Missing ticket alone must not be reported as proof that the app was never notarized. No `staple` mutation or notarization submission is proposed.

```sh
/Library/Developer/CommandLineTools/usr/bin/stapler validate -q "$test_app"
```

This is documentation-only evidence. No routing, retrieval-query, startup, runtime dependency or packaging change; no performance rerun or new tests are needed. The merged implementation retains its 34-test/CI validation.


## Public Developer ID artifact verification — 2026-10-09

The user selected iTerm2's stable release from the [official download page](https://iterm2.com/downloads.html). The page identified version **3.7.4**, built October 8, 2026, and published a SHA-256 checksum for its archive. Downloaded [iTerm2-3_7_4.zip](https://iterm2.com/downloads/stable/iTerm2-3_7_4.zip) into a new disposable directory, checked its hash before extraction, and extracted with Apple's `ditto`. Bundle version/build: 3.7.4; identifier: `com.googlecode.iterm2`. No installation, launch, registration, signing, stapling or notarization submission was performed.

Archive size: **57,903,700 bytes**. Local SHA-256 **matches the publisher's checksum**: `4bf02ae616752600cd195ca504e55392afb21741cda7314199e375ed8a46f90c`. This is an HTTPS-page checksum comparison; the page's PGP signature was not independently verified. Platform code-signature verification below supplies separate integrity/identity evidence.

| Check | Command shape | Observed result | Scope |
| --- | --- | --- | --- |
| Developer ID identity | `/usr/bin/codesign --display --verbose=4 <extracted-iTerm.app>` | Exit 0; `Developer ID Application: GEORGE NACHMAN (H7V7XYVQ7D)`; TeamIdentifier `H7V7XYVQ7D`. | Confirms the expected public developer identity on this artifact, not just its filename. |
| Signature integrity | `/usr/bin/codesign --verify --deep --strict --verbose=2 <extracted-iTerm.app>` | Exit 0; valid on disk; designated requirement satisfied. | Explicit public bundle, no launch. Successful integrity evidence on this target Mac. |
| Gatekeeper assessment | `/usr/sbin/spctl --assess --type execute --verbose=2 <extracted-iTerm.app>` | Exit 0; accepted; source `Notarized Developer ID`. | Local policy assessment at check time. Not a guarantee for other machines, future revocation/cache state, offline execution or application runtime safety. |
| Stapled ticket | `/Library/Developer/CommandLineTools/usr/bin/stapler validate -q <extracted-iTerm.app>` | Exit 0; quiet output empty. | Installed manual defines exit 0 as successful validation, including ticket contents/service comparison. Not merely an inference from Gatekeeper acceptance. |
| Integrity negative control | Same codesign verification on a **separate copy** with a new public marker added to its otherwise valid Info.plist | Exit 1; modified resource/plist rejected. Original Info.plist remained unchanged. | Demonstrates rejection of changed signed content. Does not test Gatekeeper/ticket behavior for the tampered copy. |

Target: macOS 27.0.1 (26A434), arm64; same Apple codesign/spctl paths and manuals as earlier. Stapler executable SHA-256: `bd5c8be8ca488e7a47e7562a16b5a2c6f2bfea5b4bdba62c87a23c76549c2bdc`. Installed manual `/Library/Developer/CommandLineTools/usr/share/man/man1/stapler.1`, raw-file SHA-256: `6a687f46a5131aa51b7eecbfb7fe9ed51476e222fb3e21b5fcba7c991a975712`. Stapler validation may contact Apple's ticket service and was run with network access; this was not an offline test. No extra dependencies or user credential access were needed.

The optional negative-control operation first encountered an automatic approval-review timeout with no command result. Splitting disposable copy preparation from read-only verification allowed the single retry to complete. This was not a detected signature problem with the original download.

This provides a positive public Developer ID example for signature-only, gatekeeper-only, notarization-only and the separate steps of app-audit. It does not change their catalog `unsupported` dispositions: no input-aware audit recipe exists. Missing/invalid/revoked-ticket failure distinctions and a non-notarized Developer ID example remain untested. Filesystem tracing and launchctl procinfo remain blocked on human sudo authentication; matching/nonmatching log-filter semantics remain unverified because the synthetic query had no events. All 40 tasks retain dispositions; **#2 remains open** until these gaps and independent semantic review are addressed, and **#4 remains deferred**. No full answer-accuracy figure is claimed.

## iTerm2 3.7.3 observed artifact results — 2026-10-09

Separately inspected version **3.7.3** from the [official download URL](https://iterm2.com/downloads/stable/iTerm2-3_7_3.zip), linked by the [official downloads page](https://iterm2.com/downloads.html). This is a separate artifact from the 3.7.4 check above. The ZIP was downloaded and extracted into a new disposable directory with Apple's `ditto`; **the app was inspected without launching or installing it**. No signing, stapling, registration or notarization submission was performed. Temporary paths and raw diagnostic output are omitted.

Observed ZIP size: **57,887,250 bytes**. Observed ZIP SHA-256: `eb7a166061e58602e3d4bdf69d92f2c8cf6a63feed002f6adc07128a71c8dc39`. **This hash is an observed artifact identifier, not independently authenticated provenance.** No independently verified publisher PGP signature or trusted digest channel is claimed. The code-signature, local policy and ticket results below are separate observations.

| Check | Sanitized observed result |
| --- | --- |
| Bundle | Version 3.7.3; bundle ID `com.googlecode.iterm2`; executable `Contents/MacOS/iTerm2`. |
| Universal architectures | `/usr/bin/lipo -archs <main-executable>` exits 0: `x86_64 arm64`. Architectures refer to the main executable, not every nested component. |
| Developer ID / team | `/usr/bin/codesign --display --verbose=4 <bundle>` exits 0: `Developer ID Application: GEORGE NACHMAN (H7V7XYVQ7D)`; TeamIdentifier `H7V7XYVQ7D`. |
| Code-signature verification | `/usr/bin/codesign --verify --deep --strict --verbose=2 <bundle>` exits 0: valid on disk; designated requirement satisfied. |
| Gatekeeper | `/usr/sbin/spctl --assess --type execute --verbose=2 <bundle>` exits 0: accepted; `source=Notarized Developer ID`. |
| Stapled ticket / validation | `/Library/Developer/CommandLineTools/usr/bin/stapler validate -v <bundle>` exits 0 and reports successful validation. This confirms a valid stapled ticket for the inspected bundle, separately from Gatekeeper's source classification. |

Target: macOS 27.0.1 (26A434), arm64; Python 3.14.8 used only to invoke the fixed inspection commands and sanitize output. The system codesign/spctl and CLT stapler provenance is recorded above. No root privileges or user credentials were required. Stapler validation ran with network access and may consult Apple's ticket service; no offline guarantee is established. Successful checks apply to this exact artifact on this Mac at check time, not other apps, future policy/revocation state, runtime behavior or full answer accuracy.

Documentation-only update: source code, evaluation fixtures, performance measurements and model deferral are unchanged. #2 remains open and #4 remains deferred.

## Current #2 reconciliation — 2026-10-09

This ledger supersedes the initial pending counts and acceptance assessment above. It reconciles every ID in the frozen [40-task fixture](../eval/macos.jsonl) and every work item in [issue #2](https://github.com/imaddde867/whatisit-macos/issues/2). The initial reconciliation added no device checks; subsequent authorized G2 and bounded R1 attempts are recorded in E7/E8. G2 and the human-authenticated R1 completion each update two device-result rows; the earlier blocked R1 attempt is retained as history. Target, privileges, input substitutions, manual/tool provenance and observation dates are recorded in the linked evidence; the reconciliation date is not itself a new execution date.

Three results are separate: **fixture result** tests routing against the original expectation; **device result** assesses the concrete check described in the row, including candidates outside the catalog; **semantic review** assesses whether the final response is supported within its declared scope. The semantic column records the review below, not another command run or an independent benchmark. `passed` means that bounded check succeeded, `failed` means it contradicted its stated expectation, `blocked` means a prerequisite prevented validation, and `untested` means the required observation is absent. A passed abstention is not an answered task. An untested device result may be appropriate where the correct response requires no command. A passed representative-input check is not exact-fixture execution or independent answer accuracy.

Evidence references:

- [E1: installed-manual review and all 40 initial dispositions](#all-40-initial-dispositions-before-device-checks), with [manual hashes](#installed-manual-review-hashes) and [original expectation disputes](#original-eight-disagreements).
- [E2: recorded routing comparison and separate resource/retrieval results](MEASUREMENTS.md#follow-up-routing-and-packaging-validation); [regression and installed-suite evidence](#review-blocker-executablemanual-identity). These are not device command checks.
- [E3: core device checks](#authorized-core-device-checks--2026-10-08): B1 report, M1/M2 public text metadata fixtures, M3 selected attribute and S1 assertion snapshot.
- [E4: remaining candidate checks](#remaining-candidate-checks-and-semantic-review--2026-10-08): BSD tools, battery JSON, live assertions, bounded logs, explicit launchd service and blocked root queries.
- [E5: iTerm2 3.7.4 signature/policy/ticket checks and signature negative control](#public-developer-id-artifact-verification--2026-10-09).
- [E6: separate iTerm2 3.7.3 artifact, identity, architectures and signature/policy/ticket checks](#iterm2-373-observed-artifact-results--2026-10-09). Its ZIP hash is an observed identifier, not independently authenticated provenance.
- [E7: G2 controlled log-event results](#g2-observed-results--2026-10-09): five public events and independent subsystem/level/PID/time controls.
- [E8: initial bounded R1 attempt and cleanup](#bounded-r1-observed-results--2026-10-09): fresh public selected/decoy processes, exact root-authentication failure and no trace execution.
- [E9: human-authenticated R1 completion](#human-authenticated-r1-results--2026-10-09): successful bounded selected/decoy trace and verified cleanup, without procinfo or protection changes.

| Task ID | Fixture result / catalog disposition | Device result | Semantic review | Evidence and scope; remaining requirement |
| --- | --- | --- | --- | --- |
| battery-report | passed / suggestion | passed | supported report | E1–E3 B1: datatype and numeric Cycle Count present in report. GUI cross-check not performed; no scalar answer claimed. |
| battery-cycles | passed / suggestion | passed | supported report | E1–E3 B1: same report check, not a second independent execution or numeric extraction. |
| metadata-missing | passed / needs-input | untested | supported boundary | E1/E2: explicit file path requested. No runnable command without input; device execution unnecessary for this clarification. |
| metadata-file | passed / suggestion | passed | supported report | E1–E3 M1: public text fixture inspected successfully. Frozen PDF path not executed; public-file substitution accepted for this generic metadata task. Missing/null attributes are permitted by recipe notes, not promised populated fields. |
| sleep-assertions | passed / suggestion | passed | supported report | E1–E3 S1: current summary and owner section present. Snapshot only, not exhaustive causality. |
| sleep-blockers | passed / suggestion | passed | supported report | E1–E3 S1: shared snapshot evidence, not independent execution or historical coverage. |
| filesystem-pid | passed / unsupported | passed | supported abstention | E1/E2/E4/E8/E9: earlier authentication block retained; human-authenticated trace exits 0 with reads/writes and selected-fixture lines, no decoy-fixture lines. Scoped candidate success; catalog remains unsupported. |
| launchd-owner | passed / unsupported | blocked | supported abstention | E1/E2/E4 L1: procinfo denied without authentication. PID-to-service ownership/configuration remains unverified; an arbitrary process need not be a service. |
| unified-filter | passed / unsupported | passed | supported abstention | E1/E2/E4/E7: G1 was syntax-only; G2 now validates bounded public subsystem/error-versus-default/PID/time controls and their conjunction. Arbitrary process-name matching, info/debug persistence and general log coverage remain unverified. |
| app-audit | passed / unsupported | passed | supported abstention | E1/E2/E5/E6: separate signature, Gatekeeper and ticket checks succeed on explicit public bundles without launch. No combined audit recipe, general failure taxonomy or full answer coverage established. |
| bsd-stat | passed / unsupported | passed | supported abstention | E1/E2/E4 F1: known size/mode matched using BSD flags on a public regular file. Input still required; not GNU compatibility or symlink coverage. |
| bsd-find | passed / unsupported | passed | supported abstention | E1/E2/E4 F1: bounded directory fixture found using age-under-24-hours semantics, without deletion. Caller must supply root; calendar-day interpretation excluded. |
| bsd-sed | passed / unsupported | passed | supported abstention | E1/E2/E4 F1: expected substitution preview; source unchanged. Explicit expression/file required; no in-place editing tested. |
| bsd-du | passed / unsupported | passed | supported abstention | E1/E2/E4 F1: allocation-summary command/output shape succeeds. Exact APFS attribution and apparent-size comparison untested; no exact space claim. |
| mutate-metadata | passed / unsupported | untested | supported abstention | E1/E2: mutation outside inspection scope; deliberately no destructive execution required. |
| mutate-sleep | passed / unsupported | untested | supported abstention | E1/E2: mutation outside scope; deliberately no power-setting changes required. |
| compound | passed / ambiguous | untested | supported boundary | E1/E2: ask for one supported task instead of partial output. No device command needed for clarification. |
| empty | passed / unsupported | untested | supported abstention | E1/E2: no request, no fabricated command; execution unnecessary. |
| linux | passed / unsupported | untested | supported abstention | E1/E2: no strace suggestion; retrieval miss retained. macOS tracing candidate passed bounded public-fixture validation in E9; Linux command deliberately not executed. |
| unknown | passed / unsupported | untested | supported abstention | E1/E2: outside catalog, no command; execution unnecessary. |
| battery-health | passed / unsupported | untested | supported abstention | E1/E2/E4 B2: JSON parses with cycle/capacity keys, but requested maximum-capacity schema/completeness unverified. Plain-text catalog recipe still cannot answer the whole request. |
| battery-number | passed / unsupported | untested | supported abstention | E1/E2/E3 B1: report is not scalar output. No extraction recipe or scalar execution exists; abstention is appropriate. |
| battery-phrase | passed / suggestion | passed | supported report | E1–E3 B1: shares basic report evidence; device with no battery and independent paraphrase accuracy untested. |
| metadata-paraphrase | passed / needs-input | untested | supported boundary | E1/E2: synonym routing corrected; request document path. No device command required until supplied. |
| metadata-spaces | passed / suggestion | passed | supported report | E1–E3 M1: public text path with spaces succeeds; quoting regression covers frozen path. Exact authored PDF input untested; representative path substitution accepted, not PDF-importer validation. |
| metadata-shell | passed / suggestion | passed | supported report | E1–E3 M2: literal shell characters remain one direct argument; no unexpected touch file. Rendered shell quoting tested, not executed as a shell command; exact PDF input untested; representative path substitution accepted. |
| metadata-attribute | passed / unsupported | passed | supported abstention | E1–E3 M3: named attribute present/non-null on public text fixture. Current all-attribute recipe lacks filtering; frozen PDF and null cases untested. |
| metadata-recursive | passed / unsupported | untested | supported abstention | E1/E2: one-file recipe lacks traversal/input policy. No recursive candidate tested; implementing traversal is not necessary to validate abstention. |
| sleep-paraphrase | failed / unsupported | untested | supported abstention; fixture disputed | E1/E2: sole frozen disagreement; manual-supported expectation dispute, not observed command failure. S1 is only one diagnostic step. Semantic adjudication below supports conservative abstention; frozen expectation remains unchanged. |
| sleep-history | passed / unsupported | untested | supported abstention | E1/E2/E3: snapshot cannot reconstruct 24 hours; no historical assertion recovery tested or promised. |
| sleep-live | passed / unsupported | untested | supported abstention | E1/E2/E4 S2: monitor starts, but no creation/release markers observed. Controlled assertion-event capture required to validate candidate semantics; snapshot recipe still abstains. |
| trace-missing | passed / unsupported | passed | supported abstention | E1/E2/E4/E8/E9: supplied fresh owned PID validates bounded public-file tracing and fixture exclusion. Original request still lacks PID; no input invented or new catalog recipe added. |
| launchd-label | passed / unsupported | passed | supported abstention | E1/E2/E4 L1: explicit system/com.apple.logd configuration inspected with matching public plist label. Request omits domain/label; candidate success does not fill them in. |
| logs-missing | passed / unsupported | passed | supported abstention | E1/E2/E4/E7: request still lacks subsystem/time, so catalog abstention remains appropriate. Explicit G2 public inputs validate candidate filters only, not the incomplete original request. |
| signature-only | passed / unsupported | passed | supported abstention | E1/E2/E4–E6: system/public Developer ID bundle signatures verify; changed signed plist rejected on separate 3.7.4 copy. No launch; no input-aware catalog recipe. |
| gatekeeper-only | passed / unsupported | passed | supported abstention | E1/E2/E4–E6: Apple System and Notarized Developer ID acceptance observed separately. Local policy at check time only; offline/revocation cases untested. |
| notarization-only | passed / unsupported | passed | supported abstention | E1/E2/E5/E6: stapled tickets validate separately from Gatekeeper. Missing/invalid/revoked-ticket distinctions untested; absent ticket must not imply never notarized. |
| linux-stat | passed / unsupported | untested | supported abstention | E1/E2/E4: installed BSD synopsis lacks GNU --printf; BSD candidate succeeds separately. Incompatible flag deliberately not presented or executed. |
| irrelevant-path | passed / needs-input | untested | supported boundary | E1/E2: reject irrelevant path and ask for removal. Boundary check, no device command required. |
| metadata-newline | passed / needs-input | untested | supported boundary | E1/E2: reject control character before rendering. Boundary check, no device command required. |
Fixture results: **39 passed, 1 failed** (the retained sleep-paraphrase dispute). Current device results after G2 and R1: **22 passed within the stated scope, 1 blocked, 17 untested**; there is no unresolved observed command failure in the recorded successful scopes. Initial sandbox failures remain recorded in E3/E4, followed by unrestricted checks; the earlier launchd-owner procinfo attempt remains historically blocked, while R1 tracing now passes. These counts mix shared recipes, public-input candidates and intentionally unexecuted abstentions and therefore are **not accuracy or coverage denominators**.

### Issue work and acceptance reconciliation

| #2 work item | Status | Evidence / remaining work |
| --- | --- | --- |
| Review all 40 tasks/expectations against installed manuals and relevant official documentation | passed | E1 plus E3–E6, recipe argv/notes and the semantic review below support all final dispositions within declared catalog scope. This agent review is not an independent accuracy study. |
| Manually validate answerable commands/flags with appropriate inputs, under human control | passed | E3 validates all three supported recipe shapes with declared public-input substitution. Exact authored paths and PDF importers are not certified. Prioritized bounded tracing also passed E9; general service ownership remains unverified separately. No evaluator execution added. |
| Validate clarification/abstention for missing, ambiguous and unsupported tasks | passed | E1/E2 plus semantic review below support the 32 non-command responses. sleep-paraphrase is a disputed fixture expectation, not a semantic failure of conservative abstention. Historical score stays 39/40. |
| Record task, environment, provenance, privileges, behavior, completeness, limits and date | passed | All 40 rows link to E1–E9; shared environment/provenance applies explicitly. Blocked, substituted-input and untested observations remain distinguishable. |
| Separate retrieval candidates from final suggestions; prioritize tracing, launchd, logs, signing/policy/tickets | passed within reviewed scope | E2 distinguishes retrieval; E4–E9 distinguish candidate checks. Signing/policy/ticket, G2 filters, bounded R1 tracing and explicit launchd configuration passed. General PID-to-service ownership remains unsupported/unverified; earlier procinfo attempt blocked and no ownership method certified. |
| Correct recipes/expectations only with evidence; add meaningful regressions | passed | E1/E2: seven routing fixes, explicit retained dispute, substantive routing/provenance regressions. This reconciliation changes no recipe or expectation. |

Disposition and semantic review are complete within declared prototype scope; prioritized candidate execution/semantics and a fully specified answer-accuracy assessment remain incomplete. Metrics remain separate: routing **32/40 → 39/40**, retrieval **34/35**, suggestion rate **8/40 (20%)**, abstention/unresolved **32/40 (80%)**, static wrong-platform suggestions **0/40**. Useful correct coverage and answer accuracy remain **unmeasured**; neither tool-name matches nor the 22 bounded device passes measure them. Resource measurements in E2 remain historical and unchanged. No personal paths, raw logs, private contents or secrets are added here.

### Semantic review and resolved inputs — 2026-10-09

Reviewed all 40 requests, frozen rubrics, current recipe argv/notes and E1–E6 at `b746cb6`. Re-read installed mdls(1), pmset(1), system_profiler(8), fs_usage(1), launchctl(1), log(1) and caffeinate(8); read installed `log help predicates` and `log help emit` outside the sandbox. Help exits 64 by design; the initial sandbox denial is not device-validation evidence. No task command, controlled event, model, test or benchmark was run. This is the same agent's evidence review, not independent human sign-off or a fresh held-out assessment.

Newly reviewed raw manual `/usr/share/man/man8/caffeinate.8` SHA-256: `dcde2d301a6be6151afc331cbb5ab3b855e2e7a2a88c9a7db2e58c8195d33711`. Other manual provenance remains in E1. Installed log help takes precedence for the proposed predicate field names; reading help does not prove their event-filter semantics.

- **Eight suggestions:** three battery requests are satisfied by a report containing Cycle Count, with instructions to read that field; they do not request scalar/JSON output. Two sleep requests ask for assertions, so the observed current summary/owners and explicit snapshot limitation fit. Three metadata requests ask for Spotlight attributes of one file, not PDF-specific content, a fixed non-null schema or filesystem-complete metadata. The observed public text fixtures satisfy that declared input protocol. Report availability and semantic suitability are supported; values, exhaustive causality and application-specific fields are not certified.
- **Four input responses and one ambiguity:** explicit path is required for the two missing-file requests, irrelevant battery paths and control-character paths are rejected, and the compound request asks for one supported task. No invented input or device execution is required to validate these responses.
- **Twenty-seven unsupported responses:** mutation, Linux flags/tools, unknown/empty requests, unavailable catalog families and unsupported output/traversal/history/live qualifiers appropriately abstain within this prototype. Missing domain/PID/filter/app arguments are reasons a future recipe would need clarification; they do not require changing today's unsupported status when no such recipe exists. Candidate successes are not final suggestions or useful coverage.
- **sleep-paraphrase adjudication:** “What is keeping my computer awake?” may reasonably invite an assertion report as a partial diagnostic step, but the rubric expects a final suggestion while the recipe explicitly disclaims complete causality. Conservative abstention is supported; the original expectation is contestable rather than universally wrong. Keep its routing failure, fixture bytes and 39/40 score. This semantic decision does not add a passing fixture case.

Input decisions: retain the exact authored paths/PID in the frozen comparison, but never execute placeholder PID 1234 or create files at those global paths. E3's new public text files are accepted substitutions for generic one-file metadata and path handling; no PDF rerun is needed unless PDF-importer behavior becomes a claim. A null attribute is compatible with the recipe's caveat; it cannot establish why indexing is absent. Battery hardware/field presence is already observed; GUI comparison, scalar extraction and maximum-capacity JSON schema are unnecessary to support existing basic reports or abstentions. `du -sk` reports allocated KiB, not exact APFS physical-space ownership, so allocation attribution is a retained limit, not a new closure gate.

The frozen metadata-shell input also contains an embedded slash in its command-substitution text, so as a literal path it denotes a directory hierarchy rather than one filename. E3 intentionally uses a real single filename with equivalent quoting characters; it does not certify that authored hierarchy exists. Regression evidence covers rendering the original path bytes. Neither input protocol interprets those characters as a shell fragment.

For remaining candidates, bind each missing input explicitly: fresh owned PID and public file for tracing; current domain/label/PID for launchd; unique public subsystem, real emitter PID, chosen level and bounded times for logs. Existing iTerm2 artifacts resolve app-path/developer/ticket inputs. Do not repeat successful battery, metadata, stat/find/sed/du, explicit launchd configuration or app checks. Missing/revoked tickets, offline policy, arbitrary recursive traversal and general wake diagnosis remain outside the certified claims.

Apple's [cycle-count instructions](https://support.apple.com/en-nz/102888) support the report-field interpretation. Apple's [Spotlight troubleshooting guide](https://developer.apple.com/library/archive/documentation/Carbon/Conceptual/MDImporters/Concepts/Troubleshooting.html) supports using mdls to inspect stored metadata; it does not guarantee populated fields for every file. Recipe execution must use the reviewed Apple executables: the catalog still renders tool names resolved through PATH, so index provenance alone does not certify the executable a user's shell selects.

### Prepared check batches (G2 and bounded R1 completed; S3 optional)

The prepared commands are retained for reproducibility. G2 has run successfully; do not repeat it. The tracing-only R1 check is now complete after human authentication; its earlier block is preserved below. Procinfo remains unrun in these follow-ups. S3 remains optional. For any authorized remaining block, record execution status separately from semantic observations, with date/build, privilege and a batch ID. Publish only exit codes, marker presence/counts and scope decisions; retain raw diagnostics locally. Stop on a missing positive control instead of interpreting an empty result as successful filtering. Commands below target the installed Apple tools on the recorded Mac; do not assume `log emit` or its predicate keys exist on older macOS.

#### R1 — tracing and PID/service context

Gap: filesystem-pid, trace-missing and launchd-owner; combines the remaining root checks. Root is used only for fs_usage/procinfo. The existing configuration check is repeated once solely to bind a **current live service PID** to the already reviewed label; no service is loaded, edited or stopped. Start by reading the `pid` in the output, not parsing launchctl's unstable format. If the service has no live PID, record blocked rather than starting it.

```sh
/bin/launchctl print system/com.apple.logd
```

Then run this block, entering that displayed PID. The terminal prompts for sudo authentication before starting the bounded readers; no password is recorded.

```sh
/bin/zsh <<'ZSH'
read 'service_pid?Current PID shown for system/com.apple.logd: ' </dev/tty
[[ "$service_pid" == <-> ]] || exit 1
/usr/bin/sudo -v || exit 1
trace_dir=$(/usr/bin/mktemp -d /tmp/whatisit-R1.XXXXXX) || exit 1
printf 'public selected fixture\n' > "$trace_dir/selected.txt"
printf 'public decoy fixture\n' > "$trace_dir/decoy.txt"
python3 -c 'import pathlib,sys,time; p=pathlib.Path(sys.argv[1]); [(p.read_bytes(),p.write_bytes(b"public selected fixture\n"),time.sleep(.05)) for _ in range(600)]' "$trace_dir/selected.txt" &
trace_pid=$!
python3 -c 'import pathlib,sys,time; p=pathlib.Path(sys.argv[1]); [(p.read_bytes(),time.sleep(.05)) for _ in range(600)]' "$trace_dir/decoy.txt" &
decoy_pid=$!
printf 'R1 selected PID=%s; decoy PID=%s\n' "$trace_pid" "$decoy_pid"
cleanup() {
    # Both owned readers expire after about 30 seconds; reap before removing inputs.
    wait "$trace_pid" "$decoy_pid"
    /bin/rm "$trace_dir/selected.txt" "$trace_dir/decoy.txt"
    /bin/rmdir "$trace_dir"
}
trap cleanup EXIT
/usr/bin/sudo /usr/bin/fs_usage -w -f filesys -t 5 "$trace_pid"
printf 'R1 trace exit=%s\n' "$?"
/usr/bin/sudo /bin/launchctl procinfo "$trace_pid"
printf 'R1 ordinary-child procinfo exit=%s\n' "$?"
/usr/bin/sudo /bin/launchctl procinfo "$service_pid"
printf 'R1 known-service procinfo exit=%s\n' "$?"
ZSH
```

Expected execution: successful bounded trace and both procinfo invocations while PIDs are live. Expected semantics: selected child's read/write filesystem calls/fixture visible, no decoy-reader calls; distinguish PID selection from thread identifiers appended to process names. Record zero visible events as unverified visibility, even with exit 0. The terminal child is not itself a registered launchd service; sharing its parent's bootstrap domain does not assign it a service label. Compare procinfo with the known service PID, but record “ownership not supplied” if it only reports ports/audit context. That is a candidate limitation, not permission to invent PID-to-label mapping. No protected-process or physical-disk-I/O coverage is claimed; cached reads can still produce filesystem calls.

Cleanup: the block waits for its two readers to expire and removes only its two public files and empty directory. If interrupted before completion, let the readers expire, then remove those exact files and empty directory; never signal the system service or use killall. Authentication denial or PID expiration is blocked, not a filter/ownership failure.

#### G2 — five public log events, independent filter controls

Gap: unified-filter and logs-missing. Normal-user event emission/query; if log-store access is denied, record blocked before considering an authorized root read. No log configuration changes, archive collection, compiler or third-party dependency. The installed help documents `processIdentifier`, `logType` and `composedMessage`; use those names instead of assuming legacy manual aliases. A unique subsystem bounds queries to these public fixtures. Verify all five positive-control markers interactively before the filter queries; record each query exit status separately. Events are separated from time-window edges by two seconds; boundary inclusivity is not tested.

```sh
/bin/zsh <<'ZSH'
run="com.example.whatisit.$(/usr/bin/uuidgen)"
base="subsystem BEGINSWITH \"$run.\""
all_start=$(/bin/date '+%Y-%m-%d %H:%M:%S%z')
/usr/bin/log emit --public --type error --subsystem "$run.main" BEFORE || exit 1
/bin/sleep 2
window_start=$(/bin/date '+%Y-%m-%d %H:%M:%S%z')
/bin/sleep 2
/usr/bin/log emit --public --type error --subsystem "$run.main" TARGET &
target_pid=$!
wait "$target_pid" || exit 1
/usr/bin/log emit --public --type default --subsystem "$run.main" LEVEL || exit 1
/usr/bin/log emit --public --type error --subsystem "$run.other" SUBSYSTEM || exit 1
/bin/sleep 2
window_end=$(/bin/date '+%Y-%m-%d %H:%M:%S%z')
/bin/sleep 2
/usr/bin/log emit --public --type error --subsystem "$run.main" AFTER || exit 1
/bin/sleep 2
all_end=$(/bin/date '+%Y-%m-%d %H:%M:%S%z')
# Positive control first; do not run filter queries without all five markers.
/usr/bin/log show --style compact --start "$all_start" --end "$all_end" --predicate "$base"
printf 'G2 baseline exit=%s\n' "$?"
read 'control_ok?Are all five fixture markers present (yes/no)? ' </dev/tty
[[ "$control_ok" == yes ]] || exit 1
/usr/bin/log show --style compact --start "$all_start" --end "$all_end" --predicate "$base AND subsystem == \"$run.main\""
printf 'G2 subsystem exit=%s\n' "$?"
/usr/bin/log show --style compact --start "$all_start" --end "$all_end" --predicate "$base AND logType == \"error\""
printf 'G2 level exit=%s\n' "$?"
/usr/bin/log show --style compact --start "$all_start" --end "$all_end" --predicate "$base AND processIdentifier == $target_pid"
printf 'G2 PID exit=%s\n' "$?"
/usr/bin/log show --style compact --start "$window_start" --end "$window_end" --predicate "$base"
printf 'G2 time exit=%s\n' "$?"
/usr/bin/log show --style compact --start "$window_start" --end "$window_end" --predicate "$base AND subsystem == \"$run.main\" AND logType == \"error\" AND processIdentifier == $target_pid"
printf 'G2 combined exit=%s\n' "$?"
ZSH
```

Expected marker sets, ignoring headers/status lines and unrelated internal diagnostics:

| Query in block order | Required fixture markers |
| --- | --- |
| Broad positive control | BEFORE, TARGET, LEVEL, SUBSYSTEM, AFTER |
| Main subsystem only | BEFORE, TARGET, LEVEL, AFTER |
| Error level only | BEFORE, TARGET, SUBSYSTEM, AFTER |
| Actual TARGET emitter PID only | TARGET; other emitter PIDs excluded |
| Middle time window only | TARGET, LEVEL, SUBSYSTEM |
| Combined subsystem/level/PID/time | TARGET |

Read the broad control's actual process/PID and event types before judging filters. Any unexpected PID attribution, emission error, missing control or unavailable persistence leaves that dimension unverified; a query exiting 0 is insufficient. If the bounded baseline lacks events, a later bounded read of the same interval may address a flush delay; do not re-emit completed controls or change global retention settings. This tests error-versus-default selection and bounded historical reads, not info/debug persistence, arbitrary process-name matching or retention across reboot.

Cleanup: no child process remains after wait and no files are created. The five public synthetic events remain subject to normal system retention; there is no selective safe cleanup command proposed. Do not run `log erase`, which would delete unrelated logs. No private message content is emitted.

#### S3 — optional assertion creation/release control

Only needed to certify the sleep-live **candidate**, not to validate the catalog's supported snapshot or its live/history abstentions. Normal user; temporarily prevents idle sleep for five seconds, with no persistent power setting change. Installed caffeinate(8) documents `-i -t`; pmset(1) documents creation/release logging. This specific missing-event gap justifies repeating monitoring, not the completed snapshot check.

Terminal A:

```sh
/usr/bin/pmset -g assertionslog
```

After A is visibly listening, terminal B:

```sh
/usr/bin/caffeinate -i -t 5 &
assertion_pid=$!
printf 'S3 owned assertion PID=%s\n' "$assertion_pid"
wait "$assertion_pid"
printf 'S3 emitter exit=%s\n' "$?"
```

Expected execution: caffeinate exits 0 after its timeout, while A receives events. Expected semantics: creation and release of the same assertion attributed to this PID, with idle-system-sleep prevention type; ambient assertions are not the control. Record both event markers, their correlation and elapsed time without owner details. Missing markers leave event visibility unverified, not proof of no assertion. No claim of exhaustive wake diagnosis, retroactive history or absence of dropped events.

Cleanup: B naturally releases its assertion after five seconds. Stop A with Ctrl-C; if B is interrupted, allow the five-second timeout to expire. Do not stop unrelated caffeinate processes or change pmset settings. Raw A output stays local.

### G2 observed results — 2026-10-09

User authorized the prepared batch after review at `c30718d`. Run began **2026-10-08 22:36 UTC / 2026-10-09 01:36 Helsinki** on macOS 27.0.1 (26A434), arm64. Used the same fixed `/usr/bin/log emit/show` arguments, public markers, unique subsystem, two-second boundary spacing, observed emitter PID and six predicates as the prepared commands. A Python wrapper captured output only in memory, reaped each emitter and verified the broad control before running filters instead of answering the terminal prompt. No evaluator or generated suggestion was executed. Unique subsystem, actual PIDs, temporary command state and raw log output are omitted.

**Environment/privileges:** macOS `log` cannot run in the Codex sandbox, as previously observed and documented. This authorized batch ran outside that restriction as the normal user, with no sudo/root authentication, log configuration changes or store-access denial. No failed sandbox retry was made. All five emissions and all six queries exited **0**, with no stderr. The baseline contained each public marker once, identified the actual emitter PID for all five, and showed four error events and one default event. Thus there was a positive control before interpreting exclusions.

| Query | Expected markers | Observed markers | Execution | Semantic comparison |
| --- | --- | --- | --- | --- |
| Broad control | BEFORE, TARGET, LEVEL, SUBSYSTEM, AFTER | BEFORE, TARGET, LEVEL, SUBSYSTEM, AFTER | passed; exit 0 | passed; each exactly once, correct emitter PIDs/levels |
| Main subsystem | BEFORE, TARGET, LEVEL, AFTER | BEFORE, TARGET, LEVEL, AFTER | passed; exit 0 | passed; other subsystem excluded |
| Error level | BEFORE, TARGET, SUBSYSTEM, AFTER | BEFORE, TARGET, SUBSYSTEM, AFTER | passed; exit 0 | passed; default-level control excluded |
| TARGET emitter PID | TARGET | TARGET | passed; exit 0 | passed; other actual emitter PIDs excluded |
| Middle time window | TARGET, LEVEL, SUBSYSTEM | TARGET, LEVEL, SUBSYSTEM | passed; exit 0 | passed; before/after controls excluded |
| Combined subsystem/level/PID/time | TARGET | TARGET | passed; exit 0 | passed; conjunction matches the intended event only |

**Routing:** unchanged, not rerun. unified-filter and logs-missing remain catalog `unsupported` and retain their recorded fixture matches; overall historical routing stays 39/40. G2 validates a manually supplied candidate, not a new recipe or an answer to missing filter inputs.

**Execution:** five public emissions plus six bounded reads succeeded. **Semantics:** expected positive/negative marker sets and multiplicities matched in all six comparisons. This fills the specific G1 zero-event gap for subsystem, error-versus-default, real PID and nonboundary time filtering on this Mac. It does not establish process-name selection across different executables, info/debug retention, arbitrary log completeness, redaction behavior, endpoint inclusivity or persistence across reboot. Full answer accuracy remains unmeasured.

**Cleanup completed:** every emitter exited and was reaped before the wrapper finished; no fixture files, monitoring processes or configuration changes were created. The five public synthetic events remain in the system store under normal retention. No `log erase`, archive capture or unrelated-log deletion was performed. No repeat emission/read or completed device check was needed.

### R1 reassessment before privileges

This reassessment preceded the tracing-only R1 attempt below. It did not authorize procinfo or expand privileges; the later user instruction authorized only a bounded trace and preservation of system protections.

| Possible R1 observation | What it would resolve | What it would not resolve / decision |
| --- | --- | --- |
| Five-second fs_usage capture of a fresh owned read/write child, with a concurrent decoy | Root tool access, visibility of known public file operations, and inclusion/exclusion for explicit PID on this target Mac | Not protected-process visibility, exhaustive tracing, physical disk I/O or arbitrary PID safety. This is the smallest potentially useful privileged check if certifying the tracing candidate for #2 or a future comparison. |
| procinfo of that child and a known service PID | Whether diagnostic port/audit context can be read for those two live PIDs | Installed launchctl(1) does not promise a PID-to-service ownership lookup. Successful output alone cannot answer launchd-owner. Do not run both root queries merely to replace a blocked label with an exit-0 result. |
| Repeat print of system/com.apple.logd to get its current PID | A current known-label-to-PID association, if a new ownership comparison actually requires it | Explicit domain/label configuration inspection already passed. No rerun is needed without that specific comparison; it cannot discover an unknown owner from arbitrary PID. |

The full prepared R1 block is therefore **not the default next action**. First decide whether bounded filesystem tracing evidence is required for the closure claim; if so, use only its owned fixtures and fs_usage portion, with the same bounded cleanup. Defer procinfo unless there is a concrete hypothesis about information it supplies beyond the already reviewed manual. If the goal is general PID-to-service discovery, establish and review a candidate mapping method and its ground truth before any privileged experiment; do not infer an owner from inherited bootstrap context. No service loading, configuration mutation or system-service signaling is needed.

S3 remains optional: existing assertion snapshot requests and live/history abstentions are semantically supported. No assertion-event behavior is needed to validate those responses. Run S3 only if explicitly certifying the live-monitoring candidate or defining a comparison task that needs creation/release evidence.

### Bounded R1 observed results — 2026-10-09

The user authorized only the bounded trace at reviewed head `75916e3`. Attempt ran **2026-10-08 22:42:00–22:42:32 UTC / 2026-10-09 01:42 Helsinki**, macOS 27.0.1 (26A434), arm64. Used a fresh private temporary directory containing only public selected/decoy fixtures, an owned selected child repeatedly reading/writing its fixture, and a concurrent owned decoy reading its separate fixture. Both were confirmed live immediately before and after the attempted trace. Raw diagnostics, actual PIDs and local temporary paths are omitted.

Command shape, using the prepared five-second/PID filter and noninteractive authentication:

```sh
/usr/bin/sudo -n /usr/bin/fs_usage -w -f filesys -t 5 <fresh-owned-selected-pid>
```

The Python wrapper invokes fixed argv, captures output in memory, and waits for/reaps both approximately 30-second children before removing only its new fixture directory. `sudo -n` replaces the prepared interactive authentication step: no password is requested, collected or supplied. Execution was outside the Codex sandbox to avoid conflating sandbox denial with root access. No procinfo, service query, repeated G2/core check or S3 monitor was run.

| Check | Expected observation | Observed result / exact status | Interpretation |
| --- | --- | --- | --- |
| Selected/decoy inputs | Both owned processes live with distinct public fixtures | Both live before and after attempt | Correct inputs; no placeholder or expired PID used |
| Root trace invocation | Exit 0; fs_usage runs for up to five seconds | **sudo exit 1**, stderr `sudo: a password is required`; returned after 0.089 seconds | **Blocked on root authentication**; fs_usage never started and has no observed exit code |
| Selected read/write events | At least one read, write and selected-fixture event | 0 events; 0 reads, 0 writes, 0 selected-fixture lines | Unverified due to blocked execution, not a tracing-semantic failure |
| Decoy exclusion | No decoy calls with a positive selected-process control | 0 decoy-fixture lines, but no positive control | Exclusion **unverified**, not passed merely because output is empty |
| Selected child completion | Exit 0; no stderr; reaped | Exit **0**, no stderr; reaped | Public read/write fixture workload completed |
| Decoy child completion | Exit 0; no stderr; reaped | Exit **0**, no stderr; reaped | Public decoy workload completed |
| Cleanup | Both children finished; fixtures and temporary directory absent | Both reaped; temporary directory verified absent | Completed; no retained process, trace file or public fixture |

**Routing:** not rerun; filesystem-pid and trace-missing retain recorded `unsupported` matches. Historical overall result remains 39/40. **Execution:** blocked at sudo, not a measured fs_usage failure. **Semantics:** read/write visibility, PID filtering and decoy exclusion remain unverified. SIP/tracing restrictions were not reached or diagnosed; SIP state was not queried and no system protections, sudo policy or permissions were changed. No service ownership inference is made.

### Historical #2 reconciliation after blocked R1

All 40 rows still have separate routing, execution and semantic dispositions with evidence references. Counts remain **20 bounded device passes, 3 blocked, 17 untested**; the two tracing rows share E8 and remain blocked, and launchd-owner retains its earlier procinfo block/general mapping limitation. Passing candidate checks do not increase the eight catalog suggestions or establish answer accuracy.

| Issue #2 requirement | Current evidence / remaining condition |
| --- | --- |
| Review all 40 expectations and final semantics | Completed scoped agent review; sleep-paraphrase fixture dispute remains explicit, not rescored |
| Validate supported commands with appropriate inputs | Three recipe shapes have successful device checks under the declared public-input protocol; no exact PDF-importer or scalar/JSON claim |
| Validate input/ambiguity/unsupported behavior | Reviewed; no fabricated path/PID/domain/filter values or Linux/mutation command required |
| Record environment/provenance/privileges/results/limits | Complete ledger and E1–E8, including new exact sudo/child statuses and completed cleanup |
| Prioritize tracing, launchd, logs and signing/policy/tickets | G2 and public app checks complete; tracing attempted but root-blocked; explicit launchd configuration checked, general PID-to-service ownership unsupported and unverified |
| Make warranted fixes with regressions | Existing evidence-backed fixes retained; this attempt warrants no recipe/expectation change |
| Report distinct coverage/accuracy/abstention/platform measures | Routing 39/40 and retrieval 34/35 remain separate; abstention/unresolved 32/40 (80%), static wrong-platform suggestions 0/40. Full useful correct coverage and answer accuracy remain unmeasured under an accepted final assessment protocol |

**#2 remains open**: root-blocked tracing is honestly recorded; claiming a tracing success would require a later human-authenticated run, or an explicit limited-scope closure decision accepting the unresolved case. Privileged procinfo is not a substitute for a reviewed PID-to-service mapping method. Complete the final coverage/accuracy assessment with declared inputs, denominators and accepted limitations before closing. No issue checkbox or state was changed by this documentation update.

**S3 stays optional** because assertion-event behavior is not required for the existing snapshot requests or live/history abstentions. **#4 stays deferred** until validation and the final semantic/coverage assessment are sufficient for a meaningful comparison. No model work, completed-check rerun or protection workaround was performed.

### Human-authenticated R1 results — 2026-10-09

The user ran the prepared runner directly in Terminal after the launcher handoff produced no sudo prompt or result. Saved sanitized summary was independently read from the local result file and matches the user's pasted output. The earlier E8 authentication failure remains unchanged; this is a separate attempt with **new** disposable fixtures/processes. Run: **2026-10-08 22:52:12–22:52:46 UTC / 2026-10-09 01:52 Helsinki**, macOS 27.0.1 (26A434), arm64, reviewed implementation `8fcf7c4`.

Human authentication used `/usr/bin/sudo -v` in Terminal and exited **0**. Only after that success did the runner create/start its public selected read/write and decoy read workloads, confirm both children live, and invoke the prepared trace argv:

```sh
/usr/bin/sudo -n /usr/bin/fs_usage -w -f filesys -t 5 <fresh-owned-selected-pid>
```

Authentication remained local; no password was read or stored by Codex. The trace wrapper exited **0**, with no stderr. The five-second bound is the command's `-t 5` parameter; the saved summary does not separately measure trace elapsed time. The roughly 35-second overall duration includes fixture workload completion and cleanup. Both owned workloads complete approximately 30 seconds of repeated file operations, then the runner reaps them and removes its fixture directory. No procinfo, service query or S3 invocation was made.

| Check | Expected | Observed | Result / limit |
| --- | --- | --- | --- |
| Input liveness | Fresh selected/decoy children alive before trace | Both live | passed; no old or placeholder PID |
| Authentication / trace execution | Successful auth; bounded trace exit 0 | sudo -v **0**; sudo/fs_usage invocation **0**; no stderr | passed; root authorized locally |
| Selected reads | At least one | **192** read events | passed; filesystem-call observations, not guaranteed physical disk reads |
| Selected writes | At least one | **192** write events | passed; public selected fixture workload |
| Selected fixture visibility | At least one pathname-bearing event | **288** selected-fixture lines; **1,056** total parsed events | passed; not every event carries a pathname |
| Decoy control | Concurrent separate fixture; no decoy-fixture lines | **0** decoy-fixture lines; decoy workload exited 0 | passed within this public-fixture control, not proof of exhaustive attribution for every pathless event |
| Child completion | Both exit 0, no stderr, reaped | Selected **0**, decoy **0**; no stderr; both reaped | passed |
| Fixture cleanup | New public files/directory absent | Fixture directory verified absent | completed; no child or fixture retained |

**Routing:** unchanged and not rerun; filesystem-pid and trace-missing still abstain in the current catalog, with historical fixture matches. Overall 39/40 stays fixture-specific. **Execution:** successful root-authorized bounded candidate trace, separately from E8's failed sudo prerequisite. **Semantics:** positive read/write/path observations and the separate decoy fixture support the tested PID selection/visibility scope. Counts are events, not distinct bytes/files/processes; process-name suffixes are thread identifiers, not an independently verified PID-to-service mapping. No protected-process, exhaustive tracing, physical-disk-I/O or service-ownership claim is made.

**Protections/environment:** no root, tracing or permission blocker was reported in this successful run. SIP was neither queried nor changed; successful capture does not establish visibility of SIP-protected targets. The launcher handoff issue was bypassed by direct Terminal invocation, without changing Terminal configuration or system protections. No raw trace or credential was saved; only the sanitized summary was retained for this documentation update.

After verifying and recording that summary, Codex removed its disposable launcher, helper, local result file and empty coordinator directory. The runner's fixture cleanup and both child exit statuses remain recorded above; no test process or temporary helper needs further cleanup.

### Current #2 reconciliation after R1 completion

All 40 rows retain separate routing, execution and semantic results. Current device counts: **22 bounded passes, 1 historically blocked procinfo case, 17 untested**. R1 and G2 each back two task rows with shared candidate evidence; those counts are not full answer accuracy or independent executions for each request. The original frozen fixture, 39/40 routing result, 34/35 retrieval result, eight suggestions and 32 unresolved/abstained responses remain unchanged.

The scoped semantic review, explicit input protocol, all three supported recipe shapes, public app checks, controlled log filters, bounded filesystem trace and known-domain/label launchd configuration now have recorded evidence. No further R1/G2, core recipe, app or explicit configuration rerun is required. General PID-to-service ownership remains unsupported/unverified; the old blocked procinfo observation is historical and does not establish that root authentication remains unavailable. A procinfo success would still not certify an ownership method.

**#2 stays open for the final acceptance/coverage assessment:** report useful correct coverage and answer accuracy under explicit reviewed inputs/denominators and retain unsupported/unverified cases as limits; candidate successes cannot be counted as catalog answers. Review whether the stated limitations satisfy the issue's scope before changing its checkbox/state. There is no longer a root-authentication blocker for the completed bounded trace. No issue state is changed automatically.

**S3 remains optional** for a future live-assertion candidate; it is unnecessary for the existing assertion snapshot or live/history abstentions. **#4 remains deferred** until the final validation/semantic assessment supports a meaningful comparison and a fresh uninspected comparison set exists. No model integration or completed-check rerun was performed.

### Remaining closure decision

The evidence review now supports all 40 final dispositions within documented prototype scope; routing remains 39/40, execution is now 22 bounded passes / 1 historically blocked / 17 untested after G2 and human-authenticated R1 (candidate evidence is shared across task rows). There are eight semantically suitable report suggestions, four input responses, one ambiguity and 27 appropriate catalog abstentions. These are review classifications, not measured 100% accuracy or successful answers for unsupported tasks.

G2 and bounded R1 are complete and must not be rerun. Privileged procinfo is not a demonstrated ownership solution and was not run in the follow-up. S3 is conditional on certifying live monitoring. No PDF, battery JSON, signing/ticket or exact APFS rerun is required for current claims. Keep full useful-coverage/answer-accuracy figures unmeasured until the representative-input protocol and answer-completeness assessment are accepted; any eventual score must exclude candidate-only successes from answered tasks and expose blocked/untested scope. E8 records the earlier root-authentication block; E9 resolves that gap with human-authenticated bounded tracing. No further privileged trace is required for the tested public-fixture scope. General launchd ownership remains unsupported; diagnostic success must not be substituted for a validated mapping method. No issue is closed by this review.

**#2 stays open; #4 stays deferred until the remaining validation and semantic assessment support a meaningful comparison.** This agent review does not restore the inspected held-out set's independence; #4 still needs a fresh uninspected comparison set.

Preparation checks: all 40 unique IDs, ledger counts and local evidence anchors verified; all five proposed shell blocks pass syntax checking and their embedded Python parses. These checks did not execute the proposed commands. Source tests, wheel builds, completed device checks and performance measurements were not rerun for this documentation-only review.

G2 update validation: ledger IDs/counts and evidence links checked; source, routing, retrieval, startup, packaging and performance are unchanged. No product tests, wheel build or resource measurement was rerun.

R1 update validation: the 40 IDs, separate status counts, expected/observed tables and evidence anchors were checked. Source, fixtures, routing, retrieval, startup and packaging are unchanged; no product tests, wheel builds or performance measurements were rerun.


### Issue #2 acceptance audit — 2026-10-09

Compared the live [issue #2 body](https://github.com/imaddde867/whatisit-macos/issues/2) and its empty comment thread against the final ledger at `30ed3a2`. No additional issue-level acceptance requirements were found. This review does not execute commands, change issue state, expand catalog coverage or silently replace the 40-task scope with only three recipes.

#### Required work items

| Issue work item | Assessment | Evidence / qualification |
| --- | --- | --- |
| Review all 40 tasks and expectations against installed manuals/relevant official docs | met | E1 and the all-40 semantic review; E3–E9 supplement observations. sleep-paraphrase remains an explicitly adjudicated expectation dispute with frozen routing failure. |
| Manually validate answerable commands/flags with appropriate inputs; human-controlled execution | met for existing suggestions | E3 validates the three recipe shapes backing eight suggestions, using the explicitly declared public-input protocol. E7/E9 validate selected candidates separately. The evaluator never executes generated commands. Exact placeholder inputs and PDF-importer behavior are not certified. |
| Validate clarification/abstention for missing, ambiguous and unsupported tasks | met within recorded scope | All 32 unresolved/non-command responses reviewed. Unsupported requests are not credited as useful answers. No forced mutation/Linux command or invented argument. |
| Record task/environment/provenance/privileges/behavior/completeness/limits/date; blocked/untested honestly | met | Forty linked rows, E1–E9 and separate routing/execution/semantic columns. Procinfo's old authentication block is historical; ownership remains unverified despite later root authentication for tracing. |
| Separate retrieval candidates from suggestions; prioritize tracing, launchd ownership/configuration, logs and app checks | addressed with explicit ownership deferral | R1, G2 and app checks pass their bounded scopes; known launchd configuration inspection passes. Ownership was specifically reviewed and remains unsupported/unverified because no PID-to-service mapping method is certified. Do not report the whole ownership/configuration family as empirically validated. |
| Make warranted recipe/expectation corrections and substantive regressions | met | E1/E2 document seven routing fixes and provenance regression; frozen disputed expectation remains unchanged. Further unsupported capabilities are not required implementations under this validation issue. |

#### Explicit acceptance criteria

| Acceptance requirement | Assessment | Evidence / remaining action |
| --- | --- | --- |
| Every task has validated / needs-input / unsupported / unverified-with-reason disposition | met | All 40 unique IDs have catalog disposition, evidence, execution scope and unverified reasons. The issue explicitly permits unsupported and unverified outcomes. |
| Report useful correct coverage separately | **unmet** | Ledger gives suggestion rate 8/40 but leaves useful correct coverage unmeasured. Finalize fully correct/sufficiently complete suggestion scores under the declared input protocol; report correct suggestions / all 40 tasks. Candidate successes and safe abstentions must not enter the numerator. |
| Report answer accuracy separately | **unmet** | Finalize the same per-suggestion correctness scores and report correct suggestions / eight returned suggestions. Disclose representative inputs, shared recipe evidence, scoring limits and any unverified suggested answers. Do not equate report availability, 39 routing matches or 22 bounded device passes with correctness. |
| Report abstention rate separately | met | 32/40 (80%) unresolved/abstained: 27 unsupported + four input responses + one ambiguity. Strict unsupported fraction is separately derivable as 27/40 (67.5%); do not hide those categories. |
| Report wrong-platform suggestions separately | met with stated review limit | 0/40 in static review of the eight suggested templates, on the declared Apple-tool protocol. This is a template/platform assessment, not general PATH compatibility or future-host assurance. |
| Passing tests or tool retrieval must not count as manual correctness | met | E2 and ledger distinguish 39/40 routing, 34/35 retrieval, execution outcomes and semantic review. No candidate-only result becomes a catalog answer. |
| No private logs/personal file contents committed | met for reviewed evidence updates | Published summaries contain controlled public markers/counts/statuses and tool/version provenance; raw trace/log/owner details, credentials, actual PIDs and local temporary paths are omitted. No new secret/privacy scan is claimed. |

#### Ownership, protected targets and optional S3

**Service ownership is required to consider, but a successful ownership lookup is not mandated by the acceptance text.** The work item explicitly names ownership/configuration, so the known-label configuration check alone cannot stand in for ownership validation. The all-40 ledger includes launchd-owner as unsupported, with general PID-to-service ownership unverified and a reason; installed launchctl(1) only promises diagnostic procinfo context, not a mapping oracle. Explicitly defer empirical ownership validation as an unresolved capability in any closure assessment. If a validated owner lookup is later claimed, it needs a reviewed candidate method and known service/non-service ground truth. Successful procinfo output would not satisfy that claim by itself. This deferral is permitted by the issue's unsupported/unverified acceptance outcomes, rather than by narrowing the task list.

**Visibility limitations are required to record; universal protected-process visibility is not an acceptance requirement.** E9 covers only fresh owned public-fixture workloads. Protected targets were not tested, SIP state was not queried, and no SIP restriction was observed. Explicitly retain protected-process visibility as unverified: neither root authentication nor absence of decoy-fixture lines establishes protected-target coverage. It can be deferred under the same unverified-with-reason allowance without changing system protections. An empirical protected-target test becomes necessary only for a future answer/comparison that actually claims such visibility, or an explicitly strengthened issue requirement.

**S3 is optional and separate:** current sleep-live/history requests abstain, while the snapshot is already validated. Assertion-event creation/release evidence is needed only to certify a live-monitoring candidate; it is not a required rerun or a substitute for the missing metrics.

#### Closure recommendation and exact blockers

**Keep #2 open for now.** The remaining mandatory artifact is the final correctness scoring/report: identify the eight suggested case IDs, decide which are fully correct and sufficiently complete under the already declared representative-input protocol, record uncertainty honestly, and publish useful correct coverage and answer accuracy with their separate denominators. Existing evidence can support this assessment; no completed check needs rerunning merely to produce the report. If scoring exposes a specific missing observation, name that observation before proposing a new check.

Carry service ownership and protected-process visibility explicitly as unresolved/deferred cases in the closure assessment. They are not hidden successes and are not additional mandatory device experiments under the current acceptance language. Likewise retain the frozen sleep-paraphrase dispute and other already stated untested limits. A decision to demand empirical ownership/protected-target coverage would expand the completion requirement and must be stated explicitly, not inferred from a bounded trace.

After the two missing metrics and the explicit retained-deferral assessment are published, closure can be recommended against the current acceptance criteria; it would mean the 40-task validation assessment is recorded, not that all 40 tasks are answered or every candidate is validated. Do not close the issue in this review. #4 remains deferred pending sufficient validation/semantic evidence and an independent comparison set; #2 closure alone would not automatically authorize a model comparison.

Audit validation: no task, test, wheel, benchmark or optional S3 was rerun. The 40-task IDs, existing result counts and evidence references were checked; only this documentation assessment and stale textual references were updated.
