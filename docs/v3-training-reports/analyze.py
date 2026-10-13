import hashlib,json,re
from collections import Counter
from pathlib import Path
root=Path('/tmp/whatisit-v3-screen');out=Path('docs/v3-training-reports')
correct={'pass','abstain-ok'};valid=correct|{'wrong','rejected','abstain-missed'}
precisions=('Q8_0','Q6_K','Q4_K_M')
stage2=json.loads(Path('docs/stage2-arm-labels.json').read_text())['arms']
arms={'default':{s:json.loads((root/f'default-{s}.json').read_text()) for s in ('dev','everyday')}}
assert arms['default']==stage2['default']
baselines={}
for precision in precisions:
 baselines[precision]={s:(stage2['stage2-lr1e-5-s42'][s] if precision=='Q4_K_M' else json.loads(Path(f'data/teacher/eval-ceiling/f16-labels/s42{precision}-{s}.json').read_text())) for s in ('dev','everyday')}
for seed in (42,43):
 for precision in precisions:
  arm=f's{seed}-{precision}'
  arms[arm]={s:json.loads((root/f'{arm}-{s}.json').read_text()) for s in ('dev','everyday')}
labels={arm:{**splits['dev'],**splits['everyday']} for arm,splits in arms.items()}
v2={p:{**splits['dev'],**splits['everyday']} for p,splits in baselines.items()}
coverage=json.loads((root/'coverage.json').read_text());teacher=json.loads(Path('data/teacher/eval-ceiling/teacher-report.json').read_text())['per_case']
f16={i:v for split in ('dev','everyday') for i,v in json.loads(Path(f'data/teacher/eval-ceiling/f16-labels/s42f16-{split}.json').read_text()).items()}
teacher_misses=sorted(i for i,v in teacher.items() if v['majority'] in correct and f16[i] not in correct)
assert len(teacher_misses)==30
stats={};flips={};gains={};latency={};rss={}
for arm,rows in labels.items():
 assert set(rows)==set(labels['default']) and set(rows.values())<=valid
 counts=Counter(rows.values())
 stats[arm]={'dev':sum(v in correct for v in arms[arm]['dev'].values()),'everyday':sum(v in correct for v in arms[arm]['everyday'].values()),'pooled':sum(v in correct for v in rows.values()),'accepted_wrong':counts['wrong'],'rejected':counts['rejected'],'abstain_missed':counts['abstain-missed']}
 latency[arm]={s:float(re.search(r'p50 ([0-9.]+)s',(root/f'{arm}-{s}.log').read_text())[1]) for s in ('dev','everyday')}
 if arm=='default':continue
 precision=arm.split('-',1)[1];flips[arm]={};stats[arm]['paired']={}
 for name,reference in [('default',labels['default']),('v2',v2[precision])]:
  changed=[{'id':i,'before':reference[i],'after':rows[i]} for i in sorted(rows) if reference[i]!=rows[i]]
  wins=sum(reference[i] not in correct and v in correct for i,v in rows.items());losses=sum(reference[i] in correct and v not in correct for i,v in rows.items())
  assert wins-losses==stats[arm]['pooled']-sum(v in correct for v in reference.values())
  stats[arm]['paired'][name]={'wins':wins,'losses':losses};flips[arm][name]=changed
 gains[arm]={}
 for bucket in sorted(coverage['counts']):
  ids=[i for i,b in coverage['per_case'].items() if b==bucket]
  gains[arm][bucket]={'cases':len(ids),'v3_correct':sum(rows[i] in correct for i in ids),'v2_correct':sum(v2[precision][i] in correct for i in ids),'default_correct':sum(labels['default'][i] in correct for i in ids)}
 stats[arm]['teacher_right_f16_student_wrong_fixed']=[i for i in teacher_misses if rows[i] in correct]
 rss[arm]={s:json.loads((root/f'{arm}-{s}-rss.json').read_text()) for s in ('dev','everyday')}
rules={}
for precision in precisions:
 checks={}
 for seed in (42,43):
  arm=f's{seed}-{precision}';r=stats[arm];d=stats['default']
  checks[str(seed)]={'pooled_improves':r['pooled']>d['pooled'],'neither_split_regresses':r['dev']>=d['dev'] and r['everyday']>=d['everyday'],'accepted_wrong_does_not_increase':r['accepted_wrong']<=d['accepted_wrong'],'abstain_missed_does_not_increase':r['abstain_missed']<=d['abstain_missed']}
 rules[precision]={'by_seed':checks,'passed':all(all(c.values()) for c in checks.values())}
v2stats={p:{'dev':sum(v in correct for v in rs['dev'].values()),'everyday':sum(v in correct for v in rs['everyday'].values()),'pooled':sum(v in correct for v in v2[p].values())} for p,rs in baselines.items()}
attribution=all(stats[f's{seed}-Q8_0']['pooled']>=v2stats['Q8_0']['pooled']+3 and stats[f's{seed}-Q8_0']['paired']['v2']['wins']>stats[f's{seed}-Q8_0']['paired']['v2']['losses'] for seed in (42,43))
budget=json.loads(Path('docs/server-memory-comparison.json').read_text())['baseline']['sampled_peak_rss_bytes']+64*1024*1024
result={'stats':stats,'v2_same_precision':v2stats,'screening':rules,'attribution_passed':attribution,'nominated_seed':42,'flips':flips,'coverage':coverage,'coverage_results':gains,'teacher_right_f16_student_wrong_ids':teacher_misses,'latency_p50_seconds_by_split':latency,'rss':rss,'rss_budget_bytes':budget}
(out/'screening-results.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n')
model_hashes={}
for seed in (42,43):
 for line in (out/f'seed{seed}-artifacts-sha256.txt').read_text().splitlines():
  digest,path=line.split('  ',1)
  if 'merged-Q' in path:model_hashes[f's{seed}-'+Path(path).stem.removeprefix('merged-')]=digest
Path('docs/v3-arm-labels.json').write_text(json.dumps({'arms':arms,'data_sha256':'c8f9661db1cadf79d81c58f0fd8f0628ad3461c61c0a5f97c6b20f195ec06550','models_sha256':model_hashes,'metric':'correct = pass + abstain-ok'},sort_keys=True,indent=2)+'\n')
print(json.dumps({'stats':stats,'v2':v2stats,'screening':rules,'attribution_passed':attribution},sort_keys=True))
