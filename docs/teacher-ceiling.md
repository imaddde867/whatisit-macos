# Teacher ceiling on dev + everyday (2026-10-14)

The teacher that produced the stage-2 labels, measured on the same 141
dev (61) + everyday (80) cases under the same protocol that chose the
training labels. Nothing was trained. The question: does the student's
ceiling come from weak labels or from the small model?

## Setup

- Requests `data/teacher/eval-ceiling/dev_everyday_requests.jsonl`
  (141 lines, ids unchanged), SHA-256
  `d346627efe6f7e786f372b37927b4c1d33437ad193d4485afdcaf14aa81c6573`.
- Teacher `Qwen/Qwen3.8-Flash-Next-FP8`, revision
  `236dfdf285828023ca3bcd3f37366c58a3469b13`; vLLM 0.29.0
  (`python-vllm/0.29.0` module, which sets `SIF` to
  `…/vllm_0.29.0_cuda13_roihu.sif`) on Roihu-GPU, 4xGH200, TP4 EP.
  Same serve flags as the corpus run (`tools/roihu_teacher_eval_ceiling.sbatch`,
  a copy of the pilot sbatch whose only change is the request-file path).
- Protocol identical to the label run: `TEACHER_SYSTEM_PROMPT` unchanged
  (SHA-256 `082762b9…`, identical to the corpus manifest), raw request as
  the user message (no `MACOS_PREFIX`), n=5, temperature 0.7, top_p 0.95,
  top_k 0, seeds 1000+i, max_tokens 16384, thinking on. Job 2282039;
  sampling 549.7 s; 705/705 samples parsed and finished `stop` (no
  unparsed, no token-cap hits).
- Scoring on the Mac with `PATH=/usr/bin:/bin:/usr/sbin:/sbin`:
  `tools/score_teacher_eval.py` applies exactly the checks
  `local_recovery_worker.suggest()` runs after generation — reject
  >4,096 chars or NUL/CR/LF, reject `safety.check` DANGER, reject
  `maclint.problems` + `unrequested_deletion` + the `safety.PLACEHOLDER_HINT`
  rule — then labels each case as `tools/eval_fallback.py` does. A null
  command, unparsed output or non-`stop` finish counts as no command.

## Scores (correct = pass + abstain-ok)

| arm | dev | everyday | pooled | accepted wrong | rejected | abstain-missed |
|---|---|---|---|---|---|---|
| teacher (a) majority | 41 | 47 | **88** | 8 | 45 | 0 |
| teacher (b) mean per-sample | 0.757 | 0.905 | **0.841** | — | — | — |
| teacher (c) best-of-5 (oracle) | 50 | 78 | **128** | — | — | — |
| untrained, zero-update f16 | 26 | 42 | 68 | 39 | 30 | 4 |
| student f16, seed 42 | 27 | 54 | 81 | 42 | 16 | 2 |
| stage-2 Q4, seed 42 | 27 | 43 | 70 | 38 | 30 | 3 |

Teacher rejected (45): 41 no command, 3 lint/safety-rejected majority
(`m040` `scutil --nwi`, `m080` `qlmanage …`, `m098` `whence -p python3`),
1 abstention majority on an answerable request (`e055`). Coverage (cases
with a majority at all): 100/141 (87 command majorities, 13 abstention
majorities).

## Teacher × student 2×2 (pooled, teacher-majority correct × f16 correct)

|  | student correct | student wrong |
|---|---|---|
| **teacher correct** | 58 | 30 |
| **teacher wrong** | 23 | 30 |

Against the untrained zero-update f16: TT 51 / TS 37 / ST 17 / SS 36.
Against stage-2 Q4: TT 52 / TS 36 / ST 18 / SS 35.

**Teacher-right / f16-student-wrong: 30 cases.** Five examples, each
with the teacher's majority command and the case reference:

- `e018` "replace every foo with bar in notes.txt…" — teacher
  `sed -i '' 's/foo/bar/g' notes.txt` (the reference verbatim); student wrong.
