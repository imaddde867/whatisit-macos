#!/bin/bash
set -euo pipefail
adapter_root=/Users/imadeddine/.local/share/whatisit/finetune/runtime-lora-8seed
report_root=docs/runtime-lora-8seed/reports
for arm in A B; do
  for seed in 1 2 3 4 5 6 7 8; do
    name=$arm-s$seed
    run=/tmp/whatisit-8seed-$name
    for attempt in $(seq 1 360); do
      if ssh -o BatchMode=yes core-5090-01 "test -f $run/conversion-check.json"; then break; fi
      sleep 5
    done
    ssh -o BatchMode=yes core-5090-01 "test -f $run/conversion-check.json"
    scp "core-5090-01:$run/adapter-f16.gguf" "$adapter_root/$name.gguf"
    scp "core-5090-01:$run/training-report.json" "$report_root/$name-training.json"
    scp "core-5090-01:$run/conversion-check.json" "$report_root/$name-conversion.json"
    scp "core-5090-01:$run/converter.log" "$report_root/$name-converter.log"
    .venv/bin/python - "$name" <<'PY'
import hashlib,json,sys
from pathlib import Path
name=sys.argv[1]
root=Path('docs/runtime-lora-8seed/reports')
check=json.loads((root/f'{name}-conversion.json').read_text())
assert hashlib.sha256((Path.home()/f'.local/share/whatisit/finetune/runtime-lora-8seed/{name}.gguf').read_bytes()).hexdigest()==check['gguf_sha256']
assert hashlib.sha256((root/f'{name}-training.json').read_bytes()).hexdigest()==check['report_sha256']
report=json.loads((root/f'{name}-training.json').read_text())
if not name.endswith('-s1'):
    first=json.loads((root/f'{name[0]}-s1-training.json').read_text())
    assert report['val_ids']==first['val_ids']
PY
    .venv/bin/python docs/runtime-lora-8seed/reports/eval-driver.py "$name" "$adapter_root/$name.gguf"
  done
done
