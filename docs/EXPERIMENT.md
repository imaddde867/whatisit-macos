# Local selector and app-check pilot — 2026-10-09

This is the first implementation slice for #4/#7. Six operations now work without a model: the original three plus separate app signature integrity, local Gatekeeper policy and stapled ticket validation. The app argv shapes reuse the public-artifact checks in [VALIDATION.md](VALIDATION.md#public-developer-id-artifact-verification--2026-10-09). No completed device check was repeated. Suggested commands remain manual; lookup does not launch the app or inspect the supplied path.

## Provenance and reuse

[The baseline manifest](../eval/baseline/manifest.json) freezes the source at `049fd60`, the three-recipe catalog, the original 40 development cases, and the retained system-manual index identity. The archived engine is loaded with its archived recipe data, not the expanded package catalog. Historical 57 ms fresh CLI, 28.7 MiB peak RSS and 0.22 ms repeated lookup retain their original scopes. The new worker timings below are separate measurements.

Provisional scoring remains N=7 (7/40 coverage, 7/8 suggestion accuracy) and N=8 (8/40, 8/8), pending broad-metadata adjudication. Partial answers count as incorrect. Apply the same interpretation to every variant; do not silently select N=8. Literal frozen-path execution acceptance is a separate unresolved protocol question described in [SUGGESTION_REVIEW.md](SUGGESTION_REVIEW.md).

