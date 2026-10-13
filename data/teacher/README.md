# Teacher pilot
Final pilot: first 100 corpus requests, five samples each; seeds 1000–1004, temperature 0.7, top_p 0.95, top_k 0, max_tokens 16384, concurrency 4.
Qwen3.8-27B UD-Q6_K revision 4ca720788d1e01f1bff70c033e0d0028fd02e502; llama.cpp b11565 CUDA 12.8; thinking enabled; four 32768-token slots.
Exact server command: `LD_LIBRARY_PATH=/tmp/whatisit-teacher/cudart-llama-b11565-bin-ubuntu-cuda-12.8-x64:/tmp/whatisit-teacher/llama-b11565 /tmp/whatisit-teacher/llama-b11565/llama-server -m /tmp/whatisit-teacher/Qwen3.8-27B-UD-Q6_K.gguf --alias Qwen3.8-27B -ngl 99 --ctx-size 131072 --parallel 4 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --reasoning on --reasoning-format deepseek --host 127.0.0.1 --port 8080`
Owner-approved deviation: replaced brace regex extraction with JSONDecoder.raw_decode; teacher system prompt unchanged. Token cap increased after 8k truncation; concurrency reduced after eight 32k slots exhausted VRAM.
`wall_seconds` mirrors the original sampler field `wall_seconds_this_run` (6018.8); raw samples are unchanged.
pilot_raw_samples.jsonl SHA-256: `84a8bcb9bdc7f1e6eb7b1068c56c41add5588c18176a8705cc108cb10aada750`
pilot_manifest.json SHA-256: `2d57aff827735651ef0bc96076dd3687a88d0ab91b28c8fee29108f13743a030`

# Teacher switch: Qwen3.8-Flash-Next-FP8 on Roihu (2026-10-13)
Roihu pilot, same 100 requests, prompt hash `082762b9…`, corpus hash `5577a8b5…`, n=5, temperature 0.7, top_p 0.95, top_k 0, max_tokens 16384, seeds 1000–1004; job 2257129.
Model `Qwen/Qwen3.8-Flash-Next-FP8` revision 236dfdf285828023ca3bcd3f37366c58a3469b13; vLLM 0.29.0 (`python-vllm/0.29.0`), TP4 + expert parallel on 4xGH200, thinking on (default effort), no reasoning parser: thinking arrives in `content` with only a closing `</think>`.
Server flags beyond the defaults: `--generation-config vllm` (ignore the model's top_k=20), `--max-num-seqs 32` (Mamba cache blocks cap), `--gdn-prefill-backend triton` (container lacks `cutlass.cute`), flashinfer autotune off (one run exceeded gloo's 30 min barrier timeout).

| | Qwen3.8-27B (5090) | Flash-Next (Roihu) |
|---|---|---|
| kept + abstain, after leakage gate | 26 + 9 = 35 | 35 + 8 = 43 |
| no majority / no valid command | 53 / 4 | 48 / 3 |
| lint-rejected candidates | 9.5% | 8.7% |
| wall time, 100 x 5 | 6019 s | 1078 s |

The pre-registered rule (+10 usable rows at no lower precision) was **not met** (+8, within noise), and no label review was run on the Roihu pilot. The owner chose Roihu for the full corpus anyway for throughput (about 5.6x). This is a deliberate override of the rule, not a result of it. The Roihu pilot quarantined 6 rows on the leakage gate only; the 27B figure of 24 includes author-listed bad labels.
Sampler change: `teacher_sample.py` now parses only the text after the last `</think>`; the pilot ran the older parser (9 of 500 samples hit `length` and were marked parsed; the builder drops non-`stop` rows).
The full corpus run (2,520 requests, concurrency 24, one raw file and manifest) supersedes the 5090 stage-1 run, which was stopped.
