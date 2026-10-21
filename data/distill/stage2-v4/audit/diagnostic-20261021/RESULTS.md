# Diagnostic blind review — 2026-10-21

**This is diagnostic evidence, not the official pass-2 confirmation sample.** No retained
label was promoted, dropped or edited on the strength of this review. It exists to estimate
how noisy the accepted pass-1 labels are before asking for a rebuild/re-judge decision.

## Method

Three fresh OpenCode subagent sessions judged 60 cases / 159 candidates, each session seeing
only its blind batch and the frozen rubric (`data/distill/stage2-v4/LABEL.md`, SHA-256
`aa533cdf…`). No candidate command was executed. The reviewer is the same model family as
the main judging session (DeepSeek V4.1 Flash Free), so this is model review, not
model-diverse ground truth and not human review.

The samples are purposive, not random:

| Batch | Source | Cases | Candidates |
|---|---|---|---:|---:|
| `d00` | early pass-1 batches `b00`–`b04` | 20 | 39 |
| `d01` | late pass-1 batches `b05`–`b22` | 20 | 54 |
| `d02` | device-dependent, destructive or otherwise suspicious candidates | 20 | 66 |

Files: `inputs/d0*.json` are the blind batches, `verdicts/d0*.json` the returned verdicts,
`director/` the unblinding map and pass-1 values, `scores.json` the machine-readable score.

## Agreement

| | Diagnostic correct | Diagnostic incorrect |
|---|---:|---:|
| **Pass-1 correct** | 127 | 6 |
| **Pass-1 incorrect** | 6 | 20 |

147 / 159 = **92.5%** agreement. Per batch: `d00` 36/39, `d01` 52/54, `d02` 59/66.
Among the 133 pass-1-accepted candidates, 6 were rejected by the diagnostic reviewer
(4.5%); among the 26 pass-1-rejected candidates, 6 were accepted (23.1%). These are
sample-specific rates, not population estimates.

## Disagreements and adjudication

The 12 disagreements were re-checked statically against the stock man pages. Eight are
confirmed, four are probable but depend on a fixture or an undocumented output key.

| Case | Key / command (abridged) | Pass 1 → diag | Resolution | Basis |
|---|---|---|---|---|
| `r00462` | `lsof -p 4200 -a -i -F f \| sed …` | incorrect → correct | **false reject** | `man lsof`: `-F` field output is `<field-id><data>`; `f` is the file-descriptor field. |
| `r00462` | `lsof -p 4200 -a -i -Ff \| sed …` | incorrect → correct | **false reject** | same field-output rule. |
| `r00462` | `lsof -p 4200 -a -i -F f \| awk …` | incorrect → correct | **false reject** | same field-output rule. |
| `r02309` | `lsof -u $(whoami) \| awk '$5=="FIFO"'` | correct → incorrect | **false accept** | `man lsof` TYPE: `PIPE` is a pipe; `FIFO` is a FIFO special file. The request asks for open pipes, not named FIFOs. |
| `r02309` | `lsof -u "$USER" -F \| awk … t=="PIPE"` | incorrect → correct | **false reject** | `man lsof`: `-F` emits `p`/`f`/`t`/`n` field lines; the awk prints them for `PIPE`. |
| `r01481` | `mount -o ro /dev/disk4s1 mountpoint` | correct → incorrect | **false accept** | `man mount`: “There is no default local file system for use with mount. A type must be specified in order to mount a non-NFS filesystem.” |
| `r00400` | `codesign -d --entitlements - … \| grep '<key>…'` | correct → incorrect | **false accept** | `man codesign`: default `--entitlements` output is an abstract representation; `--xml` or `--der` is required. |
| `r00400` | `codesign -d --entitlements - … \| tr -d … \| grep -F …` | correct → incorrect | **false accept** | same; the XML-tag grep cannot match the default output. |
| `r02448` | `osascript … key "signpost" … name` | correct → incorrect | **probable false accept** | The fixture is not in the repo. The command reads only objects under `signpost` and fields named `name`; it does not read `signpostName`. |
| `r02448` | `tr -d '\n' … grep -oE '"(signpost_name|signpost)"'` | correct → incorrect | **probable false accept** | The regex misses camelCase `signpostName`; sibling candidates match `signpost(_name|Name)`. |
| `r02383` | `launchctl list com.example.MyApp \| grep -i LastExitStatus` | incorrect → correct | **probable false reject** | `man launchctl`: `list [label]` prints information about the requested job; the macOS dictionary includes `LastExitStatus` (key not documented in the man page). |
| `r02383` | `launchctl list com.example.MyApp \| grep LastExitStatus` | incorrect → correct | **probable false reject** | same. |

Confirmed: 4 false accepts and 4 false rejects. Probable: 2 false accepts (fixture schema)
and 2 false rejects (`launchctl` output key).

## Impact on the provisional dataset

Two of the disagreements are the **selected target** of a retained label:

- `r02309` — `lsof -u $(whoami) | awk '$5=="FIFO"'` is the selected target. It misses
  anonymous pipes, which are the majority case for “open pipes”. Pass 1 accepted it while
  rejecting the correct `PIPE` variant in the same case.
- `r01481` — `mount -o ro /dev/disk4s1 mountpoint` is the selected target. It fails without
  `-t` on stock macOS.

That is 2 wrong labels in the 40-row human review packet (5%), but the packet deliberately
oversamples risk; it is not a global rate. The other 10 disagreements affect candidates
that were not selected, except that rejecting correct alternatives narrows the candidate
pool and can promote a wrong alternative when `select()` runs (as in `r02309`).

## Limitations

- Same model family as pass 1; agreement is not independent ground truth.
- Purposive samples; no population-wide error rate is claimed.
- The two `signpost` and two `launchctl` resolutions are probable, not verified.
- The review does not replace pass 2 or the human gate, and it cannot make the dataset READY.
