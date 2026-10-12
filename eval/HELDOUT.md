# Held-out evaluation set (`eval/heldout.jsonl`)

150 cases (130 answerable, 20 where the right outcome is no command), authored by Claude Opus 5.5 independently of
the training corpus and the other eval sets, then re-validated: every reference and `also_correct` command matches
an `accept` pattern, every `wrong_example` matches none, and max word-Jaccard vs dev/everyday/frozen/corpus is 0.444.
About 74 references were executed on macOS 27 against scratch fixtures; the rest were checked against man pages.

**Rule:** this is the decision-gate set for the distilled model (#11). It is never tuned on and never used for prompt
or lint work. Candidates are scored once. `tools/build_distill_dataset.py` includes it in the leakage gate, so training
rows whose request or normalized command overlaps it are quarantined.

Baseline (default 1.5B, scored once on 2026-10-12):

| harness | pass | wrong | rejected | abstain-ok | abstain-missed | correct |
|---|---|---|---|---|---|---|
| model only | 56 | 72 | 2 | 0 | 20 | 56/150 |
| lint + guard | 51 | 54 | 25 | 9 | 11 | 60/150 |

Known caveats: ~10 cases share an intent with a corpus request (covered by the command gate); h025 and h075 are
arguable abstains; h021, h059 and h011 have lenient accepts. Scripted `zsh -c` runs of `log show` references fail
because `log` is a zsh builtin there (interactive Terminal is fine).
