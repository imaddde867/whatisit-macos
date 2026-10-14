# Data v3 re-label protocol (pre-registered)

This protocol and voting code are committed before rebuilding the 2,520-request
Roihu corpus. No development scores inform the rule, review, or training settings.
No new teacher samples. Frozen/heldout are consumed only by the existing leakage
gate; the final evaluation gate is never run.

Voting uses only samples passing the unchanged parsed/stop, command-schema,
interactive, DANGER, macOS lint, deletion and placeholder filters. Three of five
valid commands must share a key. Three nulls still abstain. Author-abstain requests
with a command majority are excluded and listed for model review.

The key uses `_segments`, the `_parts` tool/subcommand convention, and `_flags`.
It retains every stage in order, sorted flags, and a canonical multiset of all
operands, including numbers and paths. Quoting is tokenized with shlex; filesystem
operands may lose leading `./`, directory trailing `/`, and leading `$HOME/`
becomes `~/`. Program/pattern operands and shell-glue literals are not paths.
Only the finite long-value options in `LONG_VALUES` combine `--option=value` and
`--option value`. Unknown arity is never inferred from real corpus results.

Conservative guards retain operand order and option/value association in addition
to the required multiset: otherwise `cp a b` could merge with `cp b a`, or values
could migrate between flags. Unknown short-option positions remain significant.
Wrappers, executable paths, redirections, non-pipeline control operators, quoted
expansion-sensitive tokens, malformed syntax and conflicting output/sort flags
use singleton exact keys. No key is empty. These guards may miss valid merges;
they prevent meaning-changing merges. No normalized/signature leakage key votes.

Any exact-string majority wins unchanged. Otherwise choose the most frequent
exact string in the winning cluster, then shortest, then lexicographic. Provenance
records mode, cluster votes and its distinct exact strings. The repair step keeps
the pinned original targets, reviewed amendments, 36 authored additions, explicit
paths, source families, historical quarantines and unchanged leakage checks.

Hypothesis: a large share of the historical 1,207 no-majority requests is recovered.
Fewer than approximately 150 or more than approximately 1,000 recovered requests
triggers a stop to investigate the key; this is a diagnostic, not a target.

Read every multi-string recovered cluster in a merge audit. Meaning differences
require a tested key correction and a documented deviation, then a fresh rebuild.
Draw 60 recovered command rows across categories using proportional strata,
largest-remainder allocation, sorted category/id inputs and `random.Random(314159)`.
This is **model review**, never human review. Judge stock-macOS request correctness,
real flags (local man pages), and safety as OK/debatable/wrong. Conservative precision
counts only OK; report Wilson 95% interval. More than 9 non-OK rows stops training.
Generated commands are never run against user data; optional execution is restricted
to read-only commands with fixtures in a temporary directory and stock PATH.

Every artifact is hashed in a manifest (the manifest itself via an external checksum
file). Fresh-directory builds must be byte-identical; outputs cannot be overwritten.
Verify every historical label by bytes, grouped validation and pinned-tokenizer
prefix/end-of-turn/512-token checks before freezing or publishing.

If data passes, train unchanged one-epoch stage-2 settings with seeds 42 and 43;
nominate seed 42 now. Save the unmerged adapter. Quantize with b11565 on the 5090.
Screen only dev/everyday, pinned stock PATH, after default-label identity sanity.
Per precision, both seeds must improve pooled correctness without split regression,
accepted-wrong increase or abstain-missed increase. Attribution requires both Q8
seeds at least v2 seed42 +3 pooled and paired wins exceeding losses. Report coverage,
teacher-right/student-wrong fixes, latency and Q6 RSS against default +64 MiB.
No shipped-model or serving changes. Draft PR only; never merge.

Deviations after the first diagnostic rebuild (no development scores inspected):

- The initial guard recovered only 36 rows with a stock PATH. Investigation found
  that rejecting every quoted dollar/backslash also rejected literal awk/sed
  programs. The corrected lexer aligns shlex word values with quote-preserving
  tokens and retains expansion profiles, control separators and redirection
  operands. It merges literal quoting safely while distinguishing quoted/unquoted
  variables and globs. Unknown escaped shell syntax still uses exact keys.
