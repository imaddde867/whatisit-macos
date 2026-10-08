# Why the original answers failed

Initial investigation: 2026-10-08. The observations below come from a short set of macOS questions, not a representative accuracy benchmark. The original installed package version, model checksum, saved configuration, and debug prompts have not been captured, so the exact cause of each output is still unproven.

## Observed failures

| Request | Observed answer | What needs to improve |
| --- | --- | --- |
| Battery cycle count | `ioreg -d2 -l` piped through a text filter | Fragile property spelling, registry depth, and field extraction. Start with the system power report and verify behavior on the target device. |
| Indexed metadata of one file | `mdls` with a placeholder | The tool choice is useful, but the file path is missing. Ask for it explicitly and quote it. |
| Processes/kernel assertions preventing sleep | `pmset -g` | Active settings can include hints, but the dedicated assertion report is `pmset -g assertions`. |
| Real-time filesystem activity for a PID | `strace -e trace=file <process-id>` | Linux-specific tooling and an incomplete attachment form. Investigate macOS `fs_usage`, its PID filtering, privileges, and visibility limits. |
| Owning launchd service and its configuration | `launchctl info` | Does not answer the requested relationship. PID inspection, service domain/label identification, and service configuration are distinct steps; not every process maps to a launchd service. |
| Unified logs with process/subsystem/severity/time filters | Nothing usable | Needs explicit filter values and a valid predicate/time range. Determine whether this was generation, truncation, or extraction failure from debug output. |
| Signing, notarization, and Gatekeeper acceptance | `spctl --assess` with a placeholder | Gatekeeper assessment alone is not a complete signature/notarization audit. Treat these as separate checks and distinguish local assessment from guaranteed behavior on another machine. |

The first version implements only the battery report, metadata lookup, and sleep-assertion snapshot. It deliberately abstains on the other four cases.

## Evidence from upstream

Source inspected at commit [`2e2f12778182813b0d0ac2e92ac70986e6061e38`](https://github.com/ThorOdinson246/whatisit-nl2sh/tree/2e2f12778182813b0d0ac2e92ac70986e6061e38):

- [README](https://github.com/ThorOdinson246/whatisit-nl2sh/blob/2e2f12778182813b0d0ac2e92ac70986e6061e38/README.md): describes a Qwen2.5-Coder-1.5B fine-tune, 64-token outputs, and evaluation on InterCode-ALFA. Its benchmark is not evidence of correctness for these macOS administration questions.
- [Engine](https://github.com/ThorOdinson246/whatisit-nl2sh/blob/2e2f12778182813b0d0ac2e92ac70986e6061e38/whatisit_pkg/whatisit/engine.py): defaults to a short generation budget. In the local path, grammar is gated on install intent and the host package manager. These inspection questions are not grammar-constrained by that path.
- [Host context](https://github.com/ThorOdinson246/whatisit-nl2sh/blob/2e2f12778182813b0d0ac2e92ac70986e6061e38/whatisit_pkg/whatisit/hostctx.py): supplies host facts and package-manager guidance, not retrieved documentation for each task. Its introductory comments and the engine's defaults differ; actual behavior must be checked against the installed version and configuration.

No new model benchmarks were run. We have not established that a particular model size, quantization, or training-data source caused the observed mistakes.

## Working hypotheses

1. **Task knowledge is missing or weak.** Telling a model it is on macOS does not teach the exact administrative subcommands or every BSD/GNU difference.
2. **A short command-only interface hides missing inputs.** PID, path, service label, subsystem, and time range are legitimate questions to ask, not values to invent.
3. **Output constraints do not establish semantics.** A grammar can make a command syntactically well formed while the command still answers a different task. Upstream's install grammar does not address these examples anyway.
4. **Longer tasks may exceed generation/extraction limits.** The unified-log failure needs a captured raw response before blaming the model itself.
5. **Coverage and accuracy need separate measurement.** Abstaining is better than confidently returning a wrong command, but abstaining on everything is not useful.

## Sources for the first recipes

- [Apple: battery cycle count](https://support.apple.com/en-nz/102888) establishes the System Information → Power → Battery Information route. The CLI spelling and behavior still need `man system_profiler` and a device check.
- [Apple: troubleshooting Spotlight importers](https://developer.apple.com/library/archive/documentation/Carbon/Conceptual/MDImporters/Concepts/Troubleshooting.html), together with `man mdls`, is the metadata reference.
- [Apple's PowerManagement source](https://github.com/apple-oss-distributions/PowerManagement), together with `man pmset`, is the sleep-assertion reference.
- [Apple: examining filesystem usage](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/FileSystem/Articles/FileSystemCalls.html) is a starting point for tracing. It is archived guidance; confirm current flags and restrictions locally.

## Next diagnostic capture

Record the original package version, exact model filename/hash, relevant configuration (remove secrets), and `--debug` output for each seed question. Compare one variable at a time: host context, generation budget, model, and grounded retrieval. Do not choose a replacement model from speed claims alone.
