# Roadmap

## Active direction

Keep the documented recipe catalog as the fast path. For unsupported or ambiguous requests, offer an optional local general-command fallback through the pinned upstream `whatisit` package; `--catalog-only` keeps a catalog-only invocation. The historical `--model` MLX selector remains available for catalog selection. The fallback uses upstream's shared server lifecycle with a 60-second idle timeout and adds no automatic download or execution path.

The next work is to measure useful correct coverage, abstentions and errors, latency, peak memory and idle unload behavior on a fresh comparison set. Keep generated commands reviewable, local by default, and explicitly uncertain about semantic correctness. Do not treat adding recipes as the sole path to useful coverage.

Issue #2 remains open only for final scoring/protocol acceptance and explicitly retained limitations. It does not block starting #4/#7. Earlier deferral statements in the chronological validation ledger describe the previous plan. Finish the baseline report with existing evidence; no further general validation audit is required.

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

## 3. Historical local MLX experiment — first slice implemented

- [x] Inspect original source/configuration and locally available models/runtimes; record hashes and reuse opportunities in [EXPERIMENT.md](EXPERIMENT.md). Original installed version/debug output remains uncaptured.
- [x] Implement one optional MLX selector, shared validated rendering and on-demand lifecycle, following #4.
- [x] Add separate signature, local Gatekeeper policy and stapled-ticket operations with explicit app paths, following #7.
- [x] Add an A/B/C measurement harness and record an 11-case development pilot, including retained RSS after unload. Keep the model optional; no added benefit on this slice.
- [x] Add bounded unified-log filtering from the existing G2 evidence; require typed inputs and deterministic rendering. See [LOG_FILTER.md](LOG_FILTER.md).
- [x] Add explicit known-service inspection with launchd domain and label; PID-to-service ownership remains unsupported.
- [ ] Continue #7 with bounded tracing.
- [ ] Measure frozen baseline versus expanded deterministic versus model-assisted variants on the M4.
- [ ] Record load time, fresh/warm median and p95 latency, peak total memory, retained idle memory and observed swap/pressure.
- [x] Freeze and measure a 24-case post-implementation A/B/C comparison; publish semantic judgments and negative model results in [LOG_FILTER.md](LOG_FILTER.md). This implementer-authored set is now development evidence; independent release comparison remains pending.
- [ ] Publish reproducible commands, model/configuration identities, semantic scores and a keep/change/discard decision.

Pilot commands, artifact identities and the provisional keep-deterministic/no-default-model decision are historical results in [EXPERIMENT.md](EXPERIMENT.md). They describe the MLX catalog-selector experiment and do not evaluate the general fallback.

Experiment start is unblocked. Default adoption still requires measured benefit within predeclared resource budgets, no fabricated required inputs or wrong-platform outputs on the comparison set, and separately reported errors/abstentions/coverage. A negative result is a valid outcome. Do not tune against the final comparison set.

## Deferred

Automatic execution, a GUI, cloud fallbacks, model fine-tuning, and Linux/Windows support. Revisit only when the command lookup is useful enough to justify more scope.

Routing and installed-wheel follow-up: [VALIDATION.md](VALIDATION.md). All 40 dispositions and bounded device outcomes are recorded. Final scoring acceptance and independent release evaluation remain pending. Issue #2 stays open for final scoring; #4 is the next implementation experiment and #7 supplies coverage work. Optional assertion-event check S3 is not required for the existing snapshot recipe.
