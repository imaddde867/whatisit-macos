# Request corpus

Authored 2026-10-12 for issue #10 by separate GPT-6.1-Sol (high), GPT-6-Astra (high), GPT-6-Sol (xhigh), and the main GPT-6 agent (inherited reasoning). The student model was not used. Batch source fields identify each final row author; reviewer rewrites carry the reviewer source.

Prompt version: the current issue #10 authoring prompt, with category/count assignments and explicit checks for missing inputs, at most two requests per exact intent, generic filenames, and the prescribed style mix. Each batch contains at most 150 authored request-only rows. The scripts use their existing schema and seed unchanged.

Evaluation request fields were used only for corpus avoidance and leakage checking; evaluation references/results were not used to author requests. Frozen is not used for model selection or training.

`requests.jsonl` is assembled from `batches/*.jsonl` using seed 7. The first 100 rows form the stratified pilot, including 9 abstain rows. `manifest.json` records counts, provenance and data hash. `review-sample.md` and `review-sample.jsonl` contain the deterministic 50-row human review sample; **the owner reviewed all 50 and accepted them in this session**. The macOS-specific share is qualitatively consistent with the prompt, rather than claimed as an exactly measured proportion.

Rebuild and check:

```sh
python3 tools/build_corpus.py 'data/corpus/batches/*.jsonl' data/corpus/requests.jsonl
python3 tools/check_corpus.py data/corpus/requests.jsonl
```
