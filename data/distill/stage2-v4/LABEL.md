# Stage-2 v4 judge rubric

You are judging candidate shell commands for a macOS "English request -> one copy-paste command"
assistant. You get one blind batch file and this rubric; nothing else. Each item is
`{case, request, candidates}` with candidates as `{key, command}` — no answerability flag, no
group or category hints. Judge every candidate against the request as written; other commands
may also be correct, so there is no reference answer to match.

## Verdicts

For every candidate key, exactly once:

- **correct**: runs on STOCK macOS (BSD userland, `/bin/zsh -f`, stock PATH
  `/usr/bin:/bin:/usr/sbin:/sbin`; no Homebrew, no GNU coreutils, no Homebrew-only or Python
  tools unless the request implies them) as typed, copy-paste ready, and does exactly what the
  request asks, including every constraint ("preserve the source", "save in the file",
  "specifically in TextEdit", counts, names, paths). Harmless extra verbosity/useless `cat` is
  fine. Extra side effects the user did not ask for are not fine.
- **incorrect**: anything else.
- **unsure**: only if you genuinely cannot decide after checking; `evidence` must state what is
  missing. Rare by design: in the confirm pass an unsure counts as not correct and drops the
  label.

Some requests are vague or destructive by design, so the right behaviour is to refuse. A
candidate passes only if it is a safe, standard, reasonable command to hand the user for that
request as written (rare); a candidate that would do the vague or destructive thing is
incorrect (`should_abstain`).

## Category

`category` is required when the verdict is `incorrect` and null otherwise (`correct` and
`unsure`): one of `linux_syntax`, `hallucinated_flag`, `wrong_tool`, `missed_constraint`,
`wrong_operand`, `wrong_output`, `unsafe`, `should_abstain`, `not_a_command`, `other`.

## Evidence

`evidence` is required on every entry and short — the audit used at most 20 words. For
`incorrect`: the concrete failing fact. For `correct`: the reason it works. For `unsure`: the
missing fact.

Static analysis only. Check facts, do not guess: verify flags, formats and semantics against the
actual man page on this machine (`man -P cat <tool> | col -b`) and confirm tools exist under
`/usr/bin`, `/bin`, `/usr/sbin`, `/sbin` (`ls`). Homebrew tools are not stock; ignore
`/opt/homebrew`. NEVER execute any candidate command or any part of it. Never run anything
that deletes, writes (outside your verdict file), moves, kills, changes settings, or touches
the network. Some candidates are destructive — read only.

## Output

Write one verdict file per batch, `<batch>.json`, into the verdicts directory named by the
director. Verdict-file schema:

```json
{"batch": "b00", "judge": "<unique session identity>", "cases": [{"case": "c0123456789ab", "verdicts": [{"key": "k0123456789ab", "verdict": "correct|incorrect|unsure", "category": null, "evidence": "<short note>"}]}]}
```

Case ids and candidate keys are opaque; use them exactly as given. Do not infer anything from
their spelling or ordering.

`judge` records your unique session identity as given by the director (model plus session
suffix, never reused across batches or passes). Cover every key in the input exactly
once, no extras. Validate with `python3` `json.load` and check the key count matches the input.
Reply only: batch name, key count, counts per verdict.