Re-inspected upstream [engine](https://github.com/ThorOdinson246/whatisit-nl2sh/blob/2e2f12778182813b0d0ac2e92ac70986e6061e38/whatisit_pkg/whatisit/engine.py) and [configuration](https://github.com/ThorOdinson246/whatisit-nl2sh/blob/2e2f12778182813b0d0ac2e92ac70986e6061e38/whatisit_pkg/whatisit/config.py). Its default prompt generates commands directly; its server remains resident unless an idle timeout is configured. Reuse the lifecycle lessons, not direct command generation or another server framework. No upstream code was imported and no repository restart/fork conversion was needed.

The original `nl2sh-1.5b-Q4_K_M.gguf` is locally available, SHA-256 `6f8a17a11129a31074c944f4c2602453fafd9de43bdaeb1630a8f511ec820f71`. Selected non-secret local settings: 64 output tokens, greedy sampling, automatic threads, 2,048-token context, host context off, idle timeout 180 seconds. Its llama binaries were not on PATH; the original installed package version/debug output was not captured. No claim is made that these settings caused the historical failures.

The first backend reuses cached `mlx-community/Qwen2.5-3B-Instruct-4bit`, snapshot `4f83f8f146fdf28b512a06562b671d7af4fab457`, 4-bit/group-size 64. [models.json](../eval/baseline/models.json) records all local model/tokenizer/config hashes and runtime versions. These are observed artifact identities, not independently authenticated publisher hashes. MLX-LM 0.31.3, MLX 0.32.0 and Transformers 5.5.0 were already installed in a separate local environment; no dependency was added to the default package.

## Run it

The no-model examples need an actual app path when the printed command is run:

```sh
PYTHONPATH=src python3 -m whatisit_macos --path /Applications/Example.app 'verify app signature'
# codesign --verify --deep --strict --verbose=2 /Applications/Example.app
PYTHONPATH=src python3 -m whatisit_macos 'verify app signature'
# needs-input: Supply the path with --path. No path is guessed. (exit 2)
PYTHONPATH=src python3 -m whatisit_macos 'check signing, notarization and Gatekeeper acceptance of an application'
# unsupported: Ask for one supported task at a time. (exit 2)
```

For the optional experiment, use an Apple Silicon Python environment with the recorded runtime versions. If they are not already installed, install them in a separate environment rather than changing the default CLI:

```sh
python3 -m venv .venv-model
.venv-model/bin/python -m pip install . 'mlx-lm==0.31.3' 'mlx==0.32.0' 'transformers==5.5.0'
model_dir="$HOME/.cache/huggingface/hub/models--mlx-community--Qwen2.5-3B-Instruct-4bit/snapshots/4f83f8f146fdf28b512a06562b671d7af4fab457"
PYTHONPATH=src .venv-model/bin/python -m whatisit_macos.build_docs .cache/manuals-app-experiment.sqlite3
PYTHONPATH=src .venv-model/bin/python -m whatisit_macos --model "$model_dir" \
  --docs-index .cache/manuals-app-experiment.sqlite3 --json --path /Applications/Example.app 'verify app signature'
PYTHONPATH=src .venv-model/bin/python -m tools.experiment --model "$model_dir" \
  --docs-index .cache/manuals-app-experiment.sqlite3 --passes 2 --fresh-runs 3 > .cache/app-experiment.json
```

The adapter requires an existing local model directory; it does not download a model. Omit `--model` from the harness to compare A/B without MLX. Choose a new index filename on each capture. The new pilot index contains 12 system manuals and six catalog entries, including the curated ticket operation; it does not contain a newly captured stapler manual. The existing CLT manual/device evidence remains in the validation ledger.

The prompt is in `local_model.SYSTEM_PROMPT`: bounded retrieved context, all six operation scopes, required inputs and caveats. Only a string/null `operation` key is accepted. Unknown operations, generated arguments, command strings and malformed responses abstain visibly. Missing path is derived from the catalog. Supplied paths are never sent to the selector; the renderer handles them literally. Generation is greedy with a fresh KV cache, 4,096-token total context budget and 64-token output cap. A selected template can still misunderstand an unfamiliar request; template validity is not semantic accuracy.

## Pilot results and limits

Target: M4, 16 GiB, macOS 27.0.1, arm64, Python 3.14.8. [The recorded pilot](../eval/pilot/app-checks.json) retains hashes, outputs, timing/resource samples, prompt hashes and retrieved-context identities/chunk hashes. Exact C prompts including clipped retrieved text remain in the local ignored raw report, `.cache/app-check-pilot-final.json`; copied manual passages are not versioned. Eleven authored app tasks are development cases inspected during implementation, not an independent benchmark. The existing 40 cases are also development evidence; their expectations were not rewritten to credit expansion. The harness writes full requests/inputs/prompts locally, so use authored public fixtures when sharing reports.

| Variant | App-case contracts matched | Fresh worker wall | Warm median / p95 | Worker peak RSS | RSS after explicit unload |
| --- | --- | --- | --- | --- | --- |
| A: frozen three recipes | 5/11 (abstentions only) | 51.5 ms | 0.0024 / 0.0051 ms | 26.2 MiB | 26.2 MiB |
| B: expanded deterministic + retrieval | 11/11 | 63.3 ms | 0.316 / 0.465 ms | 30.6 MiB | 30.6 MiB |
| C: same catalog/inputs + model | 11/11 | 5,428.8 ms | 3,273.2 / 4,715.7 ms | 1,926.2 MiB | 1,692.4 MiB |

Final verification uses one fresh worker per variant and 11 requests in one warm worker; the first response is excluded from warm summaries (10 samples). Fresh p95 from a single sample is not a reliable tail estimate. A preceding pilot used two fresh runs and two passes (22 requests): C warm median/p95 3,943.7/4,172.0 ms, fresh median 5,364.0 ms. It used the retained baseline index and an earlier prompt, so it is not pooled with final results.

Final C model load was 1,236.0 ms including runtime import and eager weight/tokenizer loading. Fresh wall includes interpreter, imports, retrieval, loading, response, unload and worker exit. Warm includes retrieval and rendering; filesystem caches were not flushed. These are lookup-worker measurements, not fresh CLI measurements. Index construction and model/provenance hashing occur outside response timing. Suggested commands were never executed.

Process-tree RSS sampling every 50 ms can miss short-lived peaks: A/B sampled only early startup, so their sampled tree values are unusable as peak estimates. The table uses the separate self `ru_maxrss` high-water. The adapter is in-process and starts no backend server or child; sampled process-tree peaks and MLX allocation peaks are retained separately, without adding overlapping unified memory. Retained RSS is sampled immediately after close, not after a long idle period. After C close, MLX reported 8 active bytes and zero cached bytes, but runtime/driver mappings still retained 1,692.4 MiB RSS. Worker exit ends that process; there is no resident server. Do not promise that weight unloading alone returns all process RSS.

Swap used remained 167.31 MiB before/after. System-wide pressure snapshots before the final pilot and after worker exit both reported raw kernel level 2 and 51% free memory. Pressure was not sampled during inference, and neither those snapshots nor unchanged swap establish absence of transient pressure or causality.

The final unsupported launchd case produced an unknown model operation; validation rejected it and returned `unsupported` with `model_error`. It counts as the expected external abstention contract, not a valid model decision. Three suggestions, three necessary path clarifications and five abstentions were returned by B/C. No fabricated input, runnable wrong-platform command or partial combined app check was emitted on these 11 cases. Contract matches are not reviewed useful coverage/accuracy; necessary versus unnecessary clarification and all semantic error categories need the fresh comparison rubrics.

**Decision for this slice:** keep the deterministic catalog expansion and the adapter as an optional measurement experiment. Do not adopt the model by default: it added no app-case benefit here and added seconds of latency and substantial retained RSS. No second backend, model download, fine-tuning, GUI, tracing/log/service recipe or automatic task execution was added.

## Next comparison gates

Record these provisional usability budgets now, after the short pilot and before a fresh final comparison: warm p95 at most 2,000 ms, fresh worker wall at most 5,000 ms, total process RSS at most 2,048 MiB, and retained idle RSS growth after explicit unload at most 128 MiB. A one-shot CLI must leave no model process after exit. These thresholds are engineering assumptions for occasional command lookup; seek product acceptance before final claims, and retain their timestamp/provenance if changed. They are not retroactive pilot acceptance criteria. Current C misses the latency and retained-memory targets.

Freeze a fresh authored set and expected semantics across supported paraphrases, missing-input, ambiguous, compound and unsupported requests before comparing final candidates. Keep it out of prompt/router tuning; inspected failures make it development evidence and require another reserved set. Compare A/B/C with identical supplied inputs and B/C definitions. Score useful correct coverage, accuracy among suggestions, partial/wrong answers, unsupported responses, necessary/unnecessary clarifications, fabricated inputs and wrong-platform outputs separately, preserving both metadata interpretations. Publish negative results. #2 final scoring, #4 final comparison/adoption and #7's later slices remain open.

Validation: 51 source tests and the same 51 tests against an installed wheel outside the clone passed. The isolated wheel smoke verified six packaged recipes, entry points, fresh index capture and the no-model lookup without runtime dependencies. Real MLX lookup/pilot ran with Metal access; a first sandbox-only launch failed because the sandbox could not access the GPU. No suggested app check, CI run or fresh independent semantic evaluation was performed in this slice.
