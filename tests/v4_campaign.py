"""Synthetic v4 judge campaign fixtures shared by the pool/confirm/build tests."""
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_v4_pool
import build_verified_dataset
import make_v4_confirm


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


def stub_effective(sample, request, path=None):
    return sample['cmd']


def stub_validate(rid, command, request, path=None):
    return None


def tree_bytes(root):
    root = Path(root)
    return {str(path.relative_to(root)): path.read_bytes()
            for path in sorted(root.rglob('*')) if path.is_file()}


def read_batches(directory):
    directory = Path(directory)
    return {path.stem: json.loads(path.read_text())
            for path in sorted(directory.glob('b*.json'))}


def _entry(verdict):
    value, category, evidence = verdict if isinstance(verdict, tuple) else (verdict, None, None)
    if value == 'incorrect' and category is None:
        category = 'other'
    if value != 'incorrect':
        category = None
    return {'verdict': value, 'category': category,
            'evidence': evidence or 'Fixture judgment.'}


def write_verdicts(batches, out_dir, verdict_for, judge='fixture-judge'):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, batch in batches.items():
        cases = []
        for item in batch['items']:
            entries = []
            for candidate in item['candidates']:
                verdict = _entry(verdict_for(item['case'], candidate['key'],
                                             candidate['command']))
                entries.append({'key': candidate['key'], **verdict})
            cases.append({'case': item['case'], 'verdicts': entries})
        (out / f'{name}.json').write_text(json.dumps({
            'batch': name, 'judge': judge, 'cases': cases}, indent=2) + '\n')


CONTROLS = [
    {'key': 'ct0001', 'case': 'CTL-01', 'request': 'Control alpha request.',
     'command': 'echo control-alpha', 'expected': 'correct',
     'source': 'docs/eval-audit/items.json#x9001',
     'provenance': 'fixture pass2 r0.json correct'},
    {'key': 'ct0002', 'case': 'CTL-02', 'request': 'Control beta request.',
     'command': 'printf bad', 'expected': 'incorrect',
     'source': 'docs/eval-audit/items.json#x9002',
     'provenance': 'fixture pass2 r1.json incorrect'},
    {'key': 'ct0003', 'case': 'CTL-03', 'request': 'Control gamma request.',
     'command': 'echo control-gamma', 'expected': 'correct',
     'source': 'docs/eval-audit/items.json#x9003',
     'provenance': 'fixture pass2 r2.json correct'},
    {'key': 'ct0004', 'case': 'CTL-04', 'request': 'Control delta request.',
     'command': 'false --control', 'expected': 'incorrect',
     'source': 'docs/eval-audit/items.json#x9004',
     'provenance': 'fixture pass2 r3.json incorrect'},
    {'key': 'ct0005', 'case': 'CTL-05', 'request': 'Control epsilon request.',
     'command': 'echo control-epsilon', 'expected': 'correct',
     'source': 'docs/eval-audit/items.json#x9005',
     'provenance': 'fixture pass2 r4.json correct'},
    {'key': 'ct0006', 'case': 'CTL-06', 'request': 'Control zeta request.',
     'command': 'rm -rf control-dir', 'expected': 'incorrect',
     'source': 'docs/eval-audit/items.json#x9006',
     'provenance': 'fixture pass2 r5.json incorrect'},
]

CORPUS = [
    {'id': 'r00001', 'request': 'Show the Working  Directory', 'kind': 'answer'},
    {'id': 'r00002', 'request': 'what time is it', 'kind': 'abstain'},
    {'id': 'r00003', 'request': 'print the kernel version', 'kind': 'answer'},
    {'id': 'r00004', 'request': 'show the current directory path', 'kind': 'answer'},
    {'id': 'r00005', 'request': 'show current user', 'kind': 'answer'},
    {'id': 'r00006', 'request': 'list files by size', 'kind': 'answer'},
    {'id': 'r00007', 'request': 'show disk usage', 'kind': 'answer'},
    {'id': 'r00008', 'request': 'show disk usage', 'kind': 'answer'},
    {'id': 'r00009', 'request': 'show current user account', 'kind': 'answer'},
    {'id': 'r00010', 'request': 'print hostname', 'kind': 'answer'},
    {'id': 'r00011', 'request': 'show calendar', 'kind': 'answer'},
    {'id': 'r00012', 'request': 'search leak pattern', 'kind': 'answer'},
    {'id': 'r00013', 'request': 'find the biggest log file', 'kind': 'answer'},
    {'id': 'r00014', 'request': 'find the biggest log file', 'kind': 'answer'},
    {'id': 'r00015', 'request': 'request with no usable samples', 'kind': 'answer'},
]

