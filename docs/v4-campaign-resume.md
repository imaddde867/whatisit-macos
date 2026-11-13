# v4 campaign — continue on the Mac

**Status: BLOCKED.** The four active pass-1 verdicts (`b00`–`b03`) are schema-valid and
control-matching, but they have no pass-1 receipts and their judge sessions are not in the
Linux session store. Do not build, train on, or cite them until this guide's step 1 passes.
Nineteen batches (`b04`–`b22`) still have no verdict.

- Branch: `campaign/v4-verified-rebuild-20261022`
- Audit: `data/distill/stage2-v4/campaign-20261022/audit/provenance-20261113/report.json`
- Protocol: `data/distill/stage2-v4/judge/protocol.md`
- Rubric: `data/distill/stage2-v4/LABEL.md`

## What changed on the Linux side

`tools/make_v4_receipt.py` was rebuilt to audit a judge session fail-closed: tokenized shell
allowlisting, an exact per-batch read allowlist, audited `grep`/`glob`, visible
`execute`/`webfetch`/`websearch`/`subagent`, cross-batch and superseded/calibration session
reuse detection, and pool-manifest binding. 16 focused tests and the full 276-test suite pass.

The audit found: all 23 pool batch artifacts, the keymap, controls map, director map, inputs
and tooling digests match; 63 controls (25 correct / 38 incorrect) are mapped with full
per-batch coverage; `b00`–`b03` pass the validator. But the local store contains only the
2026-11-13 audit sessions, so the 2026-10-23 judge sessions cannot be located here.

## 0. Pull the branch

```sh
cd /path/to/whatisit-macos
git status --short                 # must be clean; stash or commit local work first
git fetch origin
git checkout campaign/v4-verified-rebuild-20261022
git pull --ff-only origin campaign/v4-verified-rebuild-20261022
```

Use the campaign's own Python (the one that built the pool), not a different interpreter:

```sh
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
export PYTHONPATH=src:tools
python3 --version                  # expect 3.12.x
whatisit --version                 # expect 0.4.0
ls -l ~/.local/share/opencode/opencode.db
CAMPAIGN=data/distill/stage2-v4/campaign-20261022
```

## 1. Reconstruct the four round-2 receipts (blocking)

The tool only reads the session database and writes `receipts/pass1/<batch>/receipt.json`.
For each batch, first locate the real session:

```sh
python3 tools/make_v4_receipt.py find --campaign "$CAMPAIGN" --batch b00
```

Pick the session whose `created` is on **2026-10-23** and whose `matches` include
`p1-20261023-b00-a1` and the batch file. Then write the receipt for that session id:

```sh
python3 tools/make_v4_receipt.py receipt \
  --campaign "$CAMPAIGN" --batch b00 --session ses_REPLACE_ME
```

Exit code `0` and `"result": true` are required:

```sh
python3 -c "import json; print(json.load(open('$CAMPAIGN/receipts/pass1/b00/receipt.json'))['result'])"
```

Repeat for `b01`, `b02`, `b03`.

**If `find` returns only the 2026-11-13 sessions** (titles `Initial context exploration`,
`Review v4 receipt tool`) or nothing, the Mac store does not have the judge sessions either.
Stop and re-judge `b00`–`b03` with fresh sessions using step 2, then receipt them. Never
hand-write a receipt and never reuse a round-1 receipt: those bind different prompt and
verdict digests.

## 2. Judge the remaining 19 batches (`b04`–`b22`)

For each batch, start one **fresh** judge session that can read only
`data/distill/stage2-v4/LABEL.md` and `$CAMPAIGN/pool/batches/<batch>.json`. Use
`PASS1-PROMPT.md` with the placeholders substituted (`{batch_path}`, `{verdict_path}`,
`{batch}`, `{judge_label}`). Use a unique label per batch — `p1-YYYYMMDD-bNN-a1` with the
actual judging date is fine — and write the verdict to `$CAMPAIGN/verdicts/<batch>.json`.
The judge must never execute a candidate command.

Validate every batch (stops on the first failure):

```sh
for n in $(seq -w 4 22); do
  b="b$n"
  echo "== $b"
  python3 "$CAMPAIGN/validate_verdict.py" \
    "$CAMPAIGN/pool/batches/$b.json" \
    "$CAMPAIGN/verdicts/$b.json" \
    "$CAMPAIGN/pool/controls-map.json" || break
done
```

Then reconstruct the receipt for each new batch exactly as in step 1 and require
`result: true`.

## 3. Confirm (independent 20%) and pass 2

After **all** 23 verdicts pass:

```sh
PYTHONPATH=src:tools python3 tools/make_v4_confirm.py \
  "$CAMPAIGN/pool/keymap.json" \
  data/teacher/roihu_full_raw_samples.jsonl \
  data/distill/stage2-v3/requests.jsonl \
  "$CAMPAIGN/verdicts" \
  "$CAMPAIGN/confirm" --sample 0.2 --seed 13 --batch-size 90
```

`$CAMPAIGN/confirm` must not exist yet. The command prints the manifest; `sampled` is the
number of labels to confirm.

Each confirm batch goes to a **fresh** session that never judged those cases in pass 1. Use
the same rubric and blindness, write to `$CAMPAIGN/confirm-verdicts/<batch>.json`, and use a
`p2-...` judge identity. A confirm verdict that is not `correct` drops that label; do not
replace it.

## 4. Build the verified dataset

Pick a fresh output directory; the builder refuses a non-empty one:

```sh
OUT="data/distill/stage2-v4/verified-$(date +%Y%m%d)"
test ! -e "$OUT" || { echo "choose another output dir"; exit 1; }

PYTHONPATH=src:tools python3 tools/build_verified_dataset.py \
  "$CAMPAIGN/pool/keymap.json" \
  "$CAMPAIGN/verdicts" \
  "$CAMPAIGN/confirm" \
  "$CAMPAIGN/confirm-verdicts" \
  "$OUT" \
  --controls "$CAMPAIGN/controls.jsonl"
```

The `--controls` flag is required: the builder defaults to the 65-control
`judge/controls.jsonl`, while this campaign's pool uses the corrected 63-control set.

## 5. Human review and release gate

The builder is model review only. Before any READY claim:

1. A human reviews at least 30 **retained** examples from `$OUT/train.jsonl` (request and
   target) against `LABEL.md`, and records the reviewed ids and decisions in a signed packet.
2. Update the campaign status to `READY` only when every gate in `config.json` passes and the
   human packet is signed off. Otherwise leave it `BLOCKED` / human-review-pending.
3. Only then run the untouched frozen/held-out release gate (issue #11) and decide
   KEEP or SHELVE.

## Guardrails

- Never execute a candidate command or any part of it.
- Do not tune on `eval/dev.jsonl`, `eval/everyday.jsonl`, `eval/frozen.jsonl` or
  `eval/heldout.jsonl`; leakage gates are fail-closed.
- Every injected control must match its expected value before a batch counts.
- Never reuse a pass-1 session for pass 2, and never edit a verdict in place.
- `superseded/` and `receipts-pass1-20261022-a1/` are historical; do not use them as current.
- A receipt with `result: false` is a finding, not a formality.

## Commit points

After step 1:

```sh
git add "$CAMPAIGN/receipts" "$CAMPAIGN/config.json"
git commit -m "data(v4): record pass-1 receipts for b00-b03"
git push origin campaign/v4-verified-rebuild-20261022
```

After step 2 and after step 4, commit `verdicts/`, `confirm/`, `confirm-verdicts/` and the
built output separately so each gate is reviewable.
