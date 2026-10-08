# Design

## Implemented baseline

The CLI passes the request, `platform.system()`, a tool-availability lookup, and an optional explicit file path to `engine.suggest`. The engine selects one fixed recipe from package data, checks macOS and the required binary, requests missing inputs, and builds quoted output. Suggestions include sources and limitations.

`recipes.json` contains identifiers, keyword groups, argument templates, required parameters, references, and notes. Only inspection templates are included. The engine never runs the command, reads shell history, enumerates directories, sends a request, or starts a model server.

The keyword exclusion for obvious mutation verbs is a routing convenience, not a safety classifier. The actual execution boundary is that this project has no execution path. Tool presence proves neither semantic correctness nor that a tool on PATH is trustworthy.

## Proposed next flow

1. Retrieve a few likely macOS recipes from a local index.
2. Ground candidates in version-appropriate local manual/help sections, with provenance.
3. If useful, ask a small local model to select a recipe and identify missing typed parameters. Keep command rendering outside the model for catalog-backed tasks.
4. Reject unsupported flags, unknown recipe IDs, missing parameters, and Linux-only substitutions; ask a clarifying question or abstain.
5. Render the command, what it does, required privileges, and the evidence used.

No model-provider abstraction is implemented yet. Add the first adapter only after a measured candidate earns its place. Free-form commands, model-managed execution, and a complex agent framework are outside the starter scope.

## Resource plan

The baseline uses Python's standard library and a tiny catalog; no resident inference memory is needed. Python startup is still a cost. Measure total process latency and peak RSS on the target Apple Silicon Mac before setting a performance budget.

If a local model materially improves coverage, compare cold and warm latency, peak/resident memory, and quality under identical queries. Keep model loading optional, use an explicit idle-unload policy if a server is introduced, and leave the deterministic catalog usable without it. No speed or memory target is currently claimed as achieved.