V3_TRAIN = [
    {'id': 'r00001', 'messages': [
        {'role': 'system', 'content': 'SYS'},
        {'role': 'user', 'content': 'Show the Working  Directory'},
        {'role': 'assistant', 'content': 'echo one'}]},
    {'id': 'r00002', 'messages': [
        {'role': 'system', 'content': 'SYS'},
        {'role': 'user', 'content': 'what time is it'},
        {'role': 'assistant', 'content': ''}]},
    {'id': 'r00003', 'messages': [
        {'role': 'system', 'content': 'SYS'},
        {'role': 'user', 'content': 'print the kernel version'},
        {'role': 'assistant', 'content': 'uname -a'}]},
    {'id': 'r00004', 'messages': [
        {'role': 'system', 'content': 'SYS'},
        {'role': 'user', 'content': 'show the current directory path'},
        {'role': 'assistant', 'content': 'pwd -P'}]},
    {'id': 'r00005', 'messages': [
        {'role': 'system', 'content': 'SYS'},
        {'role': 'user', 'content': 'show current user'},
        {'role': 'assistant', 'content': 'whoami'}]},
]

V3_REQUESTS = [
    {'id': 'r00001', 'request': 'Show the Working  Directory', 'kind': 'answer',
     'path': 'notes/report.txt'},
    {'id': 'r00002', 'request': 'what time is it', 'kind': 'abstain'},
    {'id': 'r00003', 'request': 'print the kernel version', 'kind': 'answer'},
    {'id': 'r00004', 'request': 'show the current directory path', 'kind': 'answer'},
    {'id': 'r00005', 'request': 'show current user', 'kind': 'answer'},
]

RAW = [
    {'id': 'r00006', 'request': 'list files by size', 'samples': [
        {'cmd': 'ls -lS'}, {'cmd': 'ls -lS'}, {'cmd': 'ls -lt'}]},
    {'id': 'r00007', 'request': 'show disk usage',
     'samples': [{'cmd': 'du -sh .'}] * 3},
    {'id': 'r00008', 'request': 'show disk usage',
     'samples': [{'cmd': 'du -sh .'}] * 3},
    {'id': 'r00009', 'request': 'show current user account',
     'samples': [{'cmd': 'whoami'}] * 2},
    {'id': 'r00010', 'request': 'print hostname',
     'samples': [{'cmd': 'hostname'}] * 2},
    {'id': 'r00011', 'request': 'show calendar',
     'samples': [{'cmd': 'cal'}] * 2},
    {'id': 'r00012', 'request': 'search leak pattern',
     'samples': [{'cmd': 'grep foo first.txt'}] * 2},
    {'id': 'r00013', 'request': 'find the biggest log file',
     'samples': [{'cmd': 'grep leakword first.txt'}] * 2},
    {'id': 'r00014', 'request': 'find the biggest log file',
     'samples': [{'cmd': 'wc -l clean.log'}] * 2},
    {'id': 'r00015', 'request': 'request with no usable samples',
     'samples': [{'cmd': None}, {'cmd': None}]},
]

EVAL_SPLITS = {
    'dev': [
        {'request': 'unrelated dev task about searching a log',
         'reference': 'grep bar eval.txt'},
        {'request': 'unrelated dev task about sorting output',
         'reference': 'sort -u unrelated.txt'},
    ],
    'everyday': [
        {'request': 'unrelated everyday task about wifi',
         'reference': 'networksetup -getairportnetwork en0'},
    ],
    'frozen': [
        {'request': 'unrelated frozen task about dates',
         'reference': 'date +%Y'},
    ],
    'heldout': [
        {'request': 'unrelated heldout task about logs',
         'reference': 'grep leakword eval.txt'},
    ],
}


