# Issue #8: zero-step fine-tune feasibility

2026-10-11, repository `4ce57fd`, Apple M4 (`Mac16,1`), 16 GiB RAM.
The zero-update round trip passed: **26/61 correct on dev, 0/61 per-case
label flips** against a fresh default baseline. No training run or frozen
evaluation was performed. [Machine-readable results](finetune-feasibility-results.json)
retain both sets of per-case labels.

## Weights and licence decision

The [upstream model card](https://huggingface.co/ThorOdinson246/nl2sh-1.5b-Q4_K_M/blob/f64d174db959401a2a3c8b2e3b41c73bced04ccc/README.md)
names **Qwen/Qwen2.5-Coder-1.5B-Instruct**, declares **Apache-2.0**, and describes
a merged LoRA trained on 125,770 shell pairs. This agrees with the
[upstream repository](https://github.com/ThorOdinson246/whatisit-nl2sh#training-setup).
At model revision `f64d174db959401a2a3c8b2e3b41c73bced04ccc`, the published files
are `.gitattributes`, `README.md`, and the Q4_K_M GGUF. No original adapter or
safetensors are published there. The local file's SHA-256 matches its published
LFS object hash.

The owner approved **A: dequantize the existing NL2SH GGUF**, after considering
B: start from official Qwen Instruct weights. A preserves the NL2SH tuning;
B loses it and cannot reproduce the default by a no-op round trip. Dequantizing
A cannot recover the pre-quantization weights. The parity check therefore matters.

The [base licence](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct/blob/2e1fd397ee46e1388853d2af2c993145b0f1098a/LICENSE)
permits derivative redistribution subject to Apache-2.0's licence, modification,
attribution, and NOTICE requirements. Preserve the upstream tldr-pages
CC-BY-4.0 attribution as well. The model card discloses three training-data
sources whose declared licences could not be independently verified; this
experiment does not resolve that provenance uncertainty or certify distribution
rights for those sources. The approved decision is to proceed locally with A.
[The retained notice](finetune-NOTICE.txt) includes that disclosure and describes
the local conversion. No derivative has been published.

## Round trip and paired results

`tools/finetune_roundtrip.py` uses llama.cpp's `gguf` reader, dequantizer, tensor
name mapping, and writer, plus MLX-LM's Qwen2 model and LoRA implementation.
It validates exact tensor coverage, shapes and finite values before loading.
Matrices become float16; original float32 biases/norms remain float32.
A zero-initialized rank-8 LoRA on the final 16 layers is merged without updates.
All 338 tensor values, shapes and dtypes match before/after merging; signed-zero
bits are ignored because zero addition can change `-0.0` to `+0.0`.
The resulting GGUF is quantized with the installed `llama-quantize`
build **10333 (`08659901c`)**, Q4_K_M, four threads.

MLX-LM cannot load this GGUF directly, and its built-in GGUF exporter does not
support Qwen2 in the installed version. The GGUF writer preserves the source
metadata instead. The final artifact has the same 168 Q4_K, 29 Q6_K, and 141 F32
tensors; all metadata matches. Only 142/338 tensors are byte-identical after
requantization, so unchanged labels do not imply identical weights or commands.

| dev/lint outcome | Default | Round trip |
|---|---:|---:|
| pass | 20 | 20 |
| wrong | 23 | 23 |
| rejected | 10 | 10 |
| abstain-ok | 6 | 6 |
| abstain-missed | 2 | 2 |
| correct | 26/61 | 26/61 |
| p50 | 0.22 s | 0.21 s |

**Differing case IDs: none.** Comparison uses all five labels, including wrong
versus rejected, rather than just correct/incorrect totals. Runs used the unchanged
lint/deletion harness, greedy decoding, four server threads, and context 4096.
`whatisit stop` was used between model swaps. `pgrep -fl llama-server` confirmed
both the default GGUF and the converted GGUF at their respective prompt audits,
and the converted path during its dev evaluation. The default benchmark and
the audit environments' upstream `engine.py` and `config.py` are byte-identical.
61 dev cases are a limited parity check, not a general equivalence guarantee.

SHA-256:

```text
source:    6f8a17a11129a31074c944f4c2602453fafd9de43bdaeb1630a8f511ec820f71
roundtrip: 56369de81f578e9ce84d3f365ce1e7fc54e12f4fb38e53ec191821838298beab
```

## Prompt equality

The `prompt` action captures the actual upstream chat-completion body produced
by the worker, replacing inference only. It compares independently constructed
training messages with that body, then compares the tokenizer's rendering with
the running server's `/apply-template` response, byte for byte. `/tokenize`
also matches the training tokenizer's IDs with no added BOS token. Finally,
MLX-LM's actual `ChatDataset(mask_prompt=True)` must produce the identical token
prefix and mask offset when an assistant response is appended.

Both default and converted servers passed **62/62** checks: all 61 dev requests
and one explicit Unicode-path case. These are formatting checks only; no dev
examples were saved as training data or used for gradient calculation.
The original GGUF and the pinned base tokenizer have identical chat-template text.

System prompt (upstream `config.SYSTEM_PROMPT`, used by `engine.py`):

```text
You are a shell command generator. Output exactly one line: a single POSIX/bash command that accomplishes the user's request. No prose, no markdown fences, no explanation.
```

User prefix, followed by a newline and the request:

```text
Target system: macOS, using zsh and the built-in BSD command-line tools. Use macOS commands and flags, not Linux/GNU-only ones. If required inputs are missing or the request is ambiguous, output no command.
```

The ambiguity sentence was missing from the handoff's abbreviated prefix.
For an explicit path the worker additionally appends `\nExplicit inputs: `
and JSON with `ensure_ascii=False`. Host context stays disabled.
The no-tools template renders the system and user turns as
`<|im_start|>ROLE\nCONTENT<|im_end|>\n`, then appends
`<|im_start|>assistant\n`. Here `\n` denotes an actual newline.
Training adds the assistant command and end-of-turn suffix; its input prefix
remains identical to serving. Future training should use chat records with
explicit system/user/assistant roles, not a completion format that omits the system.

## Memory dry run

On the dequantized model: batch **1**, input sequence **512**, final **16** LoRA
layers, rank **8**, scale **20**, dropout **0**, seed **42**, **5,275,648** trainable
parameters, AdamW state initialized and evaluated. A forward/backward pass used
synthetic token IDs `0..512`; gradients were finite and nonzero. No optimizer
update was called. It neither loaded training data nor used eval inputs.

- Peak MLX allocation during the probe: **10,183,684,840 bytes (9.48 GiB)**.
- Process maximum RSS: **3,230,711,808 bytes (3.01 GiB)**.
- Physical memory: **17,179,869,184 bytes (16 GiB)**.

MLX allocation and RSS measure different things; do not add them to infer total
RAM. The pass completed locally, supporting LoRA feasibility for this configuration.
This is a zero-update training-memory probe, not a measured full training run or
optimizer-update peak. Larger batches, lengths, ranks, or more adapted layers remain
unmeasured. Issue #9 must record the actual training-run peak.

## Reproduce locally

Large artifacts are preserved at `~/.local/share/whatisit/finetune/issue8/`:
`dequantized/`, `fused/`, `roundtrip-f16.gguf`, `roundtrip-Q4_K_M.gguf`, licence/
NOTICE files, pinned upstream card, baseline/candidate labels, paired flips,
prompt audits, and memory report. The experiment environment is temporary;
its complete package versions are in [finetune-requirements.txt](finetune-requirements.txt).
No runtime dependencies were added to the application.

Use a new output directory: the script refuses to overwrite an existing one.
The following recreates the experiment outside the repository:

```sh
uv venv --python 3.12.10 /private/tmp/whatisit-ft8-repro-venv
uv pip install --python /private/tmp/whatisit-ft8-repro-venv/bin/python -r docs/finetune-requirements.txt
hf download Qwen/Qwen2.5-Coder-1.5B-Instruct config.json tokenizer.json tokenizer_config.json vocab.json merges.txt generation_config.json LICENSE \
  --revision 2e1fd397ee46e1388853d2af2c993145b0f1098a --local-dir /private/tmp/whatisit-ft8-repro-metadata
whatisit stop
/private/tmp/whatisit-ft8-repro-venv/bin/python tools/finetune_roundtrip.py roundtrip \
  ~/.local/share/whatisit/models/nl2sh-1.5b-Q4_K_M.gguf /private/tmp/whatisit-ft8-repro-metadata /private/tmp/whatisit-ft8-repro
~/.local/share/whatisit/bin/llama-quantize /private/tmp/whatisit-ft8-repro/roundtrip-f16.gguf \
  /private/tmp/whatisit-ft8-repro/roundtrip-Q4_K_M.gguf Q4_K_M 4
/private/tmp/whatisit-ft8-repro-venv/bin/python tools/finetune_roundtrip.py probe /private/tmp/whatisit-ft8-repro/dequantized

whatisit stop
PYTHONPATH=src WHATISIT_MODEL="$HOME/.local/share/whatisit/models/nl2sh-1.5b-Q4_K_M.gguf" \
  ~/.local/pipx/venvs/whatisit/bin/python tools/eval_fallback.py dev lint -q
cp /tmp/eval-dev-lint.json /private/tmp/whatisit-ft8-repro/baseline-dev-lint.json
pgrep -fl llama-server
PYTHONPATH=src WHATISIT_MODEL="$HOME/.local/share/whatisit/models/nl2sh-1.5b-Q4_K_M.gguf" \
  /private/tmp/whatisit-ft8-repro-venv/bin/python tools/finetune_roundtrip.py prompt /private/tmp/whatisit-ft8-repro-metadata

whatisit stop
PYTHONPATH=src WHATISIT_MODEL=/private/tmp/whatisit-ft8-repro/roundtrip-Q4_K_M.gguf \
  ~/.local/pipx/venvs/whatisit/bin/python tools/eval_fallback.py dev lint -q
cp /tmp/eval-dev-lint.json /private/tmp/whatisit-ft8-repro/dev-lint.json
pgrep -fl llama-server
diff /private/tmp/whatisit-ft8-repro/baseline-dev-lint.json /private/tmp/whatisit-ft8-repro/dev-lint.json
PYTHONPATH=src WHATISIT_MODEL=/private/tmp/whatisit-ft8-repro/roundtrip-Q4_K_M.gguf \
  /private/tmp/whatisit-ft8-repro-venv/bin/python tools/finetune_roundtrip.py prompt /private/tmp/whatisit-ft8-repro/fused
whatisit stop
```

Validation performed: 14 existing unit tests with host access; three conversion
checks (tensor mapping, missing/extra tensors, signed-zero comparison); full
round trip and no-op tensor checks; both prompt audits; paired dev evaluation.
The initial sandboxed suite failed two `sysctl` subcases because host access was
denied; the same 14 tests passed outside the sandbox. The final file-copy changes
only add licence/NOTICE sidecars and do not change the evaluated weights.

Frozen was not read or run. No accuracy tuning, new eval data, application
behavior change, commit, push, or issue update was made. Issue #11's keep rule
remains unchanged and has not been invoked. Issue #9 training is not started.