- A multiset-only diagnostic found just 136 candidates even before serving filters.
  The large-recovery hypothesis was overoptimistic for these samples; programs,
  tools, flags and output formats often differ rather than just quoting. We do not
  weaken semantic guards to reach 150. Investigation resolves the low-count alarm;
  proceeding still requires at least 60 recovered commands and the review gate.
- Stock PATH belongs to final screening, not historical data reproduction. The
  stock-path rebuild omitted four pre-existing Homebrew/npm labels. Exact-mode
  rebuilding uses the original ambient PATH; no filters or lint code change.
- "Now get a command majority" means newly recovered author-abstain conflicts.
  Historical exact-majority targets remain unchanged so the pinned amendments
  (including reviewed corrections to abstention) remain valid. New author-abstain
  command clusters are excluded and listed for model review.
- Local `man cp` confirms that a trailing source-directory slash changes recursive
  copying semantics, so cp/rsync operands retain it. Executable paths are retained
  in full (their quoting may vary, their identity may not). Known short-option
  value bindings, from local man pages, allow bundled flags and option reordering
  without moving values between flags. Ordered find expressions/actions and repeated
  ps output-column options remain exact; repeated ps `-w` counts remain significant.
- Merge inspection found a real key bug in r01802: zip exclusion patterns ending
  in `/` were treated as filesystem directory operands. Zip operands now retain
  their exact token values, so `project/build` and `project/build/` cannot merge.
  A focused negative regression test covers it. Fresh artifacts replace the
  diagnostic build; no training or development scoring has occurred.
- Further negative tests restrict path normalization to known filesystem operand
  positions. Service names, sysctl keys, zip patterns, inline programs and format
  strings remain literal. Unknown flags retain their original positions, while
  the finite value/no-value tables permit only documented option reordering.
  Bracket/brace/glob expansion, repeated value options and incompatible modes
  are guarded. These are parser correctness fixes, not score-based rule selection.
- Independent **model code review** found quote-sensitive redirections, path-root
  normalization and additional last-wins flags not covered by the first guards.
  Quoted redirection tokens are now exact, `./` becomes `.` (never empty), `.//x`
  remains relative, and documented ls/find/du/date/cp order-sensitive combinations
  remain exact. Unbound operands retain trailing slashes because the key cannot
  prove directory type or symlink resolution without accessing real user data.
  Only directory-typed `-onlyin` and git `-C` values retain slash canonicalization.
  The model code review also required pinning the full sampled targets and input
  hashes before accepting verdicts. All fixes have negative regression tests.
  The initial 64-row release commit is diagnostic/superseded and was never uploaded
  or trained. New fresh-directory results and the same seeded 60-row review replace it.
- Expansion profiles retain character positions and embedded shell operators.
  Mixed quoted/unquoted variable names use singleton keys because quote boundaries
  can change the expanded variable name. HOME aliases assume stock zsh defaults
  (SH_WORD_SPLIT and GLOB_SUBST disabled), as required by the product contract.
- Final model code review identified stock-zsh EQUALS expansion: unquoted `=ls`
  resolves an executable, while quoted `'=ls'` is a literal filename. Leading
  unquoted `=` now uses exact keys. A failing negative test preceded the fix.
  The full corpus is rebuilt to verify whether this affects any frozen label;
  any label change requires repeating the data review and training.
  Fresh full-corpus base/repair and full-package reproduction subsequently found
  zero changed labels, requests, audit records or clusters. Existing reviews and
  training runs remain valid; immutable original generator snapshots stay pinned.
- A final man-page check found the preregistered positive `ls --color=always`
  versus `ls --color always` test was wrong: optional long-option arguments need
  `=`, and the second token can be a file/revision operand. Git pretty/format
  options also have last-wins interactions. Required-value equivalence is now
  limited to per-tool documented grep/curl options; unknown inline long options
  retain their original positions. Four failing negative tests preceded the fix.
  This is a semantic parsing correction, independent of development scores.
- Relative-path normalization must preserve operand roles: `./-` is a file,
  while `-` can mean stdin; a timed bare executable is searched on PATH; Git
  pathspec magic is not a plain pathname. Pathname-producing stages feeding a
  pipeline or redirected output retain their lexical path prefixes, since a
  later pattern can observe them. Focused failing tests cover all four cases.
  These guards preserve the frozen labels; full-package reproduction is checked
  again before the result is finalized. No score-based rule selection occurs.
