#!/usr/bin/env python3
"""Mac-only recorded experiment driver; dev/everyday only, guarded server identity."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import statistics
import subprocess
import sys
import time

name = sys.argv[1]
adapter = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else None
sample = name in ('default', 'A-s1', 'B-s1')
repo = Path.cwd()
root = repo / 'docs/runtime-lora-8seed'
base = Path.home() / '.local/share/whatisit/models/nl2sh-1.5b-Q4_K_M.gguf'
server = Path.home() / '.local/share/whatisit/bin/llama-server'
python = Path.home() / '.local/pipx/venvs/whatisit/bin/python'
assert hashlib.sha256(base.read_bytes()).hexdigest() == '6f8a17a11129a31074c944f4c2602453fafd9de43bdaeb1630a8f511ec820f71'
assert adapter is None or adapter.is_file()
env = dict(os.environ, PATH='/usr/bin:/bin:/usr/sbin:/sbin', PYTHONPATH='src', WHATISIT_MODEL=str(base))
for key in ('WHATISIT_LLAMA_SERVER', 'EVAL_SYSTEM_PROMPT_FILE', 'WHATISIT_DATA_DIR'):
    env.pop(key, None)
if adapter:
    wrapper = Path('/private/tmp') / f'whatisit-8seed-{name}-server.sh'
    wrapper.write_text(f'#!/bin/sh\nexec {shlex.quote(str(server))} "$@" --lora {shlex.quote(str(adapter))}\n')
    wrapper.chmod(0o700)
    env['WHATISIT_LLAMA_SERVER'] = str(wrapper)
samples, identities, outputs = [], [], {}
for split in ('dev', 'everyday'):
    # Kill by PID: whatisit stop does not recognize wrapper-started servers.
    old = subprocess.run(['/usr/bin/pgrep', '-x', 'llama-server'], capture_output=True, text=True)
    for pid in old.stdout.split():
        os.kill(int(pid), 15)
    for attempt in range(100):
        if subprocess.run(['/usr/bin/pgrep', '-x', 'llama-server'], capture_output=True).returncode == 1:
            break
        time.sleep(.1)
    assert subprocess.run(['/usr/bin/pgrep', '-fl', 'llama-server'], capture_output=True).returncode == 1
    output = root / 'reports' / f'{name}-{split}.out'
    assert not output.exists(), output
    seen = False
    with output.open('x') as log:
        run = subprocess.Popen([str(python), 'tools/eval_fallback.py', split, 'lint', '-q'], env=env, stdout=log, stderr=subprocess.STDOUT)
        while run.poll() is None:
            pids = subprocess.run(['/usr/bin/pgrep', '-x', 'llama-server'], capture_output=True, text=True).stdout.split()
            assert len(pids) <= 1, pids
            for pid in pids:
                cmd = subprocess.check_output(['/bin/ps', '-p', pid, '-o', 'command='], text=True).strip()
                valid = str(base) in cmd and (str(adapter) in cmd if adapter else '--lora' not in cmd)
                if not valid:
                    run.terminate()
                assert valid, cmd
                seen = True
                identity = {'split': split, 'pid': int(pid), 'command': cmd}
                if identity not in identities:
                    identities.append(identity)
                if sample:
                    rss = subprocess.check_output(['/bin/ps', '-p', pid, '-o', 'rss='], text=True).strip()
                    if rss:
                        samples.append({'split': split, 'unix_time': time.time(), 'rss_bytes': int(rss) * 1024})
            time.sleep(.1)
    assert run.returncode == 0 and seen, output.read_text()
    outputs[split] = output.read_text().strip().splitlines()[-1]
    labels = json.loads(Path(f'/tmp/eval-{split}-lint.json').read_text())
    details = json.loads(Path(f'/tmp/eval-{split}-lint-detail.json').read_text())
    assert {i: d['label'] for i, d in details.items()} == labels
    if name == 'default':
        assert labels == json.loads((repo / 'docs/stage2-arm-labels.json').read_text())['arms']['default'][split], 'STOP: default drift'
    for suffix, data in [('', labels), ('-detail', details)]:
        with (root / f'{name}-{split}{suffix}.json').open('x') as f:
            f.write(json.dumps(data, indent=2) + '\n')
    print(name, outputs[split], flush=True)
for pid in subprocess.run(['/usr/bin/pgrep', '-x', 'llama-server'], capture_output=True, text=True).stdout.split():
    os.kill(int(pid), 15)
record = {'name': name, 'adapter': str(adapter) if adapter else None,
          'adapter_sha256': hashlib.sha256(adapter.read_bytes()).hexdigest() if adapter else None,
          'server_sha256': hashlib.sha256(server.read_bytes()).hexdigest(),
          'identities': identities, 'eval': outputs}
if sample:
    assert samples
    record.update(sampled_mean_rss_bytes=statistics.mean(s['rss_bytes'] for s in samples),
                  sampled_peak_rss_bytes=max(s['rss_bytes'] for s in samples),
                  sample_count=len(samples), sampling_seconds=.1)
    with (root / 'reports' / f'{name}-rss-samples.json').open('x') as f:
        f.write(json.dumps(samples, indent=2) + '\n')
with (root / 'reports' / f'{name}-runtime.json').open('x') as f:
    f.write(json.dumps(record, indent=2) + '\n')
