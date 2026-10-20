#!/usr/bin/env python3
"""Build data v4: v3 rows plus no-majority requests labelled by judged-correct teacher samples.

    PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONPATH=src:tools \
        ~/.local/pipx/venvs/whatisit/bin/python tools/build_verified_dataset.py \
        <keymap.json> <verdict dir> <confirm batches dir> <confirm-verdicts dir> <out dir>

A label is used only if the strict judge pass calls it correct (rubric in
data/distill/stage2-v4/LABEL.md). The build is fail-closed:

* the pool manifest, keymap, controls map, director map and every pool batch are
  verified against their recorded SHA-256 digests and against each other;
* the controls map and the director map are recomputed from the tracked
  controls.jsonl source (expected verdict, command, request, provenance and the
  deterministic opaque ids), not only digest-checked;
* every pool batch must carry at least one expected-correct and one
  expected-incorrect control, and every control verdict must match its expected
  value (a mismatched batch must be re-judged);
* the pass-1 verdict files must cover every batch, case and candidate exactly once
  with a valid schema;
* the deterministic 20% confirmation sample is regenerated from the pass-1
  verdicts and compared byte-for-byte with the confirm manifest and batches;
* both quarantine lists are hashed into the confirm manifest and the build
  manifest, so changing either after confirmation fails the build;
* every sampled candidate must have exactly one valid pass-2 verdict;
* the pass-2 judge identity must differ from the pass-1 judge for the same case;
  the manifest records both session sets and the per-case pairing digest;
* a confirmation-rejected selected label is dropped, never replaced or re-selected.

Among correct candidates: largest voting_key cluster by teacher sample count, then
the most frequent exact string, then shortest, then lexicographic. v3 command rows
rejected by serving policy, judged incorrect in pass 1 or rejected in pass 2 are
dropped with distinct audit actions; v3 empty targets are kept unchanged. Requests with no correct candidate are
dropped, never turned into empty targets. Leakage-rejected candidates do not reserve
a duplicate-request identity: hard leakage is filtered before the duplicate seen-set
is updated, and review-level leakage findings are written to
eval_leakage_review.jsonl.
"""
import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

from build_distill_dataset import eval_leakage, read_jsonl, read_quarantine, voting_key
from build_v4_pool import exclusion, load_controls, opaque_id, pool_population
from repair_distill_dataset import validate_command, validation_fingerprint
from whatisit_macos.local_recovery_worker import MACOS_PREFIX

ROOT = Path(__file__).resolve().parents[1]
CONFIRM_SAMPLE = 0.2
CONFIRM_SEED = 13
CONFIRM_BATCH_SIZE = 90
VERDICT_VALUES = {'correct', 'incorrect', 'unsure'}
VERDICT_CATEGORIES = {'linux_syntax', 'hallucinated_flag', 'wrong_tool',
                      'missed_constraint', 'wrong_operand', 'wrong_output', 'unsafe',
                      'should_abstain', 'not_a_command', 'other'}
CONTROL_EXPECTED = {'correct', 'incorrect'}
EVAL_SPLITS = ('dev', 'everyday', 'frozen', 'heldout')
BATCH_FILE = re.compile(r'^b\d{2}\.json$')
CASE_ID = re.compile(r'^c[0-9a-f]{12}$')
KEY_ID = re.compile(r'^k[0-9a-f]{12}$')
QUARANTINE_PATHS = {'quarantine_ids': 'data/distill/quarantine_ids.txt',
                    'roihu_full_quarantine_ids': 'data/distill/roihu_full_quarantine_ids.txt'}


def select(correct_counts):
    """Pick the training target from {command: teacher sample count} of judged-correct commands."""
    if not correct_counts:
        return None
    clusters = {}
    for command, count in correct_counts.items():
        clusters.setdefault(voting_key(command), Counter())[command] = count
    cluster = max(clusters.values(), key=lambda c: (sum(c.values()), -min(len(x) for x in c), min(c)))
    return min(cluster, key=lambda cmd: (-cluster[cmd], len(cmd), cmd))


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_sha256(value):
    """SHA-256 of a canonical JSON encoding, independent of dict insertion order."""
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def hash_json_files(directory, batches):
    directory = Path(directory)
    return {name: sha256_file(directory / f'{name}.json') for name in sorted(batches)}


def load_batches(directory, label, allow_manifest=False):
    """Load and structurally validate a directory of immutable bXX.json batch inputs."""
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError(f'{label} directory {directory} does not exist')
    files = sorted(path for path in directory.iterdir() if path.is_file())
    allowed = {path.name for path in files
               if BATCH_FILE.fullmatch(path.name) or (allow_manifest and path.name == 'manifest.json')}
    unexpected = sorted(path.name for path in files if path.name not in allowed)
    if unexpected:
        raise ValueError(f'{label} directory {directory} contains unexpected files: {unexpected}')
    paths = [path for path in files if BATCH_FILE.fullmatch(path.name)]
    if not paths:
        raise ValueError(f'{label} directory {directory} has no bXX.json files')
    expected_names = [f'b{index:02d}.json' for index in range(len(paths))]
    if [path.name for path in paths] != expected_names:
        raise ValueError(f'{label} directory {directory} batch files are not a complete '
                         f'sequence b00..b{len(paths) - 1:02d}: '
                         f'{[path.name for path in paths]}')
    batches, cases = {}, set()
    for path in paths:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or set(data) != {'batch', 'items'}:
            raise ValueError(f'{path}: batch must contain exactly batch and items')
        if data['batch'] != path.stem:
            raise ValueError(f'{path}: batch field {data["batch"]!r} does not match filename')
        items = data['items']
        if not isinstance(items, list) or not items:
            raise ValueError(f'{path}: items must be a non-empty list')
        for item in items:
            if not isinstance(item, dict) or set(item) != {'case', 'request', 'candidates'}:
                raise ValueError(f'{path}: item must contain exactly case, request, candidates')
            if not isinstance(item['case'], str) or not item['case'].strip():
                raise ValueError(f'{path}: case must be a non-empty string')
            if not CASE_ID.fullmatch(item['case']):
                raise ValueError(f'{path}: case {item["case"]!r} is not an opaque c+12hex id')
            if item['case'] in cases:
                raise ValueError(f'{path}: duplicate case id {item["case"]}')
            cases.add(item['case'])
            if not isinstance(item['request'], str) or not item['request'].strip():
                raise ValueError(f'{path}: request must be a non-empty string')
            candidates = item['candidates']
            if not isinstance(candidates, list) or not candidates:
                raise ValueError(f'{path}: candidates must be a non-empty list')
            keys = set()
            for candidate in candidates:
                if not isinstance(candidate, dict) or set(candidate) != {'key', 'command'}:
                    raise ValueError(f'{path}: candidate must contain exactly key and command')
                if not isinstance(candidate['key'], str) or not candidate['key'].strip():
                    raise ValueError(f'{path}: candidate key must be a non-empty string')
                if not KEY_ID.fullmatch(candidate['key']):
                    raise ValueError(f'{path}: candidate key {candidate["key"]!r} is not an '
                                     'opaque k+12hex id')
                if candidate['key'] in keys:
                    raise ValueError(f'{path}: duplicate candidate key {candidate["key"]}')
                keys.add(candidate['key'])
                if not isinstance(candidate['command'], str) or not candidate['command'].strip():
                    raise ValueError(f'{path}: candidate command must be a non-empty string')
        batches[data['batch']] = data
    return batches


