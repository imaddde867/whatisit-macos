"""Build a blind judge-calibration set from already-accepted v4 pass-1 batches.

The campaign's live controls cannot be used to qualify a replacement judge without
burning the gate. This tool instead reuses two kinds of already-paid material:

1. The controls that were injected into accepted batches. Those controls are spent:
   every control is injected once, so the remaining batches never see them. They are
   the same difficulty and polarity mix as the live gate (8 incorrect, 5 correct here).
2. A stratified sample of accepted candidate verdicts, to check that the replacement
   judge behaves like the judge whose labels it continues.

Both sets are re-blinded with fresh opaque case/key ids so no label is visible in the
batch files. Expected values live only in the key files.

Usage:
    build_v4_judge_calibration.py <pool dir> <verdicts dir> <out dir>
"""
import argparse
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

BATCH = re.compile(r'^b\d{2}$')
CASE_ID = re.compile(r'^c[0-9a-f]{12}$')
KEY_ID = re.compile(r'^k[0-9a-f]{12}$')
SALT = 'v4-judge-calibration-20261021'
VERDICTS = {'correct', 'incorrect', 'unsure'}


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def load(path, label):
    path = Path(path)
    if not path.is_file():
        raise SystemExit(f'{label} not found: {path}')
    return json.loads(path.read_text())


def blind(prefix, value):
    """Deterministic opaque id; the same value always maps to the same id."""
    return prefix + hashlib.sha256(f'{SALT}|{value}'.encode()).hexdigest()[:12]


def load_verdicts(verdict_dir, batches):
    """Return (verdicts, controls_checked) for the accepted batches present on disk."""
    directory = Path(verdict_dir)
    files = sorted(path.name for path in directory.iterdir() if path.is_file()) if directory.is_dir() else []
    if any(not name.endswith('.json') for name in files):
        raise SystemExit(f'verdict directory contains non-JSON files: {files}')
    names = [Path(name).stem for name in files]
    if not names:
        raise SystemExit(f'no verdict files in {directory}')
    if not set(names) <= set(batches):
        raise SystemExit(f'verdict files name unknown batches: {files}')
    if names != [f'b{index:02d}' for index in range(len(names))]:
        raise SystemExit(f'accepted batches must be a prefix of b00..; got {names}')
    verdicts, judges, inputs = {}, {}, {}
    for name in names:
        batch = load(Path(directory) / f'{name}.json', f'verdict {name}')
        if not isinstance(batch, dict) or set(batch) != {'batch', 'judge', 'cases'}:
            raise SystemExit(f'{name}.json: verdict file must contain exactly batch, judge, cases')
        if batch['batch'] != name:
            raise SystemExit(f'{name}.json: batch field does not match filename')
        if not isinstance(batch['judge'], str) or not batch['judge'].strip():
            raise SystemExit(f'{name}.json: judge identity must be non-empty')
        judges[name] = batch['judge']
        inputs[name] = sha256_file(Path(directory) / f'{name}.json')
        for case in batch['cases']:
            for verdict in case['verdicts']:
                if verdict['verdict'] not in VERDICTS:
                    raise SystemExit(f'{name}: bad verdict {verdict["verdict"]!r}')
                verdicts[verdict['key']] = verdict['verdict']
    return names, verdicts, judges, inputs


def spent_controls(controls_map, batches, verdicts):
    """Keys of controls injected into accepted batches; fails closed on any mismatch."""
    spent = {}
    for name, batch in sorted(batches.items()):
        for item in batch['items']:
            keys = [candidate['key'] for candidate in item['candidates'] if candidate['key'] in controls_map]
            if not keys:
                continue
            if any(key not in verdicts for key in keys):
                raise SystemExit(f'{name}: accepted batch is missing a control verdict')
            for key in keys:
                control = controls_map[key]
                if verdicts[key] != control['expected']:
                    raise SystemExit(f'{name}: control {control.get("origin_key", key)} does not match '
                                     f'its expected verdict; batch was not accepted')
                spent[key] = control
    return spent


def control_batch(spent):
    """One blind batch holding every spent control, shuffled deterministically."""
    items = []
    for key, control in spent.items():
        items.append({'case': blind('c', key), 'request': control['request'],
                      'candidates': [{'key': blind('k', key), 'command': control['command']}]})
    random.Random(SALT).shuffle(items)
    return {'batch': 'cal-controls', 'items': items}


