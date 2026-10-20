"""One-off serial execution of the approved r2 pass-1 campaign; never trains."""
import hashlib
import json
import os
import shutil
import tempfile
import urllib.request
from pathlib import Path
from judge_v4_local import judge
from build_verified_dataset import load_verdicts
from repair_distill_dataset import validation_fingerprint

root = Path(__file__).resolve().parent.parent
state_path = root / 'campaign-20261020-r2.json'
state = json.loads(state_path.read_text())
digest = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
controller = Path('tools/judge_v4_local.py').read_bytes()
assert hashlib.sha256(controller).hexdigest() == state['provider_amendment']['controller_sha256']
assert not any(a['status'] == 'running' for a in state['attempts']), 'Resolve interrupted attempt before resuming'
keymap = json.loads((root / 'pool/keymap.json').read_text())
controls = json.loads((root / 'pool/controls-map.json').read_text())
rubric = (root.parent / 'LABEL.md').read_text()
observations = json.loads((root / 'r2-path-observations.json').read_text())['paths']
expected_server = state['provider_amendment']['server_environment']
(root / 'strata-runs/pass1-controller.pid').write_text(str(os.getpid()) + '\n')

def save():
    temporary = state_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + '\n')
    temporary.replace(state_path)

def preflight():
    assert all(digest(p) == sha for p, sha in state['sha256'].items()), 'Frozen input changed'
    assert validation_fingerprint() == state['validation'], 'Validation environment changed'
    assert all(os.path.exists(p) == value for p, value in observations.items()), 'Observed path state changed'
    assert all(digest(root / f'verdicts/{b}.json') == sha for b, sha in state['accepted_pass1'].items())
    assert hashlib.sha256(Path('tools/judge_v4_local.py').read_bytes()).hexdigest() == hashlib.sha256(controller).hexdigest()
    with urllib.request.urlopen('http://127.0.0.1:18080/props', timeout=15) as response:
        props = json.load(response)
    actual = {k: props.get(k) for k in expected_server}
    assert actual == expected_server, 'Strata server/model/default settings changed'

try:
    for batch_path in sorted((root / 'pool/batches').glob('b[0-9][0-9].json')):
        batch = json.loads(batch_path.read_text())
        name = batch['batch']
        while name not in state['accepted_pass1']:
            if state.get('budget_stop') or state['failed_attempts'] >= 3:
                raise SystemExit('Approved retry budget reached')
            preflight()
            failed = sum(a['batch'] == name and a['status'] == 'failed' for a in state['attempts'])
            assert failed < 2, 'Batch retry budget reached'
            number = failed + 1
            session = f'strata-qwen3.8-flash-next-iq3_s-r2-p1-{name}-a{number}'
            assert all(a['session'] != session for a in state['attempts'])
            run_dir = root / f'strata-runs/{name}-a{number}'
            output = root / f'verdicts/{name}.json'
            assert not output.exists() and not run_dir.exists(), 'Preserve existing evidence before retry'
            attempt = {'batch': name, 'attempt': number, 'session': session,
                       'status': 'running', 'provider': 'Strata on5090-1',
                       'trace': str(run_dir.relative_to(root)),
                       'controller_sha256': hashlib.sha256(controller).hexdigest()}
            state['attempts'].append(attempt)
            state['status'] = f"local pass1 {len(state['accepted_pass1'])}/23 accepted; {name} running"
            save()
            print(json.dumps({'started': name, 'attempt': number}), flush=True)
            try:
                judge(batch, rubric, session, output, run_dir,
                      'http://127.0.0.1:18080/v1', 'qwen3.8-flash-next-iq3_s')
                preflight()
                keys = {c['key'] for item in batch['items'] for c in item['candidates']}
                km = {k: v for k, v in keymap.items() if k in keys}
                cm = {k: v for k, v in controls.items() if k in keys}
                with tempfile.TemporaryDirectory() as tmp:
                    shutil.copy2(output, Path(tmp) / f'{name}.json')
                    verdicts = load_verdicts(tmp, {name: batch}, keymap=km,
                                             controls=cm, require_keys=keys)
                attempt.update(status='passed', keys=len(verdicts), controls=len(cm),
                               verdict_sha256=digest(output))
                state['accepted_pass1'][name] = attempt['verdict_sha256']
            except AssertionError:
                raise
            except Exception as error:
                attempt.update(status='failed', reason=str(error)[:2000])
                state['failed_attempts'] += 1
                if output.exists():
                    destination = root / f'superseded/r2-strata-{name}-a{number}.json'
                    assert not destination.exists()
                    output.rename(destination)
                    attempt['archived_verdict'] = str(destination.relative_to(root))
                state['budget_stop'] = number >= 2 or state['failed_attempts'] >= 3
            finally:
                if run_dir.exists():
                    (run_dir / 'controller.py').write_bytes(controller)
            state['status'] = ('retry budget stop' if state.get('budget_stop') else
                               f"local pass1 {len(state['accepted_pass1'])}/23 accepted; {state['failed_attempts']} failed attempts")
            assert state['failed_attempts'] == sum(a['status'] == 'failed' for a in state['attempts'])
            assert len({a['session'] for a in state['attempts']}) == len(state['attempts'])
            save()
            print(json.dumps({'batch': name, 'result': attempt['status'],
                              'accepted': len(state['accepted_pass1']),
                              'failed_attempts': state['failed_attempts'],
                              'budget_stop': state.get('budget_stop', False),
                              'reason': attempt.get('reason')}), flush=True)
            if state.get('budget_stop'):
                raise SystemExit('Approved retry budget reached; evidence preserved')
    preflight()
    state['status'] = 'pass1 complete; independent confirmation and remaining acceptance work pending'
    save()
    print(state['status'], flush=True)
except AssertionError as error:
    state['status'] = 'frozen-state/invariant stop: ' + str(error)
    save()
    raise