class Campaign:
    """A complete small campaign: immutable inputs, pool, pass 1, confirm, pass 2."""

    def __init__(self, root, batch_size=5, controls_per_batch=2, control_seed=13,
                 validate=stub_validate):
        self.validate = validate
        self.root = Path(root)
        self.batch_size = batch_size
        self.controls_per_batch = controls_per_batch
        self.control_seed = control_seed
        self.judge_dir = self.root / 'data/distill/stage2-v4/judge'
        self.pool = self.judge_dir / 'pool'
        self.verdict_dir = self.judge_dir / 'verdicts'
        self.confirm_dir = self.judge_dir / 'confirm'
        self.confirm_verdict_dir = self.judge_dir / 'confirm-verdicts'
        self._write_inputs()
        self.pool_manifest = build_v4_pool.build_pool(
            self.root / 'data/corpus/requests.jsonl',
            self.root / 'data/teacher/roihu_full_raw_samples.jsonl',
            self.root / 'data/distill/stage2-v3', self.pool,
            batch_size=batch_size, controls_path=self.judge_dir / 'controls.jsonl',
            controls_per_batch=controls_per_batch, effective=stub_effective,
            validate=self.validate, control_seed=control_seed)
        self.keymap = json.loads((self.pool / 'keymap.json').read_text())
        self.controls_map = json.loads((self.pool / 'controls-map.json').read_text())
        self.pool_batches = read_batches(self.pool / 'batches')

    def _write_inputs(self):
        write_jsonl(self.root / 'data/corpus/requests.jsonl', CORPUS)
        write_jsonl(self.root / 'data/teacher/roihu_full_raw_samples.jsonl', RAW)
        write_jsonl(self.root / 'data/distill/stage2-v3/train.jsonl', V3_TRAIN)
        write_jsonl(self.root / 'data/distill/stage2-v3/requests.jsonl', V3_REQUESTS)
        write_jsonl(self.judge_dir / 'controls.jsonl', CONTROLS)
        (self.root / 'data/distill/roihu_full_quarantine_ids.txt').write_text(
            '# historical list is empty\n')
        (self.root / 'data/distill/quarantine_ids.txt').write_text(
            'r00010 # fixture quarantine\n')
        for split, rows in EVAL_SPLITS.items():
            write_jsonl(self.root / 'eval' / f'{split}.jsonl', rows)

    def key(self, rid, command):
        found = [key for key, entry in self.keymap.items()
                 if entry['rid'] == rid and entry['command'] == command]
        if len(found) != 1:
            raise KeyError((rid, command, found))
        return found[0]

    def case(self, rid):
        found = {entry['case'] for entry in self.keymap.values() if entry['rid'] == rid}
        if len(found) != 1:
            raise KeyError((rid, found))
        return found.pop()

    def control_key(self, origin_key):
        found = [key for key, entry in self.controls_map.items()
                 if entry['origin_key'] == origin_key]
        if len(found) != 1:
            raise KeyError((origin_key, found))
        return found[0]

    def write_pass1(self, directory=None, overrides=None, judge='fixture-pass1'):
        overrides = overrides or {}

        def verdict_for(case, key, command):
            if key in overrides:
                return overrides[key]
            if key in self.controls_map:
                return self.controls_map[key]['expected']
            return 'correct'

        out = Path(directory) if directory is not None else self.verdict_dir
        write_verdicts(self.pool_batches, out, verdict_for, judge)
        return out

    def make_confirm(self, out_dir=None, sample=1.0, seed=13, batch_size=90):
        out = Path(out_dir) if out_dir is not None else self.confirm_dir
        with patch.object(build_verified_dataset, 'ROOT', self.root):
            self.confirm_manifest = make_v4_confirm.build_confirm(
                self.pool / 'keymap.json',
                self.root / 'data/teacher/roihu_full_raw_samples.jsonl',
                self.root / 'data/distill/stage2-v3/requests.jsonl',
                self.verdict_dir, out, sample=sample, seed=seed, batch_size=batch_size,
                effective=stub_effective, pool_dir=self.pool, validate=self.validate)
        return self.confirm_manifest

    def write_pass2(self, confirm_dir=None, directory=None, overrides=None,
                    judge='fixture-pass2'):
        overrides = overrides or {}
        confirm_dir = Path(confirm_dir) if confirm_dir is not None else self.confirm_dir
        batches = read_batches(confirm_dir)

        def verdict_for(case, key, command):
            return overrides.get(key, 'correct')

        out = Path(directory) if directory is not None else self.confirm_verdict_dir
        write_verdicts(batches, out, verdict_for, judge)
        return out

    def build_verified(self, out_dir, pass1=None, confirm=None, pass2=None,
                       sample=1.0, seed=13, controls_path=None):
        fake = types.ModuleType('score_teacher_eval')
        fake.effective_command = stub_effective
        with patch.object(build_verified_dataset, 'ROOT', self.root), \
                patch.object(build_verified_dataset, 'validate_command', self.validate), \
                patch.dict(sys.modules, {'score_teacher_eval': fake}):
            return build_verified_dataset.build(
                self.keymap,
                Path(pass1) if pass1 is not None else self.verdict_dir,
                Path(confirm) if confirm is not None else self.confirm_dir,
                Path(pass2) if pass2 is not None else self.confirm_verdict_dir,
                out_dir, pool_dir=self.pool, sample=sample, seed=seed,
                controls_path=controls_path)
