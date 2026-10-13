import json, os, subprocess, tempfile
from pathlib import Path
from build_distill_dataset import read_jsonl
root=Path('data/distill/stage2-v3')
rows={r['id']:r['messages'][-1]['content'] for r in read_jsonl(root/'train.jsonl')}
approved={
'r00314':'find project -mindepth 1 -maxdepth 1 -type d',
'r00336':'date -j -u -f "%Y-%m-%dT%H:%M:%S%z" "2025-06-15T14:30:00+0300" "+%Y-%m-%dT%H:%M:%SZ"',
'r00553':"grep -Eo '([+-][0-9]{2}:?[0-9]{2}|Z)' mac-log-times.txt",
'r00740':"git -C project/ rev-parse 'HEAD@{1}'",
'r00896':"stat -f '%A' .env.example",
'r00984':'date -j -v-1d -f "%Y-%m-%d" "2028-03-01" +%Y-%m-%d',
'r01082':'du -sh -I .DS_Store project/',
'r01095':'grep -riw "draft" prose/',
'r01168':'find workspace -mindepth 1 -maxdepth 1 -type d | sort',
'r01209':"grep -Eo '([0-9]{1,3}\\.){3}[0-9]{1,3}' access.log",
'r01235':'du -sh -I node_modules project/',
'r01564':'find fixtures -mindepth 3 -maxdepth 3 -type d -name cache',
'r01674':'test -r sample.txt && test -w sample.txt && echo yes || echo no',
'r01690':'/usr/libexec/PlistBuddy -c "Print :CFBundlePackageType" MyApp.app/Contents/Info.plist',
'r01811':"grep -nE '^(<<<<<<<|=======|>>>>>>>)' project/notes.txt",
'r01848':"mdfind -onlyin review 'kMDItemLastUsedDate < 2024-01-01'",
'r01911':'stat -f "%SB" Project.alias',
'r02102':"mdfind -onlyin document-tests/ 'kMDItemAuthors == nil'",
'r02271':'grep -F -C 2 FAILURE errors.txt',
'r02276':'stat -l -f "%SB" current',
'r02338':'stat -f "%i" report.pdf',
'r02393':'stat -f "%l %b" data.bin',
'r02397':'du -sh -L project/',
'r02485':"find imports/ -type f -name 'sample-[0-9][0-9][0-9][0-9]'",
}
assert all(rows[rid]==command for rid,command in approved.items())
results=[]
with tempfile.TemporaryDirectory(prefix='whatisit-v3-scratch-') as tmp:
 p=Path(tmp)
 for name in ('project/sub','workspace/a','workspace/b','prose','fixtures/a/b/cache',
              'fixtures/a/cache','imports','review','document-tests','MyApp.app/Contents'):
  (p/name).mkdir(parents=True,exist_ok=True)
 files={'.env.example':'fixture\n','sample.txt':'fixture\n','original':'fixture\n',
 'mac-log-times.txt':'2025-01-01T12:00:00+03:00\n2025-01-01T12:00:00-0500\n2025-01-01T12:00:00Z\n',
 'access.log':'192.0.2.1 999.123.0.9\n','prose/a.txt':'DRAFT\ndrafting\nundrafted\n',
 'project/notes.txt':'<<<<<<< HEAD\na\n=======\nb\n>>>>>>> topic\n',
 'project/.DS_Store':'fixture\n','Project.alias':'fixture\n','report.pdf':'fixture\n','data.bin':'fixture\n',
 'imports/sample-1234':'fixture\n','imports/sample-12345':'fixture\n','imports/sample-abcd':'fixture\n',
 'errors.txt':'a\nb\nFAILURE\nc\nd\ne\n',
 'MyApp.app/Contents/Info.plist':'<?xml version="1.0"?><plist version="1.0"><dict><key>CFBundlePackageType</key><string>APPL</string></dict></plist>'}
 for name,data in files.items():(p/name).write_text(data)
 (p/'.env.example').chmod(0o644)
 (p/'current').symlink_to('original')
 env={**os.environ,'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_SYSTEM':'/dev/null',
      'GIT_AUTHOR_DATE':'2000-01-01T00:00:00+00:00','GIT_COMMITTER_DATE':'2000-01-01T00:00:00+00:00'}
 for args in [['init','-q','-b','main'],['add','.'],['-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','one'],
              ['checkout','-qb','other']]:
  assert subprocess.run(['/usr/bin/git','-C',str(p/'project'),*args],env=env,capture_output=True).returncode==0
 (p/'project/other.txt').write_text('other')
 for args in [['add','.'],['-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','other']]:
  assert subprocess.run(['/usr/bin/git','-C',str(p/'project'),*args],env=env,capture_output=True).returncode==0
 before_checkout=subprocess.check_output(['/usr/bin/git','-C',str(p/'project'),'rev-parse','HEAD'],env=env,text=True).strip()
 assert subprocess.run(['/usr/bin/git','-C',str(p/'project'),'checkout','-q','main'],env=env,capture_output=True).returncode==0
 (p/'project/after.txt').write_text('after')
 for args in [['add','.'],['-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','after']]:
  assert subprocess.run(['/usr/bin/git','-C',str(p/'project'),*args],env=env,capture_output=True).returncode==0
 for rid,command in approved.items():
  r=subprocess.run(['/bin/zsh','-f','-c',command],cwd=p,env=env,text=True,capture_output=True,timeout=15)
  item={'id':rid,'command':command,'returncode':r.returncode,'read_only_in_scratch':True}
  if rid=='r00740':
   assert r.stdout.strip()!=before_checkout
   item['finding']='HEAD@{1} is the previous reflog entry, not necessarily before the last checkout.'
  elif rid=='r02276':
   assert r.returncode!=0 and "can't use format" in r.stderr
   item['finding']='BSD stat rejects simultaneous -l and -f.'
  elif rid in ('r01848','r02102'):
   item['finding']='Scratch scope only; empty index cannot establish query semantics.'
   item['stderr']=r.stderr.strip()
  else:
   assert r.returncode==0,(rid,r.stderr)
   if rid=='r00336':assert r.stdout.strip()=='2025-06-15T11:30:00Z'
   if rid=='r00984':assert r.stdout.strip()=='2028-02-29'
   if rid=='r00896':assert r.stdout.strip()=='644'
   if rid=='r00553':assert r.stdout.splitlines()==['+03:00','-0500','Z']
   if rid=='r01209':assert r.stdout.splitlines()==['192.0.2.1','999.123.0.9']
   if rid=='r01564':assert r.stdout.strip()=='fixtures/a/b/cache'
   if rid=='r01690':assert r.stdout.strip()=='APPL'
   if rid=='r02485':assert r.stdout.strip()=='imports/sample-1234'
   item['finding']='Read-only fixture check completed; no user-data access.'
  results.append(item)
assert len(results)==24
(root/'execution-checks.json').write_text(json.dumps({'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','results':results},indent=2,sort_keys=True)+'\n')
print(json.dumps({'checked':len(results),'counterexamples':['r00740','r02276']}))
