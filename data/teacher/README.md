# Teacher pilot
Final pilot: first 100 corpus requests, five samples each; seeds 1000–1004, temperature 0.7, top_p 0.95, top_k 0, max_tokens 16384, concurrency 4.
Qwen3.8-27B UD-Q6_K revision 4ca720788d1e01f1bff70c033e0d0028fd02e502; llama.cpp b11565 CUDA 12.8; thinking enabled; four 32768-token slots.
Exact server command: `LD_LIBRARY_PATH=/tmp/whatisit-teacher/cudart-llama-b11565-bin-ubuntu-cuda-12.8-x64:/tmp/whatisit-teacher/llama-b11565 /tmp/whatisit-teacher/llama-b11565/llama-server -m /tmp/whatisit-teacher/Qwen3.8-27B-UD-Q6_K.gguf --alias Qwen3.8-27B -ngl 99 --ctx-size 131072 --parallel 4 --flash-attn on --cache-type-k q8_0 --cache-type-v q8_0 --reasoning on --reasoning-format deepseek --host 127.0.0.1 --port 8080`
Owner-approved deviation: replaced brace regex extraction with JSONDecoder.raw_decode; teacher system prompt unchanged. Token cap increased after 8k truncation; concurrency reduced after eight 32k slots exhausted VRAM.
`wall_seconds` mirrors the original sampler field `wall_seconds_this_run` (6018.8); raw samples are unchanged.
pilot_raw_samples.jsonl SHA-256: `84a8bcb9bdc7f1e6eb7b1068c56c41add5588c18176a8705cc108cb10aada750`
pilot_manifest.json SHA-256: `2d57aff827735651ef0bc96076dd3687a88d0ab91b28c8fee29108f13743a030`
