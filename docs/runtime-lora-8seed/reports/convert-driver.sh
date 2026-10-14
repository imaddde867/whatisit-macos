#!/bin/bash
set -euo pipefail
for arm in A B; do
  for seed in 1 2 3 4 5 6 7 8; do
    run=/tmp/whatisit-8seed-$arm-s$seed
    while [ ! -f "$run/training-report.json" ]; do
      kill -0 985740
      sleep 5
    done
    /tmp/whatisit-cuda-venv/bin/python /tmp/whatisit-lora-converter-b11565/convert_lora_to_gguf.py "$run/adapter" --base /tmp/whatisit-teacher/student-metadata --outtype f16 --outfile "$run/adapter-f16.gguf" > "$run/converter.log" 2>&1
    /tmp/whatisit-cuda-venv/bin/python - "$run" <<'PY'
import hashlib,json,sys
from pathlib import Path
from gguf import GGUFReader
run=Path(sys.argv[1])
r=GGUFReader(str(run/'adapter-f16.gguf'))
assert r.fields['adapter.lora.alpha'].contents()==160
assert len(r.tensors)==224
for t in r.tensors:
    assert t.tensor_type.name=='F16'
    assert (t.shape[1] if t.name.endswith('.lora_a') else t.shape[0])==8
report=json.loads((run/'training-report.json').read_text())
assert report['train_rows']==report['steps']==(1092 if '-A-' in str(run) else 936)
assert report['data_sha256']==('c8f9661db1cadf79d81c58f0fd8f0628ad3461c61c0a5f97c6b20f195ec06550' if '-A-' in str(run) else 'e083bd4d1da30b9ed91d65236d08d19dbf0c7260fe3daeecc82d363a0c4f85f5')
assert report['source_sha256']=='6f8a17a11129a31074c944f4c2602453fafd9de43bdaeb1630a8f511ec820f71'
assert report['adapter_sha256']=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (run/'adapter').iterdir() if p.is_file()}
checks={'gguf_sha256':hashlib.sha256((run/'adapter-f16.gguf').read_bytes()).hexdigest(), 'alpha':160,'rank':8,'scale':20,'tensor_count':224,'tensor_type':'F16', 'report_sha256':hashlib.sha256((run/'training-report.json').read_bytes()).hexdigest()}
(run/'conversion-check.json').write_text(json.dumps(checks,indent=2)+'\n')
print(run.name,checks,flush=True)
PY
  done
done
