import json
from pathlib import Path
from build_distill_dataset import _parts,read_jsonl
from train_distill_cuda import split_validation
sets={'corpus':{},'training':{}}
for version in ('v2','v3'):
 rows=read_jsonl(Path(f'data/distill/stage2-{version}/train.jsonl'))
 train,val=split_validation(rows,.05)
 report=Path('docs/stage2-training-reports/lr1e-5-s42.json') if version=='v2' else Path('docs/v3-training-reports/seed42.json')
 saved=json.loads(report.read_text())
 assert [rows[i]['id'] for i in val]==saved['val_ids']
 for mode,indices in [('corpus',range(len(rows))),('training',train)]:
  sets[mode][version]={(tool,flags) for i in indices if rows[i]['messages'][-1]['content'] for tool,flags,_ in _parts(rows[i]['messages'][-1]['content'])}
cases={r['id']:r for split in ('dev','everyday') for r in read_jsonl(Path('eval')/(split+'.jsonl'))}
reports={}
for mode,covered in sets.items():
 buckets={}
 for rid,row in cases.items():
  if row['accept'] is None:
   buckets[rid]='abstention';continue
  signatures={(tool,flags) for tool,flags,_ in _parts(row['reference'])}
  if not signatures:
   buckets[rid]='trivial_reference';continue
  c2,c3=[signatures<=covered[v] for v in ('v2','v3')]
  buckets[rid]='both' if c2 and c3 else 'new_in_v3' if c3 else 'v2_only' if c2 else 'neither'
 reports[mode]={'definition':mode+' rows; all non-trivial reference stages have an exact tool/subcommand + sorted flag-set signature in at least one training command; operands ignored for coverage only',
                'signature_counts':{v:len(c) for v,c in covered.items()},
                'new_v3_signatures':len(covered['v3']-covered['v2']),
                'per_case':buckets,'counts':{k:list(buckets.values()).count(k) for k in sorted(set(buckets.values()))}}
 assert sum(reports[mode]['counts'].values())==141
report={**reports['training'],'corpus_coverage':reports['corpus']}
Path('/tmp/whatisit-v3-screen/coverage.json').write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
print(json.dumps({mode:r['counts'] for mode,r in reports.items()}))
