import hashlib
import importlib.metadata
import json
from pathlib import Path
from transformers import AutoTokenizer
from train_distill_cuda import chat_tokens
root = Path('data/distill/stage2-v3')
snapshot = Path.home() / '.cache/huggingface/hub/models--Qwen--Qwen2.5-Coder-1.5B-Instruct/snapshots/2e1fd397ee46e1388853d2af2c993145b0f1098a'
rows = [json.loads(line) for line in (root / 'train.jsonl').read_text().splitlines()]
tokenizer = AutoTokenizer.from_pretrained(snapshot, local_files_only=True)
lengths = []
for row in rows:
    tokens, labels = chat_tokens(row, tokenizer, rows[0]['messages'][0]['content'])
    assert len(tokens) == len(labels) <= 512
    lengths.append(len(tokens))
report = {'rows': len(rows), 'max_tokens': max(lengths), 'all_prefix_end_of_turn_and_512_checks_passed': True,
          'model': 'Qwen/Qwen2.5-Coder-1.5B-Instruct', 'revision': snapshot.name,
          'transformers': importlib.metadata.version('transformers'),
          'train_sha256': hashlib.sha256((root / 'train.jsonl').read_bytes()).hexdigest(),
          'tokenizer_files_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(snapshot.iterdir()) if p.is_file()},
          'chat_tokens_script_sha256': hashlib.sha256(Path('tools/train_distill_cuda.py').read_bytes()).hexdigest()}
assert report['rows'] == json.loads((root / 'manifest.json').read_text())['rows']
assert report['transformers'] == '4.57.1'
(root / 'tokenizer-preflight.json').write_text(json.dumps(report, sort_keys=True, indent=2) + '\n')
print(json.dumps(report, sort_keys=True))
