import json,os,shutil,subprocess,sys,time
from pathlib import Path
arm,model=sys.argv[1:]
assert arm in ('s42-Q8_0','s42-Q6_K','s42-Q4_K_M','s43-Q8_0','s43-Q6_K','s43-Q4_K_M')
model=str(Path(model).resolve());assert Path(model).is_file()
root=Path('/tmp/whatisit-v3-screen')
env={**os.environ,'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','PYTHONPATH':'src','WHATISIT_MODEL':model}
for split in ('dev','everyday'):
 subprocess.run(['/Users/imadeddine/.local/bin/whatisit','stop'],env=env,check=True)
 log=root/f'{arm}-{split}.log';assert not log.exists()
 samples=[]
 with log.open('w') as output:
  process=subprocess.Popen(['/Users/imadeddine/.local/pipx/venvs/whatisit/bin/python','tools/eval_fallback.py',split,'lint','-q'],env=env,stdout=output,stderr=subprocess.STDOUT)
  while process.poll() is None:
   snapshot=subprocess.check_output(['/bin/ps','-axo','pid=,rss=,command='],text=True)
   for line in snapshot.splitlines():
    if 'llama-server' in line and model in line:
     fields=line.split(None,2);samples.append(int(fields[1])*1024)
   time.sleep(.1)
  assert process.returncode==0,log
 assert samples,'No matching llama-server RSS samples'
 shutil.copyfile(f'/tmp/eval-{split}-lint.json',root/f'{arm}-{split}.json')
 (root/f'{arm}-{split}-rss.json').write_text(json.dumps({'model':model,'sample_interval_seconds':.1,'sample_count':len(samples),'sampled_peak_rss_bytes':max(samples)},sort_keys=True,indent=2)+'\n')
 print(log.read_text().strip(),flush=True)
subprocess.run(['/Users/imadeddine/.local/bin/whatisit','stop'],env=env,check=True)