def sample_agreement(batches, verdicts, controls_map, seed, per_batch):
    """Stratified sample of accepted cases: hard (>=1 incorrect) and positive (all correct)."""
    hard, positive = [], []
    for name, batch in sorted(batches.items()):
        for item in batch['items']:
            if any(candidate['key'] in controls_map for candidate in item['candidates']):
                continue
            outcomes = [verdicts[candidate['key']] for candidate in item['candidates']]
            entry = (name, item, outcomes)
            if 'incorrect' in outcomes:
                hard.append(entry)
            elif all(outcome == 'correct' for outcome in outcomes):
                positive.append(entry)
    chosen = {}
    for kind, pool in (('hard', hard), ('positive', positive)):
        by_batch = defaultdict(list)
        for entry in pool:
            by_batch[entry[0]].append(entry)
        picked = []
        for name in sorted(by_batch):
            entries = sorted(by_batch[name], key=lambda entry: entry[1]['case'])
            take = min(per_batch, len(entries))
            picked += random.Random(f'{seed}|{kind}|{name}').sample(entries, take)
        if not picked:
            raise SystemExit(f'no {kind} cases available for calibration')
        chosen[kind] = sorted(picked, key=lambda entry: (entry[0], entry[1]['case']))
    return chosen


def agreement_batches(chosen):
    """Two balanced blind batches; every candidate of each selected case is included."""
    hard = [entry for entry in chosen['hard']]
    positive = [entry for entry in chosen['positive']]
    batches, keys, batch_keys = {}, {}, {'a0': set(), 'a1': set()}
    split = {'a0': [], 'a1': []}
    for index, entry in enumerate(hard):
        split['a0' if index % 2 == 0 else 'a1'].append(('hard', entry))
    for index, entry in enumerate(positive):
        split['a1' if index % 2 == 0 else 'a0'].append(('positive', entry))
    for name, entries in split.items():
        items = []
        for _, (source, item, outcomes) in sorted(entries, key=lambda pair: (pair[1][0], pair[1][1]['case'])):
            candidates = []
            for candidate, outcome in zip(item['candidates'], outcomes):
                key = blind('k', candidate['key'])
                candidates.append({'key': key, 'command': candidate['command']})
                batch_keys[name].add(key)
                keys[key] = {'accepted': outcome, 'batch': source, 'case': item['case'],
                             'original_key': candidate['key']}
            items.append({'case': blind('c', item['case']), 'request': item['request'],
                          'candidates': candidates})
        batches[name] = {'batch': name, 'items': items}
    return batches, keys, batch_keys


def validate_blind(batch, allowed_keys):
    keys = set()
    for item in batch['items']:
        if not CASE_ID.fullmatch(item['case']):
            raise SystemExit(f'{batch["batch"]}: invalid case id {item["case"]!r}')
        if set(item) != {'case', 'request', 'candidates'}:
            raise SystemExit(f'{batch["batch"]}: case carries non-blind metadata')
        for candidate in item['candidates']:
            if set(candidate) != {'key', 'command'} or not KEY_ID.fullmatch(candidate['key']):
                raise SystemExit(f'{batch["batch"]}: invalid candidate {candidate!r}')
            if candidate['key'] in keys:
                raise SystemExit(f'{batch["batch"]}: duplicate key {candidate["key"]}')
            keys.add(candidate['key'])
    if keys != allowed_keys:
        raise SystemExit(f'{batch["batch"]}: blind key set does not match its key file')
    return len(keys)


