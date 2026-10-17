#!/bin/bash
set -euo pipefail
cd /tmp/whatisit-8seed-code
for arm in A B; do
  if [ "$arm" = A ]; then data=data/distill/stage2-v3/train.jsonl; steps=1092; else data=data/distill/stage2-v3-abstain8/train.jsonl; steps=936; fi
  for seed in 1 2 3 4 5 6 7 8; do
    output=/tmp/whatisit-8seed-$arm-s$seed
    test ! -e "$output"
    echo "START $arm $seed $(date -u +%FT%TZ)"
    PYTHONPATH=src /tmp/whatisit-cuda-venv/bin/python tools/train_distill_cuda.py /tmp/whatisit-teacher/nl2sh-1.5b-Q4_K_M.gguf /tmp/whatisit-teacher/student-metadata "$data" "$output" --steps "$steps" --lr 1e-5 --seed "$seed" --val-fraction 0.05 > "$output.log" 2>&1
    echo "DONE $arm $seed $(date -u +%FT%TZ)"
  done
done
