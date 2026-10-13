import hashlib,json,subprocess,time
from pathlib import Path
root=Path('/tmp/whatisit-v3-screen');directory=Path('/Users/imadeddine/.local/share/whatisit/finetune/v3')
expected={}
for seed in (42,43):
 for line in Path(f'docs/v3-training-reports/seed{seed}-artifacts-sha256.txt').read_text().splitlines():
  digest,path=line.split('  ',1);name=Path(path).name
  if name.startswith('merged-Q'):
   arm=f's{seed}-'+name.removeprefix('merged-').removesuffix('.gguf')
   expected[arm]=(directory/name if seed==42 else directory/'seed43'/name,digest)
assert len(expected)==6
verified={}
while expected:
 for arm,(path,digest) in list(expected.items()):
  if not path.exists():continue
  actual=hashlib.sha256(path.read_bytes()).hexdigest();assert actual==digest,(arm,actual,digest)
  verified[arm]={'model':str(path),'sha256':actual,'verified_after_copy':True}
  (root/'transfer-verification.json').write_text(json.dumps(verified,sort_keys=True,indent=2)+'\n')
  print(f'{arm}: transfer hash verified; screening both splits.',flush=True)
  subprocess.run(['/Users/imadeddine/Documents/GitHub/experiments/whatisit-macos/.venv/bin/python','/tmp/whatisit-v3-run-arm.py',arm,str(path)],check=True)
  del expected[arm]
 if expected:time.sleep(1)
print('All six arms transferred, verified and screened.',flush=True)
