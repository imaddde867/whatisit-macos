# Distillation quality report

Host: macOS-27.0.1-arm64-arm-64bit-Mach-O (macOS verification)

Teacher: Qwen3.8-27B
Quant: Qwen3.8-27B-UD-Q6_K.gguf revision4ca720788d1e01f1bff70c033e0d0028fd02e502
Server: llama.cpp b11565 CUDA12.8
Teacher host: Linux-7.0.0-38-generic-x86_64-with-glibc2.39
Request SHA-256: 5577a8b501cdcee38ae659ffad46088bde49f97ab73a49626dc9812f6b28d782
Teacher prompt SHA-256: 082762b95298f9fc1e54f2260ca77aaaa922f380cc708aa1c605a49fe39cbd1e
Sampling: n=5, temperature=0.7, top-p=0.95, max tokens=16384, seed base=1000.

Requests: 100; kept commands: 26; abstain: 9; dropped: 57 (4 no valid command, 53 no majority).
Agreement histogram (maximum identical verified commands): {0: 12, 1: 35, 2: 19, 3: 9, 4: 11, 5: 14}.
Teacher command candidates: 444; rejected candidates: 42 (9.5%). Rejection findings (categories can overlap): {'interactive': 4, 'macos_lint': 38, 'unparsed_or_incomplete': 14}.
Abstain reasons: {'teacher_null_majority': 9}.

Dropped rows:
- r00004: no_majority (maximum agreement 2)
- r00007: no_majority (maximum agreement 1)
- r00009: no_majority (maximum agreement 1)
- r00010: no_majority (maximum agreement 1)
- r00011: no_majority (maximum agreement 2)
- r00013: no_majority (maximum agreement 1)
- r00014: no_valid_command (maximum agreement 0)
- r00017: no_majority (maximum agreement 2)
- r00019: no_majority (maximum agreement 1)
- r00020: no_majority (maximum agreement 1)
- r00021: no_majority (maximum agreement 1)
- r00023: no_majority (maximum agreement 1)
- r00024: no_majority (maximum agreement 1)
- r00025: no_valid_command (maximum agreement 0)
- r00029: no_majority (maximum agreement 1)
- r00031: no_majority (maximum agreement 1)
- r00032: no_majority (maximum agreement 2)
- r00034: no_majority (maximum agreement 1)
- r00035: no_majority (maximum agreement 1)
- r00036: no_majority (maximum agreement 1)
- r00039: no_majority (maximum agreement 2)
- r00040: no_majority (maximum agreement 1)
- r00042: no_majority (maximum agreement 2)
- r00043: no_majority (maximum agreement 2)
- r00044: no_majority (maximum agreement 2)
- r00045: no_majority (maximum agreement 2)
- r00046: no_majority (maximum agreement 2)
- r00047: no_majority (maximum agreement 1)
- r00048: no_majority (maximum agreement 1)
- r00049: no_majority (maximum agreement 1)
- r00050: no_valid_command (maximum agreement 0)
- r00054: no_majority (maximum agreement 1)
- r00056: no_majority (maximum agreement 2)
- r00057: no_majority (maximum agreement 1)
- r00058: no_majority (maximum agreement 2)
- r00060: no_majority (maximum agreement 1)
- r00062: no_majority (maximum agreement 1)
- r00065: no_majority (maximum agreement 1)
- r00066: no_majority (maximum agreement 2)
- r00067: no_majority (maximum agreement 2)
- r00068: no_majority (maximum agreement 1)
- r00070: no_majority (maximum agreement 1)
- r00072: no_majority (maximum agreement 1)
- r00075: no_majority (maximum agreement 1)
- r00076: no_majority (maximum agreement 1)
- r00077: no_majority (maximum agreement 2)
- r00078: no_majority (maximum agreement 1)
- r00080: no_majority (maximum agreement 1)
- r00083: no_majority (maximum agreement 1)
- r00084: no_majority (maximum agreement 1)
- r00086: no_majority (maximum agreement 2)
- r00089: no_majority (maximum agreement 2)
- r00090: no_majority (maximum agreement 2)
- r00091: no_majority (maximum agreement 1)
- r00094: no_valid_command (maximum agreement 0)
- r00097: no_majority (maximum agreement 1)
- r00100: no_majority (maximum agreement 1)


