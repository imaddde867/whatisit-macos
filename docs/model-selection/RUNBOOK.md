# Execution runbook: choose and qualify a 1–3B macOS command model

**Parent decision:** [2026-10-21-research.md](2026-10-21-research.md).  
**Target machine:** personal Apple M4 MacBook Pro, 16 GiB; **no work-only GPU needed** for screening.  
**Current state:** proposal and documentation, **not executed**. Every checkbox below is unchecked until its evidence artifact exists.

## Non-negotiable guardrails

1. **Do not alter the shipped model, `src/`, `eval/`, `data/distill/stage2-v3/`, or upstream `whatisit` configuration from this research branch.** Work in an isolated worktree and an external experiment directory.
2. **Do not read, sample, modify, score or include `eval/frozen.jsonl` or `eval/heldout.jsonl` during screening, dataset repair, prompt design, optimization or seed selection.** Their use is reserved for issue [#11](https://github.com/imaddde867/whatisit-macos/issues/11).
3. **No gradient updates on v4 data until [#36](https://github.com/imaddde867/whatisit-macos/issues/36) acceptance passes.** The 20-step optimizer test below is also deferred until that dependency is met. Zero-shot tests on *development only* are allowed.
4. Do not execute generated shell commands. Only the project's allowlisted, disposable scratch-fixture semantic evaluator may run specific safe commands; dangerous requests must be reviewed statically.
5. Use the **same** system/user instruction and validator for matched comparisons. A change to `shell.py` / `maclint.py` / safety code invalidates historical comparability; re-baseline.
6. Do not create a second, competing release criterion. [#11's frozen+held-out, exact one-sided sign-test KEEP rule](https://github.com/imaddde867/whatisit-macos/issues/11) remains binding.
7. Labels of `correct`, `incorrect` or `abstain` must include a semantic reason and evidence; regex alone and model confidence alone are insufficient.

## Phase 0 — Protect the checkout and capture reproducibility

- [ ] Fetch the documentation branch into an independent worktree.
- [ ] Record Mac environment and Git SHA; check for local changes.
- [ ] Run the existing tests *without touching protected evaluation artifacts*.
- [ ] Keep downloads and runs outside the repository; avoid committing model weights, generated outputs, or user data.

From an existing local clone of `whatisit-macos`:

~~~sh
git fetch origin
git worktree add ../whatisit-small-model-research origin/research/small-model-selection-20261021
cd ../whatisit-small-model-research

git status --short
git rev-parse HEAD
sw_vers
uname -m

# Outside the source repository: large weights, environment and receipts.
export MODEL_RUN="$HOME/.local/share/whatisit/model-selection-20261021"
mkdir -p "$MODEL_RUN/receipts" "$MODEL_RUN/models"

{
  date -u "+%Y-%m-%dT%H:%M:%SZ"
  git rev-parse HEAD
  sw_vers
  uname -a
  command -v uv || true
  command -v python3 || true
  command -v hf || true
} > "$MODEL_RUN/receipts/environment.txt"

# Existing Python environment; adjust only if the upstream whatisit venv moved.
PYTHONPATH=src "$HOME/.local/pipx/venvs/whatisit/bin/python" \
  -m unittest discover -s tests
~~~

`git worktree add ... origin/branch` produces a detached read-only starting point by default. If you need to commit experiments, create a separate local `exp/...` branch *in that worktree*; never experiment on `main` or rewrite this research document's base.

Before testing, snapshot the Python environment and versions (using `uv` in the following examples; install it yourself if it is not already present). Do not assume a particular unverified version works:

~~~sh
uv venv --python 3.12 "$MODEL_RUN/venv"
uv pip install --python "$MODEL_RUN/venv/bin/python" mlx-lm huggingface_hub psutil

uv pip freeze --python "$MODEL_RUN/venv/bin/python" \
  > "$MODEL_RUN/receipts/requirements-resolved.txt"
"$MODEL_RUN/venv/bin/python" -c 'import mlx, mlx_lm; print("MLX and MLX-LM import OK")'
"$MODEL_RUN/venv/bin/mlx_lm.generate" --help \
  > "$MODEL_RUN/receipts/generate-help.txt"
"$MODEL_RUN/venv/bin/mlx_lm.lora" --help \
  > "$MODEL_RUN/receipts/lora-help.txt"
~~~

**Verification:** these commands are selected from the current [MLX-LM CLI](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/generate.py) and [LoRA CLI](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/lora.py), but they have **not** been run here. If the chosen versions change their interface, record the incompatibility and update the experimental recipe before proceeding. Do not fix it by silently changing the production application.

## Phase 1 — Unblock *verified* stage2-v4 labels (required for any training)

- [ ] Inspect the latest [PR #38](https://github.com/imaddde867/whatisit-macos/pull/38) branch head, `CAMPAIGN-STATUS.md`, rubric, controls, and pass-1 verdict manifests.
- [ ] Reconcile the **future-dated b06–b22 entries** (status file says 2026-10-22, commit was written 2026-10-21) and reviewer/committer provenance before signing off an audit.
- [ ] Confirm the recorded **23/23** pass-1 claims and the validity of all uncontested controls. Document calibration-label noise (~8% of one inspected sample) and the contested-control policy.
- [ ] Run the **pre-registered, deterministic 20% independent confirm** with new, blind pass-2 judges; no reused pass-1 judge on an overlapping item.
- [ ] Build the verified dataset **only after genuine pass-2 verdict files exist**; no synthetic/mock pass-2 files.
- [ ] Human-spot-check ≥30 retained command and abstention rows, quarantine or re-judge actual errors, keep judge identities and evidence.
- [ ] Repeat the build from pinned inputs to prove byte-identical outputs; save dataset counts, dropped reasons, leakage report, source-license/use limitations, manifests and SHA-256.
- [ ] Record that issue [#36](https://github.com/imaddde867/whatisit-macos/issues/36) is accepted **before** proceeding to Phase 4.

The existing PR #38 branch—not this documentation branch—contains the v4 campaign artifacts. The **source-of-truth commands** are in its [judge protocol](https://github.com/imaddde867/whatisit-macos/blob/campaign/v4-r2-20261020/data/distill/stage2-v4/judge/protocol.md). From a checkout of that branch with its exact pinned environment, *after confirming pass 1 and before pass 2*:

~~~sh
# Director only; do not give control maps to judges.
PATH=/usr/bin:/bin:/usr/sbin:/sbin \
PYTHONPATH=src:tools \
"$HOME/.local/pipx/venvs/whatisit/bin/python" \
tools/make_v4_confirm.py \
  data/distill/stage2-v4/judge/pool/keymap.json \
  data/teacher/roihu_full_raw_samples.jsonl \
  data/distill/stage2-v3/requests.jsonl \
  data/distill/stage2-v4/judge/verdicts \
  data/distill/stage2-v4/judge/confirm \
  --sample 0.2 --seed 13 --batch-size 90 \
  --adjudication \
  data/distill/stage2-v4/judge/control-adjudication-r3-20261021.json
~~~

**STOP:** deliver only blind `confirm` batch files and the rubric to independent pass-2 judges. Do **not** hand them keymaps, director maps, control expectations, earlier labels, or this research score table.

After pass-2 verdicts have been independently completed and validated:

~~~sh
PATH=/usr/bin:/bin:/usr/sbin:/sbin \
PYTHONPATH=src:tools \
"$HOME/.local/pipx/venvs/whatisit/bin/python" \
tools/build_verified_dataset.py \
  data/distill/stage2-v4/judge/pool/keymap.json \
  data/distill/stage2-v4/judge/verdicts \
  data/distill/stage2-v4/judge/confirm \
  data/distill/stage2-v4/judge/confirm-verdicts \
  data/distill/stage2-v4/verified \
  --adjudication \
  data/distill/stage2-v4/judge/control-adjudication-r3-20261021.json
~~~

These are recorded commands from the campaign protocol, **not executed by this documentation task**. The builders refuse non-empty output directories; do not clobber audit evidence. The pass-2 protocol may be amended in the campaign branch; use its current committed rubric and hash-pinned artifacts. No v4 training if the reproducibility, leakage or label-quality gate is unresolved.

## Phase 2 — Low-cost model screen, no new training

This phase can run independently while Phase 1 continues, but must use **development cases only**, with recorded model/template revisions. It must not change the #36 dataset labels.

- [ ] Download **one model at a time**; reuse cache (important on a phone hotspot).
- [ ] Verify model LICENSE, tokenizer hash, exact weight revision, architecture and backend support.
- [ ] Prove chat-prefix behavior, final answer/no-think behavior, EOS and one-line output on ≥10 manually inspected development prompts.
- [ ] Screen the same balanced ≤100 development requests across all candidates, covering BSD options, macOS-only commands, operands, composition and abstention.
- [ ] Record every candidate command and validator reason; adjudicate semantic correctness independently, blind to model identity.
- [ ] Measure initial cold generation, model-only warm generation, memory and tokens; **do not claim production end-to-end timing until integrated**.
- [ ] Rank by (1) accepted-wrong/safety, (2) semantic correct, (3) abstention, (4) latency/memory—not vendor benchmarks.

Exact checkpoint downloads (only confirmed public IDs):

~~~sh
"$MODEL_RUN/venv/bin/hf" download Qwen/Qwen3-1.7B-MLX-4bit \
  --local-dir "$MODEL_RUN/models/qwen3-1.7b-mlx4"

"$MODEL_RUN/venv/bin/hf" download LiquidAI/LFM2.5-1.2B-Instruct-MLX-5bit \
  --local-dir "$MODEL_RUN/models/lfm25-1.2b-mlx5"
~~~

Qwen3 command-only smoke test:

~~~sh
"$MODEL_RUN/venv/bin/mlx_lm.generate" \
  --model "$MODEL_RUN/models/qwen3-1.7b-mlx4" \
  --system-prompt "Output one stock macOS zsh command. No prose, no markdown. Never execute commands. If input is insufficient or unsafe, abstain." \
  --prompt "Show the current Mac battery charging status." \
  --chat-template-config '{"enable_thinking":false}' \
  --max-tokens 64 --temp 0 --seed 42 --verbose false \
  > "$MODEL_RUN/receipts/qwen3-smoke.txt"
~~~

**Do not presume** that the MLX tokenizer honors `enable_thinking=false`: inspect the rendered prefix, tokens and output. If it emits `<think>` or cannot terminate consistently, fix the *experimental tokenizer/template* and re-run the matching tests before attributing any result to non-thinking inference. Qwen's published default sampling settings differ from greedy decoding; record them as an optional **separate pre-registered arm**, not a post-hoc best-of-many.

LFM2.5 smoke test (its published checkpoint recommends temperature 0.1):

~~~sh
"$MODEL_RUN/venv/bin/mlx_lm.generate" \
  --model "$MODEL_RUN/models/lfm25-1.2b-mlx5" \
  --system-prompt "Output one stock macOS zsh command. No prose, no markdown. Never execute commands. If input is insufficient or unsafe, abstain." \
  --prompt "Show the current Mac battery charging status." \
  --max-tokens 64 --temp 0.1 --seed 42 --verbose false \
  > "$MODEL_RUN/receipts/lfm25-smoke.txt"
~~~

**Qwen3.5-2B:** its [official ID](https://huggingface.co/Qwen/Qwen3.5-2B) is verified but its primary checkpoint includes multimodal scaffolding. Do not invent a particular official MLX quantized repo name. First verify and pin an actual text-generation-capable MLX or llama.cpp conversion, then run the same smoke and semantic screen; skip with `backend_unqualified` rather than recording a fake zero score.

Existing NL2SH control (stock PATH, no protected set):

~~~sh
PYTHONPATH=src "$HOME/.local/pipx/venvs/whatisit/bin/python" \
  tools/eval_fallback.py dev lint -q
cp /tmp/eval-dev-lint-detail.json \
  "$MODEL_RUN/receipts/nl2sh-dev-detail.json"

PYTHONPATH=src "$HOME/.local/pipx/venvs/whatisit/bin/python" \
  tools/eval_fallback.py everyday lint -q
cp /tmp/eval-everyday-lint-detail.json \
  "$MODEL_RUN/receipts/nl2sh-everyday-detail.json"
~~~

The two commands above produce **regex-era harness labels** and raw candidate details; they are **not semantic truth**. The candidate screen must use a separate blind semantic review and the *same corrected guard* before any improvement claim. DO NOT invoke `eval_fallback.py frozen` or `heldout`.

### Minimum result schema for the new screening harness (not currently implemented)

Implement a small **experimental** adapter/harness on an `exp/...` branch, keeping production untouched. For each request save:

~~~json
{
  "case_id": "dev-001",
  "model_revision": "<exact HF commit>",
  "prompt_template_sha256": "<hash>",
  "request": "<development request>",
  "raw_response": "<as generated>",
  "candidate_command": "<parsed one-line command or null>",
  "guard_accepted": false,
  "guard_reason": "<reason or null>",
  "semantic_verdict": "correct|incorrect|abstain_correct|abstain_wrong|unresolved",
  "error_category": "linux_syntax|hallucinated_flag|wrong_tool|missed_constraint|wrong_operand|wrong_output|unsafe|should_abstain|other|null",
  "judge_evidence": "<man page, read-only check or safe scratch fixture>",
  "cold_ms": null,
  "warm_ms": null,
  "peak_rss_bytes": null
}
~~~

A schema is not a script: **this harness has not been implemented** on the research branch. Before comparing totals, write tests proving that the same request and command receive consistent labels and that all cases are accounted for. Split `unresolved` into a reported category, not automatically "correct".

## Phase 3 — Record a decision and pre-register one training experiment

- [ ] Publish a read-only side-by-side table for the top three. Explicitly mark unavailable/failed backend measurements as missing, not zero.
- [ ] Choose **Qwen3-1.7B by default**, unless LFM is non-inferior on independently judged command accuracy while materially faster/smaller, or Qwen3.5 gains sufficiently more correctness to justify its training/deployment burden.
- [ ] Keep **one primary** training candidate and **at most one justified challenger**; save selection rationale **before** training results.
- [ ] Pin the exact data split, checkpoint revision, prompt/template rendering, optimizer, seeds (e.g. 42/43/44), quantization plan, eval policy, tie-break, stop rule, and resource budget before touching gradients.
- [ ] Re-baseline the shipped NL2SH model under the **same post-#35 runtime/guard, Mac, evaluation revision, and semantic judge**; old counts cannot be promoted as new matched evidence.

**Stop if #36 is still open/unqualified.**

## Phase 4 — LoRA/QLoRA only after verified v4 is ready

- [ ] Copy the **verified** v4 records into `$MODEL_RUN/data/train.jsonl` and `valid.jsonl`. *Copy, do not mutate*, with source hash recorded. The source should be the accepted `data/distill/stage2-v4/verified/` artifact; do not use staged raw pass-1 labels or `stage2-v3` as "verified v4".
- [ ] Create an **intent-family-grouped** split with no overlapping normalized command+request family; preserve command/abstention balance. Save group membership and SHA-256. No eval cases, prompt variants or accepted reference commands may leak from `eval/`.
- [ ] Verify the chosen tokenizer's **actual** training `apply_chat_template` output, user/system prefix, assistant start, thinking tokens, loss mask, EOS and empty-refusal encoding against inference. If mismatch: **STOP** and amend the tokenizer/data adapter; do not train a mismatched checkpoint.
- [ ] Verify chosen LoRA keys exist in Qwen3 `model.layers` and inspect exact trainable parameter count. If there are zero trainable parameters: **STOP**.
- [ ] Confirm optimizer/backward feasibility over 20 updates, report swap and memory pressure, and keep the Mac usable. Only then consider a registered one-epoch run.
- [ ] Report the three predeclared seeds and paired semantic dev outcomes; do not pick a favorable seed post-hoc.

The starting configuration is committed at [`experiments/model-selection/qwen3-mlx-lora.yaml`](../../experiments/model-selection/qwen3-mlx-lora.yaml). **It is proposed, not Mac-validated.**

~~~sh
# Do this ONLY after Phase 1's verified-v4 dataset gate and Phase 4 template
# and group-split checks pass.
test -s "$MODEL_RUN/data/train.jsonl" || exit 1
test -s "$MODEL_RUN/data/valid.jsonl" || exit 1

"$MODEL_RUN/venv/bin/mlx_lm.lora" --train \
  --model "$MODEL_RUN/models/qwen3-1.7b-mlx4" \
  --data "$MODEL_RUN/data" \
  --config experiments/model-selection/qwen3-mlx-lora.yaml \
  --iters 20 --seed 42 \
  --adapter-path "$MODEL_RUN/qwen3-probe-seed42"

shasum -a 256 "$MODEL_RUN/qwen3-probe-seed42/adapters.safetensors" \
  > "$MODEL_RUN/receipts/qwen3-probe-adapter-sha256.txt"
~~~

The CLI uses `scale` rather than PEFT `alpha`. The 20-step run is a **true optimizer probe**, not a claim of learned generalization. Memory estimates are not proof of 16-GB viability; obtain peak MLX active/peak allocation, process-tree RSS, OS memory pressure, swap delta, wall time/step, and repeat if needed. Do not silently increase the batch, context, rank, layers, or epochs without a registered new experiment.

Full training only once the probe succeeds and a **validation-based stop/selection rule** is frozen. If training improves loss but not semantic correctness, stop. If seed spread remains high, report all seeds and do not cherry-pick.

## Phase 5 — Quantization, deployment, and matched performance

- [ ] Compare unmodified 4-bit checkpoint and MLX LoRA adapter, with actual aligned prompt/output code.
- [ ] If selecting an adapter, verify a **real converter** from its exact architecture and tokenizer to supported GGUF, or explicitly keep a compatible MLX backend. Do not assume direct adapter interchange with llama.cpp.
- [ ] Test fused/higher precision and candidate quantized Q4_K_M; also compare Q5_K_M/Q6_K **if** quality degrades and footprint allows. Check per-case semantic flips at every stage.
- [ ] Run both candidate and default through the *same* production-grade `local_recovery_worker` guard; measure correct, accepted-wrong, abstention, new rejection modes and memory/latency.
- [ ] Measure independent **cold** first-run and **warm** throughput across at least 30 (preferably 100) predeclared development requests. Record p50, p95, TTFT, complete end-to-end p50/p95, and token count. Separate OS file caching and resident-server effects; never compare a fresh MLX process with warm llama-server as though matched.
- [ ] Monitor Mac swap, memory pressure and usability; prove workers unload at the documented idle timeout. A larger persistent daemon is *not* an automatic improvement.
- [ ] Save one candidate (including exact adapter and export hashes) only if it shows clear **semantic** development gain with no guard/safety regression and acceptable system footprint.

For a *cold, model-only smoke* (not end-to-end CLI timing), macOS `/usr/bin/time -l` provides max resident size:

~~~sh
/usr/bin/time -l "$MODEL_RUN/venv/bin/mlx_lm.generate" \
  --model "$MODEL_RUN/models/qwen3-1.7b-mlx4" \
  --system-prompt "Output one stock macOS zsh command. No prose." \
  --prompt "Show the current Mac battery charging status." \
  --chat-template-config '{"enable_thinking":false}' \
  --max-tokens 64 --temp 0 --seed 42 --verbose false \
  > "$MODEL_RUN/receipts/qwen3-cold-output.txt" \
  2> "$MODEL_RUN/receipts/qwen3-cold-time.txt"
~~~

This measures command startup plus model load and generation **for one request**. For warm p50/p95, load the model once and time repeated in-process calls, and separately time calls through the final worker+validator. Neither `mlx_lm.generate` alone nor the upstream `eval_fallback.py` provides all needed percentiles/process-tree metrics; implement and test the experimental harness before publishing performance comparisons.

## Phase 6 — Frozen release gate, or honest null result

- [ ] Lock one chosen model+adapter+quantization, full code/data hashes, tokenizer, config, scorer, judge instructions and static validation code.
- [ ] Lock matched default controls, the original [#11 KEEP rule](https://github.com/imaddde867/whatisit-macos/issues/11), resource budget and blind-judgment protocol *before* opening protected files.
- [ ] Trigger the one-time independent pooled frozen (59) + held-out (150) comparison. Report accepted-wrong, abstain-missed, paired correct wins/losses and **one-sided exact sign-test p**, plus dev and everyday non-regression on the same scorer.
- [ ] **KEEP** only if *every pre-existing #11 condition* passes; otherwise **SHELVE**, preserve null evidence and do not use the sealed cases to tune another model.
- [ ] Only a later separately preregistered campaign with a **new untouched held-out set** can justify another release attempt.

The research document's 95/141 development and 120/150 held-out objectives are **aspirational product targets**, not retroactive changes to this decision gate.

## Required deliverables / exact evidence checklist

Before opening a training PR, produce the following from the experiment (the names are proposed, not existing files):

| Artifact | What it must contain |
| --- | --- |
| `receipts/environment.txt` | machine/OS, versions, source SHA |
| `receipts/requirements-resolved.txt` | pinned environment (plus lockfile if possible) |
| `model-manifest.json` | HF IDs/revisions, weight and tokenizer hashes, licenses |
| `screen/requests.jsonl` | fixed **development-only** IDs and category sampling rationale |
| `screen/outputs/*.jsonl` | raw outputs, validated outputs, semantic verdicts with independent evidence |
| `screen/decision.md` | reason for primary and at most one challenger |
| `data/manifest.json` | qualified v4 artifact hashes, split families, leakage checks |
| `training/protocol.md` | pretrained baseline, LoRA keys and hyperparameters, seeds, pinned stop rule |
| `training/reports/*.json` | optimizer steps, losses, memory/swap, timing and adapter checksums |
| `conversion/manifest.json` | model fusion/GGUF, quantizer version and hashes, zero-update/semantic parity |
| `perf/*.json` | full pipeline cold/warm p50/p95, process-tree RSS, unload/idle memory |
| `eval/dev-semantic.jsonl` | per-case paired semantic wins/losses and accepted-wrong |
| `release/KEEP-or-SHELVE.md` | only after #11: single blinded comparison and official decision |

**What has been implemented by this branch:** these research and runbook documents and the proposed YAML. **What has not:** checkpoint downloads, a zero-shot harness, MLX optimization, conversion, Mac timing, semantic review, v4 confirmation or a release gate.

### Fastest useful next action

**Take the existing pass-1 campaign in [PR #38](https://github.com/imaddde867/whatisit-macos/pull/38) through the 20% independent confirmation and dataset-quality gates in [#36](https://github.com/imaddde867/whatisit-macos/issues/36).** In parallel, the safely independent task is a **Qwen3 vs LFM development-only zero-shot/latency screen**, starting with the two verified MLX model IDs above. Do not launch LoRA until the verified v4 dataset exists.
