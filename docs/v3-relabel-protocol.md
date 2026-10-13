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

Deviations: none at registration.
