import json,glob,collections,statistics,sys
A=sys.argv[1]; P=json.load(open(sys.argv[2]))
K=json.load(open(f'{A}/items.json'))
def load(pat):
    V={}
    for f in glob.glob(pat):
        for c in json.load(open(f))['cases']:
            for v in c['verdicts']: V[v['key']]={**v,'case_flag':c.get('case_flag')}
    return V
S1=load(f'{A}/pass1-sonnet/b*.json'); S2=load(f'{A}/pass2-opus/r*.json')
ok=lambda s: s in('pass','abstain-ok')
final={}; flips=collections.Counter(); unresolved=[]
for k,i in K.items():
    sc=ok(i['scorer'])
    if k not in S2: final[k]=sc; continue
    v1,v2=S1[k]['verdict'],S2[k]['verdict']
    if v2=='unsure' or (v1!='unsure' and v1!=v2): final[k]=sc; unresolved.append(k); continue
    final[k]=(v2=='correct')
    if final[k]!=sc: flips['scorer wrong->correct' if final[k] else 'scorer pass->incorrect']+=1
print('re-checked',len(S2),'flips',dict(flips),'unresolved (kept scorer)',len(unresolved))
cmd2key={(i['id'],i['command']):k for k,i in K.items()}
cases={i['id']:i['answerable'] for i in K.values()}
allids=set()
for r in P['outputs'].values(): allids|=set(r)
def correct(cid,cmd):
    if not cmd: return not cases.get(cid,True) if cid in cases else False
    return final[cmd2key[(cid,cmd)]]
# unanswerable with no command: abstain-ok
ans={}
import re
for sp in ('dev','everyday'):
    for l in open(f'eval/{sp}.jsonl'):
        c=json.loads(l); ans[c['id']]=c['accept'] is not None
def corr(cid,cmd): return (not ans[cid]) if not cmd else final[cmd2key[(cid,cmd)]]
res={}
for r,o in P['outputs'].items():
    res[r]=(sum(ok_ for ok_ in [corr(c,m) for c,m in o.items()]), sum(1 for c,m in o.items() if m and not corr(c,m)))
print('run: audited correct /141, accepted-but-incorrect')
for r in res: print(' ',r,res[r])
for a in 'AB': print(a,'mean',statistics.mean(res[f'{a}-s{i}'][0] for i in range(1,9)))
T=P['teacher']
per=statistics.mean(sum(corr(c,m) for m in ms)/len(ms) for c,ms in T.items())*141
p5=sum(any(corr(c,m) for m in ms) for c,ms in T.items())
print('teacher audited: mean per-sample',round(per,1),'pass@5',p5)
cat=collections.Counter()
for r in [f'{a}-s{i}' for a in 'AB' for i in range(1,9)]:
    for c,m in P['outputs'][r].items():
        if m and not corr(c,m):
            k=cmd2key[(c,m)]; v=S2.get(k,S1[k]); cat[v.get('category') or 'unresolved']+=1
print('student error categories (16 adapters):',cat.most_common())
json.dump({'final':final,'unresolved':unresolved,'scores':res},open(f'{A}/final.json','w'),indent=1)
