import json
from pathlib import Path
from build_distill_dataset import _parts,read_jsonl
covered={}
for version in ('v2','v3'):
 covered[version]={(tool,flags) for row in read_jsonl(Path(f'data/distill/stage2-{version}/train.jsonl')) if row['messages'][-1]['content'] for tool,flags,_ in _parts(row['messages'][-1]['content'])}
cases={r['id']:r for split in ('dev','everyday') for r in read_jsonl(Path('eval')/(split+'.jsonl'))}
buckets={}
for rid,row in cases.items():
 if row['accept'] is None:
  buckets[rid]='abstention';continue
 signatures={(tool,flags) for tool,flags,_ in _parts(row['reference'])}
 if not signatures:
  buckets[rid]='trivial_reference';continue
 c2,c3=[signatures<=covered[v] for v in ('v2','v3')]
 buckets[rid]='both' if c2 and c3 else 'new_in_v3' if c3 else 'v2_only' if c2 else 'neither'
report={'definition':'all non-trivial reference stages have an exact tool/subcommand + sorted flag-set signature in at least one training command; operands ignored for coverage only','signature_counts':{v:len(c) for v,c in covered.items()},'per_case':buckets,'counts':{k:list(buckets.values()).count(k) for k in sorted(set(buckets.values()))}}
assert sum(report['counts'].values())==141
Path('/tmp/whatisit-v3-screen/coverage.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
print(json.dumps(report['counts']))