Recorded completion tokens: 993617 total, 739.0 median per sample.
Manifest wall time: 6018.8 s for this invocation (100 requests written); throughput: 165.1 tokens/s; per-request latency was not recorded by the sampler.
Manifest metadata: finished=2026-10-12T16:57:17+0300, top-k=0, note='Owner approved JSONDecoder parser fix overriding issue17 no-local-edit rule; teacher prompt unchanged. Default thinking/xhigh on; 4x32768 context; Q8 KV. max_tokens16384 after measured 8k truncation; concurrency4 after 8x32k VRAM OOM. Final-corpus smoke6/6 parsed and stop. Partial-corpus smoke length anomalies retained.'.

Evaluation leakage gate: 24 rows quarantined (excluded from the dataset, never trained on). Hard checks: request word-Jaccard >= 0.7 and normalized command (tool, flags and non-path operands) against dev, everyday and frozen references. The frozen set was used only for this gate.
Report-only overlaps (not gated): request similarity 0.5-0.7 vs dev: 3 rows; request similarity 0.5-0.7 vs everyday: 2 rows; tool+flags vs dev: 6 rows; tool+flags vs everyday: 7 rows; tool+flags vs frozen: 7 rows; tool+flags vs heldout: 11 rows (36 row/split pairs; ids are in the review-hit list below).
- quarantined r00005: author quarantine list: df -t <fstype> is deprecated usage; documented form is -T (one reviewer) frozen/dev
- quarantined r00006: author quarantine list: mdls -all is not an option (both reviewers) frozen/dev
- quarantined r00016: normalized command heldout
- quarantined r00026: normalized command frozen
- quarantined r00028: normalized command heldout
- quarantined r00033: normalized command heldout
- quarantined r00057: author quarantine list: ps keyword thcount does not exist on macOS (both reviewers) frozen/dev
- quarantined r00081: normalized command everyday
- quarantined r00088: normalized command heldout
- quarantined r00177: author quarantine list: paraphrase of a held-out evaluation case frozen/dev
- quarantined r00487: author quarantine list: paraphrase of a held-out evaluation case frozen/dev
- quarantined r00617: author quarantine list: paraphrase of a held-out evaluation case frozen/dev
- quarantined r00849: author quarantine list: paraphrase of a held-out evaluation case frozen/dev
- quarantined r00910: author quarantine list: paraphrase of a held-out evaluation case frozen/dev
- quarantined r01014: author quarantine list: paraphrase of a held-out evaluation case frozen/dev
- quarantined r01179: author quarantine list: paraphrase of a held-out evaluation case frozen/dev
- quarantined r01220: author quarantine list: paraphrase of a held-out evaluation case frozen/dev
- quarantined r01311: author quarantine list: paraphrase of a held-out evaluation case frozen/dev
- quarantined r01402: author quarantine list: paraphrase of a held-out evaluation case frozen/dev
- quarantined r01465: author quarantine list: paraphrase of a held-out evaluation case frozen/dev
- quarantined r01473: author quarantine list: paraphrase of a held-out evaluation case frozen/dev
- quarantined r01979: author quarantine list: paraphrase of a held-out evaluation case frozen/dev
- quarantined r02051: author quarantine list: paraphrase of a held-out evaluation case frozen/dev
- quarantined r02203: author quarantine list: paraphrase of a held-out evaluation case frozen/dev
- r00754: request similarity 0.5-0.7 dev
- r00950: request similarity 0.5-0.7 dev
- r02012: request similarity 0.5-0.7 everyday
- r02222: request similarity 0.5-0.7 dev
- r02426: request similarity 0.5-0.7 everyday

No-command target: empty assistant content. The serving worker returns `unsupported` with no command when upstream generation produces no complete command; the worker-path test covers this behavior. The Mac prompt audit (`docs/distill-prompt-audit.json`) confirmed that an empty target trains its end-of-turn token. A live-model abstention probe remains pending.

Human precision review: **pending**. 26 rows were saved to `/private/tmp/claude-501/-Users-imadeddine-Documents-GitHub-experiments-whatisit-macos/6b4d529c-5987-4b44-94da-36341bc82963/scratchpad/new_sample2.jsonl` with blank human verdicts; no precision estimate is claimed. At least 30 reviewed rows are required for acceptance.
