# Roihu full-corpus teacher run (2026-10-13)

All 2,520 corpus requests, five samples each, seeds 1000-1004, temperature 0.7, top_p 0.95, top_k 0, max_tokens 16384, concurrency 24. Prompt SHA-256 `082762b9…`, request file SHA-256 `5577a8b5…` (identical to the 27B pilot).
Model `Qwen/Qwen3.8-Flash-Next-FP8` revision 236dfdf285828023ca3bcd3f37366c58a3469b13; vLLM 0.29.0 (`python-vllm/0.29.0`) on CSC Roihu-GPU, 4xGH200, tensor parallel 4 with expert parallel; thinking on, returned in `content` with only a closing `</think>`.
Job 2257376, `gpumedium`, finished in 4 h 23 min (sampling 15,586 s). Script: `tools/roihu_teacher_pilot.sbatch`, run with `TAG=full RUN=stage-all LIMIT=0 CONC=24`.
Server flags beyond defaults: `--generation-config vllm --max-model-len 32768 --max-num-seqs 32 --gdn-prefill-backend triton --kernel-config '{"enable_flashinfer_autotune": false}'`.
Sampler: `tools/teacher_sample.py` parses only text after the last `</think>` (PR #23). 12,279 of 12,600 samples parsed and stopped cleanly; 321 were rejected as unparsed or incomplete (307 hit the token cap, and 14 stopped but failed parsing).

`roihu_full_raw_samples.jsonl` SHA-256: `f441332f08ad3655877a1ece27595b518c0a197744bf278cd054a25a235ea4bd`
`roihu_full_manifest.json` SHA-256: `362f4ccaf5bec7770821fc652bac1260522e5c54d2f386371194ab7773bb728c`

Builder result and review: `data/distill/roihu_full_quality_report.md`, `data/distill/roihu_full_review_result.md`. Training rows: `data/distill/roihu_full_train.jsonl` (1,075: 832 commands and 243 abstentions). The retained 30-command review sample predates the final quarantine exclusions and remains unchanged.
This run supersedes the stopped 5090 stage-1 run; the pilot comparison and the switch decision are recorded in `data/teacher/README.md` (PR #23).
