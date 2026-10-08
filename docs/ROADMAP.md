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
- [x] Expand to 40 authored tasks covering BSD/GNU differences, missing inputs, multi-step checks, and abstention; freeze 20 dev and 20 held-out cases. The inspected held-out split is now development evidence; a fresh uninspected comparison set is required.
- [x] Inspect current local manuals and validate the three supported recipe shapes on the target Mac under the disclosed representative-input protocol.
- [x] Record bounded candidate checks for filesystem tracing, known-service configuration, controlled log filtering, and signing/Gatekeeper/notarization. These remain candidate evidence, not added catalog recipes; general service ownership and protected-process visibility are unverified.
- [x] Record baseline contracts, lexical retrieval results, fresh-process latency and peak RSS on the target Mac.
- [ ] Finalize the eight suggestion judgments and useful correct coverage in [SUGGESTION_REVIEW.md](SUGGESTION_REVIEW.md). Agent-reviewed N=8 is provisional; Imad's protocol acceptance and broad metadata completeness judgment remain pending.

Gate: a recipe needs documented flags, explicit parameters, a successful device check or a recorded limitation, and positive/negative regression cases.

## 2. Improve retrieval before choosing a model

- [x] Build an explicit local FTS5 index from curated recipes and selected system manuals, searchable as bounded text chunks.
- [x] Fix the documented Spotlight paraphrase and reject known partial-answer qualifiers; broader intent matching remains limited.
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

Routing and installed-wheel follow-up: [VALIDATION.md](VALIDATION.md). All 40 dispositions and bounded device outcomes are recorded. Final scoring acceptance and independent release evaluation remain pending. Issue #2 stays open; #4 stays deferred. Optional assertion-event check S3 is not required for the existing snapshot recipe.
