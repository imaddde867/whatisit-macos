# Design

## Implemented baseline

The CLI passes the request, `platform.system()`, a tool-availability lookup, an optional explicit file path, and optional typed `LogFilter` inputs to `engine.suggest`. The engine selects one fixed recipe from package data, checks macOS and the required binary, requests missing inputs, and builds quoted output. Suggestions include sources and limitations.

`recipes.json` contains identifiers, keyword groups, argument templates, required parameters, references, and notes. The app and log-filter operations also record input schemas, output scope and privileges. Only inspection templates are included. The engine never runs the command, reads shell history, enumerates directories, sends a request, or starts a model server.

The optional `--model LOCAL_DIRECTORY --docs-index INDEX` path uses `local_model.suggest_with_model`. It retrieves at most three chunks and clips each to 1,600 characters in the prompt, alongside the same catalog used by keyword routing. A strict one-key JSON response selects a catalog ID or abstains. The shared `engine.render` rejects unknown selections and known unsupported scope, checks tools and required inputs, and builds argv only from supplied path/filter inputs. Model-produced commands and inputs are rejected. This limits command construction; it does not prove the selected operation satisfies an arbitrary natural-language request.

MLX imports and local model loading occur only on first selection. Each query uses greedy sampling, a fresh KV cache, a 4,096-token context budget and at most 64 output tokens. The CLI closes model references, synchronizes MLX, clears its cache and exits. The pilot measures retained process RSS after close separately from process shutdown; unloading weights does not imply the runtime returns all RSS. See [EXPERIMENT.md](EXPERIMENT.md).

The keyword exclusion for obvious mutation verbs is a routing convenience, not a safety classifier. The actual execution boundary is that this project has no execution path. Tool presence proves neither semantic correctness nor that a tool on PATH is trustworthy.

## Local evidence retrieval — implemented

An explicit `tools/build_docs.py` capture reads system manuals from `/usr/share/man` using fixed tool names and sections, and adds the seven authored recipe descriptions. It records tool/source paths, macOS version, UTC capture time and a SHA-256 of rendered document text. Executable provenance is resolved in Apple system directories, or the catalog's explicit Command Line Tools stapler path, ignoring PATH shadows; unavailable tools are excluded even if a third-party replacement is on PATH. No documented executable is invoked. Missing manuals/tools are recorded as unavailable; failed rendering aborts the capture. Existing indexes are refused and incomplete new indexes are removed on build failure.

The index uses standard-library SQLite FTS5, with overlapping 35-line windows at 30-line intervals. `--docs-index` opens an existing index read-only, tokenizes the request into literal search terms, removes common filler words, and returns up to three BM25-ranked chunks. It never interpolates SQL or passes user input to a shell. The text windows can split sections, share repeated evidence and match irrelevant text; no paraphrase expansion or semantic ranking is claimed.

Evidence is appended separately to the existing answer, including for unsupported requests. A retrieval failure is visible in `documentation_error`; it does not discard a catalog command or change the CLI exit status. The version and capture date are displayed for human review, with no automatic version-certification claim. Source identity distinguishes local manual paths from `catalog:RECIPE_ID` entries. Indexes are local ignored artifacts, not package data.

## Remaining semantic comparison

1. Retrieve a few likely macOS recipes from a local index.
2. Ground candidates in version-appropriate local manual/help sections, with provenance.
3. If useful, ask a small local model to select a recipe and identify missing typed parameters. Keep command rendering outside the model for catalog-backed tasks.
4. Reject unsupported flags, unknown recipe IDs, missing parameters, and Linux-only substitutions; ask a clarifying question or abstain.
5. Render the command, what it does, required privileges, and the evidence used.

The first optional adapter implements catalog selection and deterministic missing-input handling. A final fresh-set comparison remains pending. Free-form commands, model-managed execution, and a complex agent framework are outside the starter scope.

## Resource plan

The default uses Python's standard library and a tiny catalog; no resident inference memory is needed. Python startup is still a cost. Historical Apple Silicon measurements are recorded in [MEASUREMENTS.md](MEASUREMENTS.md). Provisional budgets for a future comparison are recorded in [EXPERIMENT.md](EXPERIMENT.md); no model release has passed them.

If a local model materially improves coverage, compare cold and warm latency, peak/resident memory, and quality under identical queries. Keep model loading optional, use an explicit idle-unload policy if a server is introduced, and leave the deterministic catalog usable without it. No speed or memory target is currently claimed as achieved.

The bounded log operation accepts an exact ASCII subsystem, a positive integer PID, error/default severity and ordered offset timestamps. The renderer validates these fields before interpolating the fixed predicate and shell-quoting argv. Required inputs are requested individually, never inferred from text or supplied by the selector. Filter values stay out of the model prompt. Other operations reject unused log flags.