def _valid_evidence(value):
    return isinstance(value, str) and bool(value.strip())


def load_verdicts(directory, batches, keymap=None, controls=None, require_keys=None,
                  case_judges=None, contested=None):
    """Strictly load verdict files against their immutable batch inputs.

    Every batch must have exactly one file, every case must be present exactly once,
    every candidate key must be judged exactly once, and every verdict must obey the
    rubric schema. Control verdicts must match their expected values. When
    ``case_judges`` is passed, it receives the judge identity of every judged case.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError(f'verdict directory {directory} does not exist')
    keymap = keymap or {}
    controls = controls or {}
    contested = set(contested or ())
    if contested - set(controls):
        raise ValueError('contested controls are not in the controls map: '
                         f'{sorted(contested - set(controls))[:5]}')
    expected_files = sorted(f'{name}.json' for name in batches)
    files = sorted(path.name for path in directory.iterdir() if path.is_file())
    unexpected = [name for name in files if name not in expected_files]
    if unexpected:
        raise ValueError(f'verdict directory {directory} contains unexpected files: {unexpected}')
    missing_files = [name for name in expected_files if name not in files]
    if missing_files:
        raise ValueError(f'verdict directory {directory} is missing batches: {missing_files}')

    verdicts, sources = {}, {}
    for name in sorted(batches):
        batch = batches[name]
        path = directory / f'{name}.json'
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or set(data) != {'batch', 'judge', 'cases'}:
            raise ValueError(f'{path}: verdict file must contain exactly batch, judge, cases')
        if data['batch'] != name:
            raise ValueError(f'{path}: batch field {data["batch"]!r} does not match filename')
        if not isinstance(data['judge'], str) or not data['judge'].strip():
            raise ValueError(f'{path}: judge identity must be a non-empty string')
        cases = data['cases']
        if not isinstance(cases, list) or not cases:
            raise ValueError(f'{path}: cases must be a non-empty list')
        batch_cases = {item['case']: item for item in batch['items']}
        seen_cases = set()
        for case in cases:
            if not isinstance(case, dict) or set(case) != {'case', 'verdicts'}:
                raise ValueError(f'{path}: case must contain exactly case and verdicts')
            case_id = case['case']
            if case_id not in batch_cases:
                raise ValueError(f'{path}: unknown or misplaced case {case_id!r}')
            if case_id in seen_cases:
                raise ValueError(f'{path}: case {case_id} judged twice')
            seen_cases.add(case_id)
            if case_judges is not None:
                case_judges[case_id] = data['judge']
            expected = {candidate['key']: candidate['command']
                        for candidate in batch_cases[case_id]['candidates']}
            entries = case['verdicts']
            if not isinstance(entries, list) or not entries:
                raise ValueError(f'{path}: case {case_id} has no verdicts')
            seen_keys = set()
            for entry in entries:
                if not isinstance(entry, dict) or set(entry) != {'key', 'verdict', 'category',
                                                                 'evidence'}:
                    raise ValueError(f'{path}: verdict must contain exactly key, verdict, '
                                     'category, evidence')
                key = entry['key']
                if key not in expected:
                    raise ValueError(f'{path}: case {case_id} has misplaced or unknown key {key!r}')
                if key in seen_keys:
                    raise ValueError(f'{path}: key {key} judged twice in case {case_id}')
                seen_keys.add(key)
                if key in verdicts:
                    raise ValueError(f'{key}: judged in both {sources[key]} and {name}')
                verdict = entry['verdict']
                if verdict not in VERDICT_VALUES:
                    raise ValueError(f'{path}: key {key} has invalid verdict {verdict!r}')
                category = entry['category']
                if verdict == 'incorrect':
                    if category not in VERDICT_CATEGORIES:
                        raise ValueError(f'{path}: key {key} incorrect verdict needs a valid category')
                elif category is not None:
                    raise ValueError(f'{path}: key {key} {verdict} verdict must have null category')
                if not _valid_evidence(entry['evidence']):
                    raise ValueError(f'{path}: key {key} needs non-empty evidence')
                if key in keymap:
                    if keymap[key].get('case') != case_id:
                        raise ValueError(f'{path}: key {key} belongs to case '
                                         f'{keymap[key].get("case")!r}, not {case_id!r}')
                    if keymap[key]['command'] != expected[key]:
                        raise ValueError(f'{path}: key {key} command does not match keymap')
                elif key in controls:
                    if controls[key].get('case') != case_id:
                        raise ValueError(f'{path}: control {key} belongs to case '
                                         f'{controls[key].get("case")!r}, not {case_id!r}')
                    if controls[key]['command'] != expected[key]:
                        raise ValueError(f'{path}: control {key} command does not match controls map')
                else:
                    raise ValueError(f'{path}: key {key} is not in the keymap or controls map')
                verdicts[key] = verdict
                sources[key] = name
            missing_keys = set(expected) - seen_keys
            if missing_keys:
                raise ValueError(f'{path}: case {case_id} is missing verdicts for '
                                 f'{sorted(missing_keys)}')
        missing_cases = set(batch_cases) - seen_cases
        if missing_cases:
            raise ValueError(f'{path}: missing verdicts for cases {sorted(missing_cases)}')

    if require_keys is not None:
        missing = sorted(set(require_keys) - set(verdicts))
        extra = sorted(set(verdicts) - set(require_keys))
        if missing:
            raise ValueError(f'{len(missing)} required candidates have no verdict: {missing[:5]}')
        if extra:
            raise ValueError(f'{len(extra)} verdicts are outside the required candidate set: '
                             f'{extra[:5]}')
    for key, control in controls.items():
        if key not in verdicts:
            raise ValueError(f'control {key} has no verdict')
        if key in contested:
            continue
        if verdicts[key] != control['expected']:
            raise ValueError(f'control {key} expected {control["expected"]!r}, judge said '
                             f'{verdicts[key]!r}; re-judge the batch with a fresh judge')
    return verdicts


def _request_for_rid(group, rid, raw, v3_requests):
    if group == 'v3_kept':
        if rid not in v3_requests:
            raise ValueError(f'{rid}: v3 request is missing')
        request = v3_requests[rid]['request']
        path = v3_requests[rid].get('path')
        if path is not None:
            request += '\nExplicit inputs: ' + json.dumps({'path': path}, ensure_ascii=False)
        return request
    if group == 'no_majority':
        if rid not in raw:
            raise ValueError(f'{rid}: raw teacher samples are missing')
        request = raw[rid]['request']
        if raw[rid].get('path') is not None:
            request += '\nExplicit inputs: ' + json.dumps({'path': raw[rid]['path']}, ensure_ascii=False)
        return request
    raise ValueError(f'{rid}: unknown keymap group {group!r}')


def verify_keymap(keymap, v3, raw, effective, v3_requests=None):
    """Bind keymap entries to immutable v3/raw inputs, including candidate frequencies."""
    v3_targets = {row['id']: row['messages'][-1]['content'] for row in v3}
    v3_ids = set(v3_targets)
    by_rid, case_owners = {}, {}
    for key, entry in keymap.items():
        if not isinstance(entry, dict) or set(entry) != {'case', 'group', 'rid', 'command', 'count'}:
            raise ValueError(f'{key}: keymap entry must contain case, group, rid, command, count')
        if entry['group'] not in ('v3_kept', 'no_majority'):
            raise ValueError(f'{key}: unknown keymap group {entry["group"]!r}')
        if not isinstance(entry['case'], str) or not entry['case'].strip():
            raise ValueError(f'{key}: keymap case must be a non-empty string')
        if not isinstance(entry['rid'], str) or not entry['rid'].strip():
            raise ValueError(f'{key}: keymap rid must be a non-empty string')
        if not isinstance(entry['command'], str) or not entry['command'].strip():
            raise ValueError(f'{key}: keymap command must be a non-empty string')
        if not isinstance(entry['count'], int) or entry['count'] < 1:
            raise ValueError(f'{key}: keymap count must be a positive integer')
        owner = (entry['group'], entry['rid'])
        if entry['case'] in case_owners and case_owners[entry['case']] != owner:
            raise ValueError(f'{key}: case {entry["case"]} is shared by different items')
        case_owners[entry['case']] = owner
        by_rid.setdefault(owner, []).append((key, entry))
    for (group, rid), candidates in by_rid.items():
        cases = {entry['case'] for _, entry in candidates}
        if len(cases) != 1:
            raise ValueError(f'{rid}: keymap candidates disagree on case id {sorted(cases)}')
        commands = [entry['command'] for _, entry in candidates]
        if len(set(commands)) != len(commands):
            raise ValueError(f'{rid}: duplicate keymap candidate command')
        if group == 'v3_kept':
            if rid not in v3_targets:
                raise ValueError(f'{rid}: v3_kept keymap rid is not a v3 row')
            if not v3_targets[rid]:
                raise ValueError(f'{rid}: v3_kept keymap rid has an empty target')
            if len(candidates) != 1 or commands[0] != v3_targets[rid]:
                raise ValueError(f'{rid}: v3_kept keymap candidate does not match the training target')
            if candidates[0][1]['count'] != 1:
                raise ValueError(f'{rid}: v3_kept candidate count must be 1')
        else:
            if rid in v3_ids:
                raise ValueError(f'{rid}: no_majority keymap rid is also a v3 row')
            if rid not in raw:
                raise ValueError(f'{rid}: no_majority keymap rid is missing from raw samples')
            request = raw[rid]['request']
            counts = Counter(effective(sample, request, raw[rid].get('path')) for sample in raw[rid]['samples'])
            for key, entry in candidates:
                command = entry['command']
                if command not in counts:
                    raise ValueError(f'{rid}: keymap candidate {key} command {command!r} is not '
                                     f'in fresh counts')
                if counts[command] != entry['count']:
                    raise ValueError(f'{rid}: candidate {key} frequency changed: keymap says '
                                     f'{entry["count"]}, fresh samples say {counts[command]}')
    for row in v3:
        target = row['messages'][-1]['content']
        if target:
            if v3_requests is not None:
                record = v3_requests[row['id']]
                try:
                    validate_command(row['id'], target, record['request'], record.get('path'))
                except ValueError:
                    continue
            candidates = by_rid.get(('v3_kept', row['id']), [])
            if len(candidates) != 1:
                raise ValueError(f'{row["id"]}: v3 row with a target must have exactly one '
                                 f'keymap candidate')
    return by_rid


def verify_validation(manifest):
    if manifest.get('validation') != validation_fingerprint():
        raise ValueError('validation policy or environment changed; regenerate pool and confirmation')


def verify_population(keymap, manifest, corpus, raw, v3, v3_requests, effective,
                      validate=None):
    validate = validate or validate_command
    items, warnings, excluded = pool_population(corpus, raw, v3, v3_requests,
                                                effective, validate)
    expected = {}
    seed = manifest['control_seed']
    for item in items:
        for command, count in item['candidates']:
            key = opaque_id('k', seed, item['group'], item['rid'], command)
            expected[key] = {'case': opaque_id('c', seed, item['group'], item['rid']),
                             'group': item['group'], 'rid': item['rid'],
                             'command': command, 'count': count}
    for key in keymap.keys() & expected.keys():
        if not isinstance(keymap[key], dict) or keymap[key].get('count') != expected[key]['count']:
            raise ValueError(f'{key}: candidate frequency changed')
    if keymap != expected:
        raise ValueError('keymap does not match the complete policy-accepted population; rebuild pool')
    if manifest.get('excluded_candidates') != excluded or manifest.get('warnings') != warnings:
        raise ValueError('pool policy exclusions do not match current validation; rebuild pool')
    v3_ids = {row['id'] for row in v3}
    v3_items = sum(item['group'] == 'v3_kept' for item in items)
    counts = {'v3_rows': len(v3), 'v3_items': v3_items, 'v3_candidates': v3_items,
              'v3_policy_rejected': sum(entry['rid'] in v3_ids for entry in excluded),
              'no_majority_considered': len(set(corpus) - v3_ids),
              'no_majority_with_candidates': len(items) - v3_items,
              'excluded_candidates': len(excluded), 'items': len(items),
              'candidates': len(expected)}
    if any(manifest['counts'].get(name) != count for name, count in counts.items()):
        raise ValueError('pool manifest population count does not match current validation')


def verify_pool_manifest(pool_manifest, keymap, controls_map, paths, pool_batches=None):
    verify_validation(pool_manifest)
    required = {'inputs_sha256', 'artifacts_sha256', 'counts', 'batch_size',
                'control_seed', 'controls_per_batch', 'controls_by_batch'}
    missing = required - set(pool_manifest)
    if missing:
        raise ValueError(f'pool manifest is missing {sorted(missing)}; rebuild the pool')
    expected_inputs = {name: sha256_file(path) for name, path in paths.items()}
    if pool_manifest['inputs_sha256'] != expected_inputs:
        raise ValueError('pool input digests do not match the current immutable inputs; '
                         'the pool is stale or an input changed')
    artifacts = pool_manifest['artifacts_sha256']
    for name in ('keymap', 'director_map', 'controls_map'):
        if name not in artifacts:
            raise ValueError(f'pool manifest has no {name} digest; rebuild the pool')
    counts = pool_manifest['counts']
    if counts.get('candidates') != len(keymap):
        raise ValueError('pool manifest candidate count does not match keymap')
    if pool_batches is not None:
        if counts.get('batches') != len(pool_batches):
            raise ValueError('pool manifest batch count does not match the batch files')
        real_cases = ({item['case'] for batch in pool_batches.values() for item in batch['items']}
                      - {entry['case'] for entry in controls_map.values()})
        if counts.get('items') != len(real_cases):
            raise ValueError('pool manifest item count does not match the batch files')
        v3_items = sum(1 for entry in keymap.values() if entry['group'] == 'v3_kept')
        if counts.get('v3_items') != v3_items:
            raise ValueError('pool manifest v3 item count does not match keymap')
        no_majority_items = len({entry['rid'] for entry in keymap.values()
                                 if entry['group'] == 'no_majority'})
        if counts.get('no_majority_with_candidates') != no_majority_items:
            raise ValueError('pool manifest no-majority count does not match keymap')
    if counts.get('controls_total') != len(controls_map):
        raise ValueError('pool manifest control count does not match controls map')
    if counts.get('controls_injected') != len(controls_map):
        raise ValueError('pool manifest says controls were not all injected')
    if counts.get('controls_total', 0) < 1:
        raise ValueError('pool has no controls; refusing to build an unverified dataset')
    if pool_manifest['batch_size'] < 1:
        raise ValueError('pool batch_size must be positive')
    if pool_manifest['controls_per_batch'] < 2:
        raise ValueError('pool controls_per_batch must be >= 2')
    if not isinstance(pool_manifest['control_seed'], int):
        raise ValueError('pool control_seed must be an integer')


def load_adjudication(path, controls_map, controls_sha):
    """Return the contested control keys from an adjudication pinned to this controls map."""
    data = _load_json(Path(path), 'control adjudication')
    if data.get('inputs_sha256', {}).get('controls-map.json') != controls_sha:
        raise ValueError('control adjudication is stale for this controls map')
    keys = data.get('contested_keys')
    if not isinstance(keys, list) or not all(isinstance(key, str) for key in keys):
        raise ValueError('control adjudication contested_keys must be a list of strings')
    if not set(keys) <= set(controls_map):
        raise ValueError('control adjudication names keys outside the controls map')
    return set(keys)


def verify_control_maps(controls, controls_map, director_map, keymap, control_seed):
    """Recompute every control entry and the director view from controls.jsonl.

    Digest checks accept a controls map, pool manifest and verdicts that were all
    rewritten together; this reconstruction pins each control's expected verdict,
    command, request, provenance and deterministic opaque ids to the tracked
    controls source, and the director map to the keymap and controls map.
    """
    expected = {}
    for control in controls:
        case = opaque_id('c', control_seed, 'control', control['source'], control['key'])
        key = opaque_id('k', control_seed, 'control', control['source'], control['key'])
        if key in expected or key in keymap:
            raise ValueError(f'control {control["key"]}: key {key} collides with another '
                             'candidate')
        entry = {'case': case, 'expected': control['expected'], 'source': control['source'],
                 'request': control['request'], 'command': control['command'],
                 'origin_case': control['case'], 'origin_key': control['key']}
        if 'provenance' in control:
            entry['provenance'] = control['provenance']
        expected[key] = entry
    for key in sorted(set(expected) | set(controls_map)):
        if expected.get(key) != controls_map.get(key):
            raise ValueError(f'control {key} does not recompute from controls.jsonl '
                             f'({controls_map.get(key)!r}); rebuild the pool')
    expected_director = {}
    for key, entry in keymap.items():
        case_entry = expected_director.setdefault(entry['case'], {
            'kind': 'real', 'group': entry['group'], 'rid': entry['rid'], 'candidates': []})
        case_entry['candidates'].append({'key': key, 'command': entry['command']})
    for key, entry in controls_map.items():
        if entry['case'] in expected_director:
            raise ValueError(f'control {key}: case {entry["case"]} collides with a real case')
        expected_director[entry['case']] = {
            'kind': 'control', 'candidates': [{'key': key, 'command': entry['command']}],
            'expected': entry['expected'], 'source': entry['source'],
            'request': entry['request'], 'origin_case': entry['origin_case'],
            'origin_key': entry['origin_key']}
        if 'provenance' in entry:
            expected_director[entry['case']]['provenance'] = entry['provenance']
    for entry in expected_director.values():
        entry['candidates'].sort(key=lambda candidate: candidate['key'])
    if director_map != expected_director:
        raise ValueError('director map does not match the keymap and controls map; '
                         'rebuild the pool')


def verify_pool_batches(pool_batches, keymap, controls_map, v3, raw, v3_requests, effective):
    keymap_by_case, keymap_keys = {}, set()
    for key, entry in keymap.items():
        keymap_by_case.setdefault(entry['case'], []).append((key, entry))
        keymap_keys.add(key)
    controls_by_case = {entry['case']: (key, entry) for key, entry in controls_map.items()}
    if len(controls_by_case) != len(controls_map):
        raise ValueError('controls map has duplicate case ids')
    seen_keys, seen_cases = set(), set()
    controls_by_batch = {}
    for name, batch in pool_batches.items():
        summary = Counter()
        for item in batch['items']:
            case = item['case']
            if case in seen_cases:
                raise ValueError(f'{name}: case {case} appears in more than one pool item')
            seen_cases.add(case)
            if case in controls_by_case:
                control_key, control = controls_by_case[case]
                if item['request'] != control['request']:
                    raise ValueError(f'{name}: control {control_key} request changed')
                expected = [{'key': control_key, 'command': control['command']}]
                if item['candidates'] != expected:
                    raise ValueError(f'{name}: control {control_key} candidate changed')
                if control_key in seen_keys:
                    raise ValueError(f'{name}: control {control_key} appears twice')
                seen_keys.add(control_key)
                summary[control['expected']] += 1
                continue
            if case not in keymap_by_case:
                raise ValueError(f'{name}: case {case} is not in keymap or controls map')
            entries = sorted(keymap_by_case[case], key=lambda pair: pair[0])
            expected_candidates = [{'key': key, 'command': entry['command']}
                                   for key, entry in entries]
            if item['candidates'] != expected_candidates:
                raise ValueError(f'{name}: case {case} candidates do not match keymap')
            group = entries[0][1]['group']
            rid = entries[0][1]['rid']
            expected_request = _request_for_rid(group, rid, raw, v3_requests)
            if item['request'] != expected_request:
                raise ValueError(f'{name}: case {case} request does not match immutable input')
            for key, _ in entries:
                if key in seen_keys:
                    raise ValueError(f'{name}: key {key} appears twice')
                seen_keys.add(key)
        if not summary:
            raise ValueError(f'{name}: batch has no controls; refusing to accept it')
        if set(summary) != CONTROL_EXPECTED:
            raise ValueError(f'{name}: batch lacks one control of each polarity')
        controls_by_batch[name] = {'correct': summary['correct'],
                                   'incorrect': summary['incorrect']}
    missing = keymap_keys - seen_keys
    if missing:
        raise ValueError(f'pool batches are missing keymap candidates: {sorted(missing)[:5]}')
    missing_controls = set(controls_map) - seen_keys
    if missing_controls:
        raise ValueError(f'pool batches are missing controls: {sorted(missing_controls)[:5]}')
    return controls_by_batch


def selected_items(keymap, verdicts, raw, v3_requests, effective, validate=None):
    """Re-derive the pass-1 selected labels in the same order used by make_v4_confirm."""
    validate = validate or validate_command
    correct = {key for key, verdict in verdicts.items() if verdict == 'correct'}
    by_rid = {}
    for key, entry in keymap.items():
        by_rid.setdefault((entry['group'], entry['rid']), []).append((key, entry))
    items = []
    for (group, rid), candidates in sorted(by_rid.items(), key=lambda pair: pair[0][1]):
        candidates.sort(key=lambda pair: pair[0])
        cases = {entry['case'] for _, entry in candidates}
        if len(cases) != 1:
            raise ValueError(f'{rid}: candidates disagree on case id')
        _request_for_rid(group, rid, raw, v3_requests)
        record = v3_requests[rid] if group == 'v3_kept' else raw[rid]
        for _, entry in candidates:
            validate(rid, entry['command'], record['request'], record.get('path'))
        if group == 'v3_kept':
            chosen = any(key in correct for key, _ in candidates)
            request = _request_for_rid(group, rid, raw, v3_requests)
        elif group == 'no_majority':
            if rid not in raw:
                raise ValueError(f'{rid}: raw samples missing for selected-item derivation')
            request = raw[rid]['request']
            counts = Counter(effective(sample, request, raw[rid].get('path')) for sample in raw[rid]['samples'])
            for key, entry in candidates:
                if entry['command'] not in counts:
                    raise ValueError(f'{rid}: keymap candidate {key} command is not in fresh counts')
                if counts[entry['command']] != entry['count']:
                    raise ValueError(f'{rid}: candidate {key} frequency changed')
            chosen = select({entry['command']: counts[entry['command']]
                             for key, entry in candidates if key in correct}) is not None
        else:
            raise ValueError(f'{rid}: unknown keymap group {group!r}')
        if chosen:
            request = _request_for_rid(group, rid, raw, v3_requests)
            items.append({'case': next(iter(cases)), 'group': group, 'rid': rid,
                          'request': request,
                          'candidates': [{'key': key, 'command': entry['command']}
                                         for key, entry in candidates]})
    items.sort(key=lambda item: item['rid'])
    if len({item['case'] for item in items}) != len(items):
        raise ValueError('selected labels have duplicate case ids')
    return items


def sample_record(items):
    return [{'case': item['case'], 'rid': item['rid'], 'group': item['group'],
             'keys': [candidate['key'] for candidate in item['candidates']]}
            for item in items]


def expected_confirm_batches(selected, sample, seed, batch_size):
    if not selected:
        raise ValueError('no selected labels to confirm')
    if not 0 < sample <= 1:
        raise ValueError('confirm sample must be in (0, 1]')
    if batch_size < 1:
        raise ValueError('confirm batch_size must be >= 1')
    count = round(len(selected) * sample)
    if count < 1:
        raise ValueError(f'confirmation sample is empty: {len(selected)} selected labels at '
                         f'sample={sample}; at least one label must be confirmed')
    picked = random.Random(seed).sample(selected, count)
    picked.sort(key=lambda item: item['case'])
    public = [{field: item[field] for field in ('case', 'request', 'candidates')}
              for item in picked]
    batches = {}
    for index in range(0, len(public), batch_size):
        name = f'b{index // batch_size:02d}'
        batches[name] = {'batch': name, 'items': public[index:index + batch_size]}
    return batches, picked


def _load_json(path, label):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f'{label} file {path} does not exist')
    return json.loads(path.read_text())


def build(keymap, verdict_dir, confirm_batches_dir, confirm_verdicts_dir, out_dir,
          pool_dir=None, sample=CONFIRM_SAMPLE, seed=CONFIRM_SEED, adjudication=None):
    pool_dir = Path(pool_dir) if pool_dir is not None else Path(verdict_dir).parent / 'pool'
    pool_manifest = _load_json(pool_dir / 'manifest.json', 'pool manifest')
    pool_keymap = _load_json(pool_dir / 'keymap.json', 'pool keymap')
    if pool_keymap != keymap:
        raise ValueError('passed keymap does not match the pool keymap; refusing to build')
    controls_map = _load_json(pool_dir / 'controls-map.json', 'pool controls map')
    director_map = _load_json(pool_dir / 'director-map.json', 'pool director map')
    if set(controls_map) & set(keymap):
        raise ValueError('controls map and keymap share candidate keys')
    pool_batches = load_batches(pool_dir / 'batches', 'pool batches')
    expected_artifacts = {
        'keymap': sha256_file(pool_dir / 'keymap.json'),
        'controls_map': sha256_file(pool_dir / 'controls-map.json'),
        'director_map': sha256_file(pool_dir / 'director-map.json'),
        'batches': hash_json_files(pool_dir / 'batches', pool_batches),
    }
    if pool_manifest.get('artifacts_sha256') != expected_artifacts:
        raise ValueError('pool artifacts do not match the pool manifest; rebuild the pool')
    contested, adjudication_sha = set(), None
    if adjudication is not None:
        adjudication_sha = sha256_file(Path(adjudication))
        contested = load_adjudication(adjudication, controls_map, expected_artifacts['controls_map'])

    corpus_path = ROOT / 'data/corpus/requests.jsonl'
    raw_path = ROOT / 'data/teacher/roihu_full_raw_samples.jsonl'
    v3_train_path = ROOT / 'data/distill/stage2-v3/train.jsonl'
    v3_requests_path = ROOT / 'data/distill/stage2-v3/requests.jsonl'
    controls_path = ROOT / 'data/distill/stage2-v4/judge/controls.jsonl'
    paths = {'corpus': corpus_path, 'raw_samples': raw_path, 'v3_train': v3_train_path,
             'v3_requests': v3_requests_path, 'controls': controls_path}
    quarantine_paths = {name: ROOT / relative for name, relative in QUARANTINE_PATHS.items()}
    verify_pool_manifest(pool_manifest, keymap, controls_map, paths,
                         pool_batches=pool_batches)
    verify_control_maps(load_controls(controls_path), controls_map, director_map, keymap,
                        pool_manifest['control_seed'])

    corpus = {row['id']: row for row in read_jsonl(corpus_path)}
    raw = {row['id']: row for row in read_jsonl(raw_path)}
    for rid in sorted(corpus.keys() & raw.keys()):
        if corpus[rid]['request'] != raw[rid]['request']:
            raise ValueError(f'{rid}: corpus and raw teacher requests differ')
    v3 = read_jsonl(v3_train_path)
    v3_requests = {row['id']: row for row in read_jsonl(v3_requests_path)}
    from score_teacher_eval import effective_command  # lazy: module imports without upstream whatisit

    verify_population(keymap, pool_manifest, corpus, raw, v3, v3_requests, effective_command)
    by_rid = verify_keymap(keymap, v3, raw, effective_command, v3_requests)
    controls_by_batch = verify_pool_batches(pool_batches, keymap, controls_map, v3, raw,
                                            v3_requests, effective_command)
    if controls_by_batch != pool_manifest['controls_by_batch']:
        raise ValueError('pool control coverage summary does not match the pool batches')

    pass1_judges = {}
    verdicts = load_verdicts(verdict_dir, pool_batches, keymap=keymap,
                             controls=controls_map,
                             require_keys=set(keymap) | set(controls_map),
                             case_judges=pass1_judges, contested=contested)
    selected = selected_items(keymap, verdicts, raw, v3_requests, effective_command)
    expected_batches, picked = expected_confirm_batches(selected, sample, seed,
                                                        CONFIRM_BATCH_SIZE)
    confirm_batches = load_batches(confirm_batches_dir, 'confirm batches', allow_manifest=True)
    if set(confirm_batches) != set(expected_batches):
        raise ValueError('confirm batch coverage does not match the deterministic sample')
    for name, expected in expected_batches.items():
        if confirm_batches[name] != expected:
            raise ValueError(f'confirm batch {name} does not match the deterministic sample')
    confirm_manifest = _load_json(Path(confirm_batches_dir) / 'manifest.json',
                                  'confirm manifest')
    confirm_fields = {'selected_total', 'sampled', 'sample', 'seed', 'batch_size',
                      'selected', 'sample_cases', 'inputs_sha256', 'artifacts_sha256', 'validation'}
    if set(confirm_manifest) != confirm_fields:
        raise ValueError('confirm manifest does not contain exactly '
                         f'{sorted(confirm_fields)}; re-run make_v4_confirm.py')
    verify_validation(confirm_manifest)
    expected_sample = sample_record(picked)
    expected_selected = sample_record(selected)
    checks = {
        'selected_total': len(selected), 'sampled': len(picked),
        'sample': sample, 'seed': seed, 'batch_size': CONFIRM_BATCH_SIZE,
    }
    for field, expected in checks.items():
        if confirm_manifest.get(field) != expected:
            raise ValueError(f'confirm manifest {field} is {confirm_manifest.get(field)!r}, '
                             f'expected {expected!r}')
    if confirm_manifest.get('selected') != expected_selected:
        raise ValueError('confirm manifest selected labels do not match the pass-1 selection')
    if confirm_manifest.get('sample_cases') != expected_sample:
        raise ValueError('confirm manifest sample does not match the deterministic sample')
    expected_inputs = {
        'pool_manifest': sha256_file(pool_dir / 'manifest.json'),
        'keymap': sha256_file(pool_dir / 'keymap.json'),
        'raw_samples': sha256_file(raw_path),
        'v3_requests': sha256_file(v3_requests_path),
        'pass1_verdicts': canonical_sha256(verdicts),
        'pass1_verdict_files': hash_json_files(verdict_dir, pool_batches),
        'quarantine_ids': sha256_file(quarantine_paths['quarantine_ids']),
        'roihu_full_quarantine_ids': sha256_file(
            quarantine_paths['roihu_full_quarantine_ids']),
        'control_adjudication': adjudication_sha,
    }
    if confirm_manifest.get('inputs_sha256') != expected_inputs:
        raise ValueError('confirm manifest is bound to different inputs; '
                         're-run make_v4_confirm.py')
    expected_artifacts = hash_json_files(confirm_batches_dir, confirm_batches)
    if confirm_manifest.get('artifacts_sha256') != expected_artifacts:
        raise ValueError('confirm batch outputs do not match the confirm manifest; '
                         'confirm data is stale or tampered')
    sample_keys = {candidate['key'] for item in picked for candidate in item['candidates']}
    pass2_judges = {}
    confirmed = load_verdicts(confirm_verdicts_dir, confirm_batches, keymap=keymap,
                              require_keys=sample_keys, case_judges=pass2_judges)
    sample_cases = [item['case'] for item in picked]
    reused = [case for case in sample_cases if pass1_judges[case] == pass2_judges[case]]
    if reused:
        raise ValueError(f'{len(reused)} sampled cases were judged by the same identity in '
                         f'pass 1 and pass 2, e.g. {reused[0]} by '
                         f'{pass1_judges[reused[0]]!r}; pass 2 requires a fresh judge session')

    correct = {key for key, verdict in verdicts.items() if verdict == 'correct'}
    rejected = {key for key, verdict in confirmed.items() if verdict != 'correct'}
    rows, audit = [], []
    for row in v3:
        target = row['messages'][-1]['content']
        keys = [key for key, _ in by_rid.get(('v3_kept', row['id']), [])]
        if target:
            record = v3_requests[row['id']]
            try:
                validate_command(row['id'], target, record['request'], record.get('path'))
            except ValueError as exc:
                audit.append({'id': row['id'], 'action': 'drop_v3_policy_rejected',
                              'target': target,
                              'reason': exclusion(row['id'], target, exc)['reason']})
                continue
            target_keys = [key for key in keys if keymap[key]['command'] == target]
            if len(target_keys) != 1:
                raise ValueError(f'{row["id"]}: v3 target is not bound to exactly one keymap key')
            key = target_keys[0]
            if key not in correct:
                audit.append({'id': row['id'], 'action': 'drop_v3_first_pass_incorrect',
                              'target': target})
                continue
            if key in rejected:
                audit.append({'id': row['id'], 'action': 'drop_v3_second_pass_rejected',
                              'target': target})
                continue
        rows.append(row)
        audit.append({'id': row['id'], 'action': 'keep_v3'})

    quarantine = read_quarantine(quarantine_paths['roihu_full_quarantine_ids'], set(corpus))
    quarantine.update(read_quarantine(quarantine_paths['quarantine_ids'], set(corpus)))
    kept_ids = {row['id'] for row in rows}
    seen = {}
    for record in read_jsonl(ROOT / 'data/distill/stage2-v3/requests.jsonl'):
        if record['id'] in kept_ids:
            seen.setdefault(' '.join(record['request'].casefold().split()), record['id'])

    candidates, leaks = [], []
    for (group, rid), cands in sorted(by_rid.items(), key=lambda pair: pair[0][1]):
        if group != 'no_majority':
            continue
        request = raw[rid]['request']
        counts = Counter(effective_command(sample, request, raw[rid].get('path')) for sample in raw[rid]['samples'])
        for key, entry in cands:
            command = entry['command']
            if command not in counts:
                raise ValueError(f'{rid}: keymap candidate {key} command {command!r} is not in '
                                 f'fresh counts')
            if counts[command] != entry['count']:
                raise ValueError(f'{rid}: candidate {key} frequency changed')
        target = select({command: counts[command]
                         for key, command in [(key, entry['command']) for key, entry in cands]
                         if key in correct})
        if target is None:
            audit.append({'id': rid, 'action': 'drop_no_correct'})
            continue
        if rid in quarantine:
            audit.append({'id': rid, 'action': 'drop_quarantine'})
            continue
        target_keys = [key for key, entry in cands if entry['command'] == target]
        if any(key in rejected for key in target_keys):
            audit.append({'id': rid, 'action': 'drop_second_pass_rejected'})
            continue
        if corpus[rid]['request'] != request:
            raise ValueError(f'{rid}: corpus and raw request differ')
        validate_command(rid, target, request, raw[rid].get('path'))
        norm = ' '.join(request.casefold().split())
        row = {'id': rid, 'source_id': rid, 'messages': [
            {'role': 'system', 'content': v3[0]['messages'][0]['content']},
            {'role': 'user', 'content': MACOS_PREFIX +
             _request_for_rid(group, rid, raw, v3_requests)},
            {'role': 'assistant', 'content': target}]}
        candidates.append({'rid': rid, 'request': request, 'row': row, 'norm': norm})

    hard, review = eval_leakage([{'id': item['rid'], 'request': item['request']}
                                 for item in candidates],
                                [item['row'] for item in candidates], ROOT / 'eval')
    leaked = {rid for rid, _, _ in hard}
    leaks = [{'id': rid, 'kind': kind, 'split': split} for rid, kind, split in review]
    leaks.sort(key=lambda item: (item['id'], item['kind'], item['split']))
    for item in candidates:
        rid = item['rid']
        if rid in leaked:
            audit.append({'id': rid, 'action': 'drop_eval_leakage'})
            continue
        if item['norm'] in seen:
            audit.append({'id': rid, 'action': 'drop_duplicate_request',
                          'duplicate_of': seen[item['norm']]})
            continue
        seen[item['norm']] = rid
        rows.append(item['row'])
        audit.append({'id': rid, 'action': 'add_verified',
                      'target': item['row']['messages'][-1]['content']})

    out = Path(out_dir)
    if out.exists() and any(out.iterdir()):
        raise ValueError(f'output directory {out} is not empty; move it aside or delete it '
                         'before re-running')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'train.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    (out / 'audit.jsonl').write_text(''.join(json.dumps(entry) + '\n' for entry in audit))
    (out / 'eval_leakage_review.jsonl').write_text(
        ''.join(json.dumps(entry) + '\n' for entry in leaks))
    actions = dict(sorted(Counter(entry['action'] for entry in audit).items()))
    empty = sum(1 for row in rows if not row['messages'][-1]['content'])
    inputs = {
        'corpus': sha256_file(corpus_path), 'raw_samples': sha256_file(raw_path),
        'v3_train': sha256_file(v3_train_path),
        'v3_requests': sha256_file(v3_requests_path), 'controls': sha256_file(controls_path),
        'keymap': sha256_file(pool_dir / 'keymap.json'),
        'pool_manifest': sha256_file(pool_dir / 'manifest.json'),
        'pool_batches': hash_json_files(pool_dir / 'batches', pool_batches),
        'controls_map': sha256_file(pool_dir / 'controls-map.json'),
        'director_map': sha256_file(pool_dir / 'director-map.json'),
        'pass1_verdicts': canonical_sha256(verdicts),
        'pass1_verdict_files': hash_json_files(verdict_dir, pool_batches),
        'confirm_manifest': sha256_file(Path(confirm_batches_dir) / 'manifest.json'),
        'confirm_batches': hash_json_files(confirm_batches_dir, confirm_batches),
        'confirm_verdicts': canonical_sha256(confirmed),
        'confirm_verdict_files': hash_json_files(confirm_verdicts_dir, confirm_batches),
        'quarantine_ids': sha256_file(quarantine_paths['quarantine_ids']),
        'roihu_full_quarantine_ids': sha256_file(
            quarantine_paths['roihu_full_quarantine_ids']),
        'eval': {split: sha256_file(ROOT / 'eval' / f'{split}.jsonl')
                 for split in EVAL_SPLITS},
    }
    outputs = {'train': sha256_file(out / 'train.jsonl'),
               'audit': sha256_file(out / 'audit.jsonl'),
               'eval_leakage_review': sha256_file(out / 'eval_leakage_review.jsonl')}
    judge_sessions = {'pass1': sorted(set(pass1_judges.values())),
                      'pass2': sorted(set(pass2_judges.values())),
                      'case_pairs_sha256': canonical_sha256(
                          {case: [pass1_judges[case], pass2_judges[case]]
                           for case in sample_cases})}
    manifest = {'validation': validation_fingerprint(), 'rows': len(rows),
                'commands': len(rows) - empty, 'empty_targets': empty,
                'actions': actions, 'inputs_sha256': inputs, 'outputs_sha256': outputs,
                'train_sha256': outputs['train'],
                'judge_sessions': judge_sessions,
                'control_adjudication': {'sha256': adjudication_sha,
                                         'contested_keys': sorted(contested)},
                'eval_leakage_review': leaks,
                'eval_leakage_review_count': len(leaks)}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Build the verified v4 dataset from pass-1 and confirm verdicts.')
    parser.add_argument('keymap', type=Path)
    parser.add_argument('verdict_dir', type=Path)
    parser.add_argument('confirm_batches', type=Path)
    parser.add_argument('confirm_verdicts', type=Path)
    parser.add_argument('out_dir', type=Path)
    parser.add_argument('--adjudication', type=Path, default=None,
                        help='control adjudication JSON; contested controls are not gated')
    args = parser.parse_args()
    keymap = json.loads(args.keymap.read_text())
    print(json.dumps(build(keymap, args.verdict_dir, args.confirm_batches,
                           args.confirm_verdicts, args.out_dir,
                           pool_dir=args.keymap.parent,
                           adjudication=args.adjudication), indent=2))
