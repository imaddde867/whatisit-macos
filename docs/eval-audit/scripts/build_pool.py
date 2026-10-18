import json,re,collections,statistics,sys,random
sys.path.insert(0,'tools')
D='docs/runtime-lora-8seed/'
cases={}
for sp in ('dev','everyday'):
    for l in open(f'eval/{sp}.jsonl'):
        c=json.loads(l); c['split']=sp; cases[c['id']]=c
def label(c,cmd):
    if c['accept'] is None: return 'abstain-missed' if cmd else 'abstain-ok'
    if not cmd: return 'rejected'
    a=[c['accept']] if isinstance(c['accept'],str) else c['accept']
    return 'pass' if any(re.search(p,cmd) for p in a) else 'wrong'
runs=['default']+[f'{a}-s{i}' for a in 'AB' for i in range(1,9)]
outputs={}  # run -> id -> command (None = no command)
score={}
for r in runs:
    outputs[r]={}
    for sp in ('dev','everyday'):
        for k,v in json.load(open(f'{D}{r}-{sp}-detail.json')).items():
            outputs[r][k]=v['command']
    score[r]=sum(label(cases[k],c) in('pass','abstain-ok') for k,c in outputs[r].items())
print('default',score['default'],'A',statistics.mean(score[f'A-s{i}'] for i in range(1,9)),'B',statistics.mean(score[f'B-s{i}'] for i in range(1,9)))
# teacher
from score_teacher_eval import effective_command
teacher={}
for l in open('data/teacher/eval-ceiling/raw_samples.jsonl'):
    t=json.loads(l); teacher[t['id']]=[effective_command(s,t['request']) for s in t['samples']]
p5=sum(any(label(cases[k],c) in('pass','abstain-ok') for c in cs) for k,cs in teacher.items())
maj=sum(label(cases[k],collections.Counter(cs).most_common(1)[0][0]) in('pass','abstain-ok') for k,cs in teacher.items())
print('teacher pass@5',p5,'majority(approx)',maj)
pool=collections.defaultdict(lambda:{'sources':collections.Counter()})
for r in runs:
    for k,c in outputs[r].items():
        if c: pool[(k,c)]['sources'][r]+=1
for k,cs in teacher.items():
    for c in cs:
        if c: pool[(k,c)]['sources']['teacher']+=1
for k,c in cases.items():
    for t in c.get('traps') or []: pool[(k,t)]['sources']['trap']+=1
items=[]
for (k,cmd),p in pool.items():
    c=cases[k]; items.append({'id':k,'request':c['request'],'reference':c['reference'],'answerable':c['accept'] is not None,
      'command':cmd,'scorer':label(c,cmd),'sources':dict(p['sources'])})
print(len(items), collections.Counter((i['scorer'],'trap' in i['sources']) for i in items))
json.dump({'items':items,'outputs':outputs,'teacher':teacher},open(sys.argv[1],'w'),indent=1)
