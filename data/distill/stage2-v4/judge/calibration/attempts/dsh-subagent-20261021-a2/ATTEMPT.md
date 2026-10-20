# Calibration attempt 1 — DSH subagent judge (2026-10-21)

**Result: FAILED — do not use as the campaign judge. No `b05` attempt was consumed.**

The campaign still stands at the retry-budget stop. This attempt cost nothing from the
campaign budget because it ran only against the frozen calibration set.

## Judge and isolation

- Judge: three fresh DSH subagent sessions (`dsh-judge-cal-controls-a2`,
  `dsh-judge-a0-a2`, `dsh-judge-a1-a2`), one per calibration batch.
- Each session received only `LABEL.md` and its batch file (copied outside the repository);
  it had no repository path, no key file, no controls map and no accepted verdicts.
- Tool boundary: `man -P cat <tool> | col -b` and existence checks under
  `/usr/bin`, `/bin`, `/usr/sbin`, `/sbin`; no candidate was executed.
- Verdict files and the score report are in this directory.

## Score against the frozen bar

| Metric | Required | Observed | |
|---|---|---|---|
| Spent controls correct | 13 / 13 | **10 / 13** | fail |
| Accepted verdicts reproduced | ≥ 101 / 112 | 101 / 112 | at the bar |
| False accepts (accepted-incorrect → correct) | ≤ 2 / 35 | **8 / 35** | fail |
| Unsure | ≤ 2 | 0 | pass |

Control mismatches, all "close but not exact" commands judged `correct`:

- `ct0015` — `mkdir photos && find . -type f -name '*.jpg' -exec mv {} photos/ \;`
  for "put all the jpgs in this folder into a new folder called photos": recurses instead
  of staying in this folder.
- `ct0019` — `ps -axo comm= | grep python` for "list my running python processes".
- `ct0007` — `find /Applications -type d -name '*Chrome*'` for "list apps in /Applications
  with chrome in the name": lists directories, not apps.

## Failure pattern

The judge verifies documented flags but does not check that the command does exactly what
the request asks:

- field vs substring (`grep -c '"level":"warning"'` rejects valid JSON whitespace;
  UUID extraction counts UUID-shaped substrings rather than UUID fields);
- wrong tool semantics (`log stream` accepted for "assertion history" because `--timeout`
  exists; the request needs `pmset assertionslog`);
- non-stock tool accepted (`python3 -c` for a JSON extraction request);
- non-existent field label accepted (`diskutil … '/Read-Only Media/'`; the label is
  `Media Read-Only`, so the pipeline prints nothing).

It also rejected three accepted-correct commands; two of those rejections are defensible
(`awk` counts blank lines as zeros; `du` without `-type d` lists files), one is not
(`grep -qE 'Read-Only:...'`).

This is the same permissive pattern that failed the two Strata `b05` attempts. A judge of
this kind would likely pass some live control batches and silently inflate labels, which is
worse than failing the gate.

## Disposition

- Rejected. The calibration set and its bar were not edited.
- The campaign judge remains unqualified; no pass-1 batch was re-judged, no confirm was
  produced, no dataset was built.
- Next judge must clear all 13 spent controls and the false-accept cap before `b05`.
