# Learning64 diagnostic (frozen before generation)

This is a controlled learning diagnostic, not a deployment benchmark or a model-capacity test. No frozen/held-out evaluation file is used. All tasks are authored independently around stock macOS command semantics and synthetic scratch files. Every target is a command; there are no empty targets.

The package has 64 training rows (16 task families, four examples per family), 64 identical-request fit cases, 64 new phrasings of those requests, 64 unseen operand cases, and 16 new compositions. The training system prompt and macOS prefix are copied from the existing serving-format dataset. Evaluation messages contain the identical system prompt and prefix. Training receives only `train.jsonl`; all diagnostic case files stay on the evaluation host.

Before any model generation, run every reference against its supplied synthetic fixture on macOS with stock PATH and zsh. Assert the expected stdout/file state, record platform and results, and stop if any reference fails. This verifies the labels rather than assuming a plausible command is correct. Commands with metadata-dependent stdout have a declared check. Generated commands are not automatically executed: inspect them or restrict execution to the scratch fixture after review.

Freeze the SHA-256 manifest after reference verification and independent review, before inference or training. Any data correction before freeze must be documented. After freeze, do not silently change examples, acceptance, training configuration or thresholds based on outputs.

Compare the shipped base with the new runtime LoRA on all four evaluation groups. If practical, include one previously preserved runtime adapter as a separately named comparator. Never merge/requantize the new adapter for the primary comparison. Use the same Mac server build, stock PATH, greedy decoding and context as the prior experiment. Preserve the full HTTP request/response, raw assistant text, finish reason, exact command, and post-generation lint outcome for each case; distinguish generated empty output from parsing or lint rejection.

One predeclared training run: original pinned NL2SH GGUF; rank8, alpha160, last16 layers, all seven projection modules; AdamW learning rate1e-5, batch1, seed42, 1024 optimizer steps, validation fraction0. This is 16 complete exposures to 64 rows. Preserve the unmerged adapter. No diagnostic evaluation row enters training or checkpoint selection. If a checkpoint is recorded after 64 steps, it is descriptive only; the 1024-step result remains primary. No automatic extra run if the result disappoints.

Score exact/allowlisted command matches separately from semantic correctness. `accept` contains anchored whole-command patterns for known variants. A miss is `needs_review`, not established incorrectness. A reviewer uses `semantic_criterion`, literal operands and fixture behavior, and rejects extra effects or lost information. Do not normalize whitespace inside quoted arguments. Report raw and post-lint correctness separately, plus unresolved review counts. The finite allowlist is deliberately not a semantic equivalence engine.

Operational interpretation, fixed in advance:

- At least61/64 semantically correct original fit cases (95.3%) means this run fits this small command set. If the base already reaches that level, report that this set cannot establish a fine-tuning fit benefit.
- If fit is below61/64, inspect the concrete residual fit errors and raw teacher-forced command losses before blaming generalization or model capacity. An optimization, format or supervision problem remains possible; one failed recipe cannot establish a capacity limit.
- Compare each paraphrase and operand case with its paired fit case. At least seven additional errors in a 64-case group is a descriptive gap exceeding10 percentage points. Report paired gains/losses and a paired interval; this threshold is a diagnostic flag, not a significance test.
- Report compositions as a separate16-case set with exact numerator/denominator. These are a harder held-out construction, not equivalent in difficulty to paraphrases. A composition miss should identify which operation, operand or dependency failed.

The set favors controlled, reproducible semantics over breadth. It does not cover abstention, arbitrary user data, interactive commands, dangerous operations or all macOS tools. High scores therefore do not authorize shipping.
