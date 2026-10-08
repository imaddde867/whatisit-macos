# Roadmap

## 0. Starter baseline — implemented

- [x] Small installable CLI with zero third-party runtime dependencies.
- [x] Three fixed macOS inspection recipes with references and caveats.
- [x] Tool/platform checks, quoted paths, explicit missing-input and unsupported states.
- [x] Regression tests and seed questions from the original failures.
- [x] CI definition for Ubuntu/macOS and installed-wheel catalog smoke testing.

CI passing does not mean the suggestions have been executed on the target MacBook.

## 1. Establish a useful macOS evaluation

- [ ] Capture original model/config/debug evidence without credentials or private history.
- [x] Expand to 40 authored tasks covering BSD/GNU differences, missing inputs, multi-step checks, and abstention; freeze 20 dev and 20 held-out cases. Independent author review remains pending.
- [ ] Inspect current local manuals and manually validate each recipe on the target macOS release.
- [ ] Add filesystem tracing, launchd inspection, unified-log filtering, and separate signing/Gatekeeper/notarization checks only after the required inputs and caveats are documented.
- [x] Record baseline contracts, lexical retrieval results, fresh-process latency and peak RSS on the target Mac.
- [ ] Establish command correctness and useful correct coverage through manual device checks.

Gate: a recipe needs documented flags, explicit parameters, a successful device check or a recorded limitation, and positive/negative regression cases.

## 2. Improve retrieval before choosing a model

- [x] Build an explicit local FTS5 index from curated recipes and selected system manuals, searchable as bounded text chunks.
- [ ] Improve paraphrase matching; detect requests the catalog only partially answers.
- [x] Keep source identity, macOS version, capture date and document hash with each entry. Capture date is not a command validation date.

The first comparison and eight routing mismatches are recorded in [MEASUREMENTS.md](MEASUREMENTS.md). Evidence retrieval leaves keyword routing unchanged.

Gate: compare against the keyword baseline on the expanded evaluation, including false matches and abstentions. Keep a held-out set that was not used to tune routing.

## 3. Optional local model experiment

- [ ] Compare the original fine-tune with a few small instruct/coder candidates using the same retrieval context and cases.
- [ ] Start with recipe selection and parameter clarification; do not silently introduce arbitrary command generation.
- [ ] Measure cold/warm wall time, model memory, and useful correct coverage on the actual MacBook.
- [ ] Add one backend only if the improvement justifies the resource cost.

Gate: zero wrong-platform suggestions on the release set, no fabricated required inputs, and separately reported errors/abstentions/coverage. Set numerical latency and memory limits after measuring the target machine; do not invent them now.

## Deferred

Automatic execution, a GUI, cloud fallbacks, model fine-tuning, and Linux/Windows support. Revisit only when the command lookup is useful enough to justify more scope.
