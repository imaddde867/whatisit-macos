"""Score a judge's calibration verdicts against the frozen key files.

The calibration set and its pass bar are built once by
``build_v4_judge_calibration.py`` and must not change after any verdict is read.
This tool validates the verdict schema and coverage, then reports whether the judge
cleared the bar.

Usage:
    score_v4_judge_calibration.py <calibration dir> <verdicts dir> <report path>
"""
import argparse
import hashlib
import json
from pathlib import Path

BATCHES = ('cal-controls', 'a0', 'a1')
VERDICTS = ('correct', 'incorrect', 'unsure')
UNSURE = 'unsure'


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


def load_verdicts(verdict_dir, expected_keys):
    directory = Path(verdict_dir)
    files = sorted(path.name for path in directory.iterdir() if path.is_file()) if directory.is_dir() else []
    wanted = sorted(f'{batch}.json' for batch in BATCHES)
    if files != wanted:
        raise SystemExit(f'verdict directory must hold exactly {wanted}; got {files}')
    verdicts, judges = {}, {}
    for name in BATCHES:
        data = load(directory / f'{name}.json', f'verdict {name}')
        if not isinstance(data, dict) or set(data) != {'batch', 'judge', 'cases'}:
            raise SystemExit(f'{name}.json: must contain exactly batch, judge, cases')
        if data['batch'] != name:
            raise SystemExit(f'{name}.json: batch field does not match filename')
        if not isinstance(data['judge'], str) or not data['judge'].strip():
            raise SystemExit(f'{name}.json: judge identity must be non-empty')
        judges[name] = data['judge']
        seen = set()
        for case in data['cases']:
            if not isinstance(case, dict) or set(case) != {'case', 'verdicts'}:
                raise SystemExit(f'{name}: case must contain exactly case, verdicts')
            for verdict in case['verdicts']:
                if not isinstance(verdict, dict) or set(verdict) != {'key', 'verdict', 'category', 'evidence'}:
                    raise SystemExit(f'{name}: verdict must contain key, verdict, category, evidence')
                if verdict['verdict'] not in VERDICTS:
                    raise SystemExit(f'{name}: bad verdict {verdict["verdict"]!r}')
                if verdict['verdict'] == 'incorrect':
                    if not isinstance(verdict['category'], str) or not verdict['category']:
                        raise SystemExit(f'{name}: incorrect verdict needs a category')
                elif verdict['category'] is not None:
                    raise SystemExit(f'{name}: category must be null for {verdict["verdict"]}')
                if not isinstance(verdict['evidence'], str) or not verdict['evidence'].strip():
                    raise SystemExit(f'{name}: evidence must be non-empty')
                if verdict['key'] in seen:
                    raise SystemExit(f'{name}: duplicate key {verdict["key"]}')
                seen.add(verdict['key'])
                verdicts[verdict['key']] = verdict['verdict']
        if seen != expected_keys[name]:
            missing = sorted(expected_keys[name] - seen)
            extra = sorted(seen - expected_keys[name])
            raise SystemExit(f'{name}: coverage mismatch; missing {missing[:5]}, extra {extra[:5]}')
    return verdicts, judges


def score(calibration_dir, verdict_dir, report_path):
    root = Path(calibration_dir)
    manifest = load(root / 'manifest.json', 'calibration manifest')
    control_keys = load(root / 'controls' / 'key.json', 'control key')
    agreement_keys = load(root / 'agreement' / 'key.json', 'agreement key')
    expected = {'cal-controls': set(control_keys)}
    for name in ('a0', 'a1'):
        batch = load(root / 'agreement' / 'batches' / f'{name}.json', f'agreement batch {name}')
        expected[name] = {candidate['key'] for item in batch['items'] for candidate in item['candidates']}
    if expected['a0'] | expected['a1'] != set(agreement_keys):
        raise SystemExit('agreement key file does not cover the agreement batches')

    verdicts, judges = load_verdicts(verdict_dir, expected)
    mismatches = []
    for key, control in sorted(control_keys.items()):
        if verdicts[key] != control['expected']:
            mismatches.append({'key': key, 'origin_key': control.get('origin_key'),
                               'expected': control['expected'], 'observed': verdicts[key],
                               'request': control['request'], 'command': control['command']})
    agree, false_accepts, false_rejects, unsure = 0, [], [], []
    for key, entry in sorted(agreement_keys.items()):
        observed = verdicts[key]
        if observed == UNSURE:
            unsure.append({'key': key, 'accepted': entry['accepted'], 'batch': entry['batch']})
        elif observed == entry['accepted']:
            agree += 1
        elif observed == 'correct':
            false_accepts.append({'key': key, 'batch': entry['batch'], 'accepted': entry['accepted']})
        else:
            false_rejects.append({'key': key, 'batch': entry['batch'], 'accepted': entry['accepted']})

    bar = manifest['pass_bar']
    passed = (not mismatches and agree >= bar['agreement_required']
              and len(false_accepts) <= bar['false_accept_max'] and len(unsure) <= bar['unsure_max'])
    report = {
        'calibration_manifest_sha256': sha256_file(root / 'manifest.json'),
        'judge_sessions': judges,
        'controls': {'total': len(control_keys), 'matched': len(control_keys) - len(mismatches),
                     'mismatches': mismatches},
        'agreement': {'total': len(agreement_keys), 'agree': agree,
                      'false_accepts': false_accepts, 'false_rejects': false_rejects,
                      'unsure': unsure},
        'pass_bar': bar,
        'pass': passed,
        'verdict_sha256': {name: sha256_file(Path(verdict_dir) / f'{name}.json') for name in BATCHES},
    }
    report_path = Path(report_path)
    if report_path.exists():
        raise SystemExit(f'report already exists: {report_path}')
    report_path.write_text(json.dumps(report, indent=1, sort_keys=True) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('calibration_dir')
    parser.add_argument('verdict_dir')
    parser.add_argument('report')
    args = parser.parse_args()
    report = score(args.calibration_dir, args.verdict_dir, args.report)
    print(json.dumps({'pass': report['pass'], 'controls': report['controls']['matched'],
                      'agree': report['agreement']['agree'], 'total': report['agreement']['total'],
                      'false_accepts': len(report['agreement']['false_accepts']),
                      'false_rejects': len(report['agreement']['false_rejects']),
                      'unsure': len(report['agreement']['unsure'])}, indent=1))


if __name__ == '__main__':
    main()
