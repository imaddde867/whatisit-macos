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
- [ ] Expand to 30–50 independently phrased tasks: BSD/GNU differences, missing inputs, multi-step checks, and tasks that should abstain.
- [ ] Inspect current local manuals and manually validate each recipe on the target macOS release.
- [ ] Add filesystem tracing, launchd inspection, unified-log filtering, and separate signing/Gatekeeper/notarization checks only after the required inputs and caveats are documented.
- [ ] Record baseline correctness, useful coverage, cold latency, and peak RSS.

Gate: a recipe needs documented flags, explicit parameters, a successful device check or a recorded limitation, and positive/negative regression cases.

## 2. Improve retrieval before choosing a model

- [ ] Build a small local index from curated recipes and selected manual sections.
- [ ] Improve paraphrase matching; detect requests the catalog only partially answers.
- [ ] Keep source identity, macOS version, and validation date with each entry.

Gate: compare against the keyword baseline on the expanded evaluation, including false matches and abstentions. Keep a held-out set that was not used to tune routing.

## 3. Optional local model experiment

- [ ] Compare the original fine-tune with a few small instruct/coder candidates using the same retrieval context and cases.
- [ ] Start with recipe selection and parameter clarification; do not silently introduce arbitrary command generation.
- [ ] Measure cold/warm wall time, model memory, and useful correct coverage on the actual MacBook.
- [ ] Add one backend only if the improvement justifies the resource cost.

Gate: zero wrong-platform suggestions on the release set, no fabricated required inputs, and separately reported errors/abstentions/coverage. Set numerical latency and memory limits after measuring the target machine; do not invent them now.

## Deferred

Automatic execution, a GUI, cloud fallbacks, model fine-tuning, and Linux/Windows support. Revisit only when the command lookup is useful enough to justify more scope.
