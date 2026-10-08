# Design

## Implemented baseline

The CLI passes the request, `platform.system()`, a tool-availability lookup, and an optional explicit file path to `engine.suggest`. The engine selects one fixed recipe from package data, checks macOS and the required binary, requests missing inputs, and builds quoted output. Suggestions include sources and limitations.

`recipes.json` contains identifiers, keyword groups, argument templates, required parameters, references, and notes. Only inspection templates are included. The engine never runs the command, reads shell history, enumerates directories, sends a request, or starts a model server.

The keyword exclusion for obvious mutation verbs is a routing convenience, not a safety classifier. The actual execution boundary is that this project has no execution path. Tool presence proves neither semantic correctness nor that a tool on PATH is trustworthy.

## Local evidence retrieval — implemented

An explicit `tools/build_docs.py` capture reads system manuals from `/usr/share/man` using fixed tool names and sections, and adds the three authored recipe descriptions. It records tool/source paths, macOS version, UTC capture time and a SHA-256 of rendered document text. Executable provenance is resolved only in Apple system directories, ignoring PATH shadows; unavailable system tools are excluded even if a third-party replacement is on PATH. No documented executable is invoked. Missing manuals/tools are recorded as unavailable; failed rendering aborts the capture. Existing indexes are refused and incomplete new indexes are removed on build failure.

The index uses standard-library SQLite FTS5, with overlapping 35-line windows at 30-line intervals. `--docs-index` opens an existing index read-only, tokenizes the request into literal search terms, removes common filler words, and returns up to three BM25-ranked chunks. It never interpolates SQL or passes user input to a shell. The text windows can split sections, share repeated evidence and match irrelevant text; no paraphrase expansion or semantic ranking is claimed.

Evidence is appended separately to the existing answer, including for unsupported requests. A retrieval failure is visible in `documentation_error`; it does not discard a catalog command or change the CLI exit status. The version and capture date are displayed for human review, with no automatic version-certification claim. Source identity distinguishes local manual paths from `catalog:RECIPE_ID` entries. Indexes are local ignored artifacts, not package data.

## Proposed next flow

1. Retrieve a few likely macOS recipes from a local index.
2. Ground candidates in version-appropriate local manual/help sections, with provenance.
3. If useful, ask a small local model to select a recipe and identify missing typed parameters. Keep command rendering outside the model for catalog-backed tasks.
4. Reject unsupported flags, unknown recipe IDs, missing parameters, and Linux-only substitutions; ask a clarifying question or abstain.
5. Render the command, what it does, required privileges, and the evidence used.

No model-provider abstraction is implemented yet. Add the first adapter only after a measured candidate earns its place. Free-form commands, model-managed execution, and a complex agent framework are outside the starter scope.

## Resource plan

The baseline uses Python's standard library and a tiny catalog; no resident inference memory is needed. Python startup is still a cost. Target Apple Silicon measurements are recorded in [MEASUREMENTS.md](MEASUREMENTS.md). No numerical release budget has been set.

If a local model materially improves coverage, compare cold and warm latency, peak/resident memory, and quality under identical queries. Keep model loading optional, use an explicit idle-unload policy if a server is introduced, and leave the deterministic catalog usable without it. No speed or memory target is currently claimed as achieved.