def build(pool_dir, verdict_dir, out_dir, seed, per_batch):
    pool_dir, out_dir = Path(pool_dir), Path(out_dir)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f'output directory is not empty: {out_dir}')
    manifest = load(pool_dir / 'manifest.json', 'pool manifest')
    controls_map = load(pool_dir / 'controls-map.json', 'controls map')
    batches = {name: load(pool_dir / 'batches' / f'{name}.json', f'batch {name}')
               for name in sorted(manifest['controls_by_batch'])}
    for name in batches:
        if not BATCH.fullmatch(name) or batches[name]['batch'] != name:
            raise SystemExit(f'pool batch {name} is inconsistent')
    accepted, verdicts, judges, verdict_sha = load_verdicts(verdict_dir, batches)
    spent = spent_controls(controls_map, {name: batches[name] for name in accepted}, verdicts)
    if not spent:
        raise SystemExit('no spent controls found in the accepted batches')
    chosen = sample_agreement({name: batches[name] for name in accepted}, verdicts,
                              controls_map, seed, per_batch)
    controls = control_batch(spent)
    agreement, agreement_keys, agreement_batch_keys = agreement_batches(chosen)

    control_keys = {blind('k', key) for key in spent}
    counts = {
        'controls': {'total': len(spent),
                     'correct': sum(1 for expected in spent.values() if expected['expected'] == 'correct'),
                     'incorrect': sum(1 for expected in spent.values() if expected['expected'] == 'incorrect')},
        'agreement': {
            'cases': sum(len(batch['items']) for batch in agreement.values()),
            'candidates': sum(len(item['candidates']) for batch in agreement.values() for item in batch['items']),
            'accepted_incorrect': sum(1 for value in agreement_keys.values() if value['accepted'] == 'incorrect'),
            'accepted_correct': sum(1 for value in agreement_keys.values() if value['accepted'] == 'correct'),
            'by_source_batch': dict(Counter(value['batch'] for value in agreement_keys.values())),
        },
    }
    n_agreement = counts['agreement']['candidates']
    n_incorrect = counts['agreement']['accepted_incorrect']
    pass_bar = {
        'controls': 'every control verdict must equal its expected value; unsure counts as failure',
        'agreement_required': max(1, -(-9 * n_agreement // 10)),
        'agreement_total': n_agreement,
        'false_accept_max': 2 if n_incorrect >= 20 else 1,
        'false_accept_total': n_incorrect,
        'unsure_max': 2,
        'pilot': 'then one b05 attempt with the live controls; any failure still trips the budget',
    }

    control_key_file = {
        blind('k', key): {'expected': control['expected'], 'origin_key': control.get('origin_key'),
                          'source': control.get('source'), 'case': control.get('case'),
                          'request': control['request'],
                          'command': control['command'], 'batch': next(
                              name for name in accepted
                              if any(key == candidate['key'] for item in batches[name]['items']
                                     for candidate in item['candidates']))}
        for key, control in spent.items()
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / 'controls').mkdir()
    (out_dir / 'agreement').mkdir()
    (out_dir / 'agreement' / 'batches').mkdir()
    (out_dir / 'controls' / 'batch.json').write_text(json.dumps(controls, indent=1) + '\n')
    (out_dir / 'controls' / 'key.json').write_text(json.dumps(control_key_file, indent=1, sort_keys=True) + '\n')
    for name, batch in sorted(agreement.items()):
        (out_dir / 'agreement' / 'batches' / f'{name}.json').write_text(json.dumps(batch, indent=1) + '\n')
    (out_dir / 'agreement' / 'key.json').write_text(json.dumps(agreement_keys, indent=1, sort_keys=True) + '\n')

    if validate_blind(controls, control_keys) != len(control_keys):
        raise SystemExit('control batch coverage mismatch')
    for name, batch in agreement.items():
        validate_blind(batch, agreement_batch_keys[name])

    artifacts = {}
    for path in sorted(out_dir.rglob('*')):
        if path.is_file() and path.name != 'manifest.json':
            artifacts[str(path.relative_to(out_dir))] = sha256_file(path)
    record = {
        'revision': '20261021',
        'purpose': 'Qualify a replacement pass-1 judge on already-paid material before any campaign batch is re-judged.',
        'source': {
            'pool_manifest_sha256': sha256_file(pool_dir / 'manifest.json'),
            'controls_map_sha256': sha256_file(pool_dir / 'controls-map.json'),
            'pool_manifest_counts': manifest['counts'],
            'accepted_batches': accepted,
            'accepted_judges': judges,
            'accepted_verdict_sha256': verdict_sha,
            'seed': seed,
            'per_batch_case_sample': per_batch,
        },
        'counts': counts,
        'pass_bar': pass_bar,
        'blindness': 'Fresh opaque case/key ids; expected labels exist only in key.json; '
                     'the judge never sees the key files, controls.jsonl or controls-map.json.',
        'artifacts_sha256': artifacts,
        'limitations': [
            'Qualification measures strictness and consistency with the accepted judge, not absolute correctness.',
            'The 13 spent controls were answered by the accepted judge; a new judge passing them is necessary, not sufficient.',
        ],
    }
    (out_dir / 'manifest.json').write_text(json.dumps(record, indent=1, sort_keys=True) + '\n')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('pool_dir')
    parser.add_argument('verdict_dir')
    parser.add_argument('out_dir')
    parser.add_argument('--seed', type=int, default=20261021)
    parser.add_argument('--per-batch', type=int, default=4,
                        help='cases sampled per accepted batch, per polarity')
    args = parser.parse_args()
    record = build(args.pool_dir, args.verdict_dir, args.out_dir, args.seed, args.per_batch)
    print(json.dumps(record['counts'], indent=1))
    print(json.dumps(record['pass_bar'], indent=1))


if __name__ == '__main__':
    main()