- `e054` "eject the usb drive called BACKUP" — teacher
  `diskutil eject /Volumes/BACKUP` (the reference); student rejected.
- `e066` "make my mac say build finished out loud" — teacher
  `say "build finished"` (the reference); student rejected.
- `e068` "undo my last commit but keep my changes" — teacher
  `git reset --soft HEAD~1` (the reference); student rejected.
- `e070` "stage everything and commit it with the message fix typo" —
  teacher `git add -A && git commit -m "fix typo"` (the reference);
  student rejected.

## Reference sanity

Every answerable case's `reference` and `also_correct` (129 cases, 352
commands) went through the same lint and accept patterns. No accept
pattern misses a reference. Three references are lint-rejected — harness
issues, not model issues:

- `m040` `scutil --nwi` — maclint: `scutil --nwi: not in man page`
  (the man-page parser misses the documented `--nwi` option)
- `m080` `qlmanage -t -s 256 -o ~/Downloads photo.jpg` — maclint:
  `qlmanage -o: not in man page` (same class; `-o` is documented)
- `e030` `node --version` — `node: not installed on macOS` (not on a
  stock macOS PATH; the reference itself assumes a tool the lint cannot see)

The same three misses reject three teacher majorities (`m040`, `m080`,
`m098`; `m098`'s `whence` is a zsh builtin the PATH-based lint cannot
see — its reference is `command -v python3`). Correcting those harness
artifacts would move the teacher to 91/141; the conclusion below is
unchanged.

## Why the majority loses: vote splitting

All 41 no-command cases are split votes, not teacher ignorance: every
one has ≥2 distinct commands with none reaching 3 (21 cases with 5
distinct commands, 19 with 4, 1 with 3), and 38 of the 41 contain at
least one sample that passes the case's accept pattern. At temperature
0.7 the teacher answers the same intent in 4–5 different surface forms
(flag order, quoting, equivalent tools), and the exact-string majority
protocol — the one that chose the training labels — discards them. The
training builder (`tools/build_distill_dataset.py`) drops exactly these
cases (`no_majority`) and also discards lint-rejected candidates before
voting, so on these 141 cases the label protocol would retain a command
label on 84, an abstention on 13, and drop 44 (31%).

## Interpretation

Teacher-majority 88/141 ≤ ~90, so per the rule fixed in advance: **label
quality caps the student.** The teacher's knowledge is not the bottleneck —
one sample is expected to be correct 84% of the time and best-of-5 reaches
128/141 (91%) — but the majority-of-exact-strings label protocol retains a
correct label on only 62% of cases and produces no label at all on 31% of
them. The student sits 7 points below the teacher majority (81 vs 88), and
its training gain over the untrained baseline (+13: 68→81) decomposes into
+7 cases the teacher majority also gets right (real distillation gain, where
labels exist) and +6 cases where the teacher majority itself failed (split
votes, where no label exists to learn from). The student already beats the
teacher majority on 23 cases. What limits the student on these 141 cases is
the label protocol's coverage and surface-form brittleness, not the 1.5B
capacity: a majority over normalized commands (or a higher agreement threshold
with a canonicalization step) would recover most of the 41 lost cases before
any model change is justified.

## Artifacts

| file | SHA-256 |
|---|---|
| `data/teacher/eval-ceiling/dev_everyday_requests.jsonl` | `d346627e…` |
| `data/teacher/eval-ceiling/raw_samples.jsonl` | `254b4dc6…` |
| `data/teacher/eval-ceiling/manifest.json` | `c47b4790…` |

`probe.log`, the scorer report (`teacher-report.json`) and the f16/zero
label files used for the 2×2 are in `data/teacher/eval-ceiling/`.
Scorer test: `tests/test_score_teacher_eval.py` (16 tests; full suite
68/68). Roihu job 2282039, artifacts under
`/scratch/project_2020845/imadh/whatisit/out/ceiling-dev-everyday/`.

## Not done

- Frozen + held-out are untouched, per protocol.
- No retraining, no prompt or threshold changes; the normalization
  suggestion above is a hypothesis, not a measurement.
