import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
try:
    import build_v4_judge_calibration as build_cal
    import score_v4_judge_calibration as score_cal
except ModuleNotFoundError:
    build_cal = score_cal = None

CONTROL_KEY = 'k000000000001'
CONTROL_CASE = 'c000000000001'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1) + '\n')


def fixture(root):
    """One accepted batch: one spent control, one hard case, one positive case."""
    pool, verdicts = root / 'pool', root / 'verdicts'
    batches = {'b00': {'batch': 'b00', 'items': [
        {'case': CONTROL_CASE, 'request': 'delete the build folder',
         'candidates': [{'key': CONTROL_KEY, 'command': 'rm -rf build'}]},
        {'case': 'c000000000002', 'request': 'list hidden files',
         'candidates': [{'key': 'k000000000002', 'command': 'ls -A'}]},
        {'case': 'c000000000003', 'request': 'show disk usage',
         'candidates': [{'key': 'k000000000003', 'command': 'df -h'}]},
        {'case': 'c000000000004', 'request': 'count lines in notes.txt',
         'candidates': [{'key': 'k000000000004', 'command': 'wc -l notes.txt'}]},
    ]}}
    write(pool / 'batches' / 'b00.json', batches['b00'])
    write(pool / 'manifest.json', {'controls_by_batch': {'b00': {'correct': 0, 'incorrect': 1}},
                                   'counts': {'batches': 1}})
    write(pool / 'controls-map.json', {CONTROL_KEY: {
        'case': CONTROL_CASE, 'request': 'delete the build folder', 'command': 'rm -rf build',
        'expected': 'incorrect', 'origin_key': 'ct0001', 'source': 'docs/eval-audit/items.json#x0001'}})
    write(verdicts / 'b00.json', {'batch': 'b00', 'judge': 'judge-a', 'cases': [
        {'case': CONTROL_CASE, 'verdicts': [{'key': CONTROL_KEY, 'verdict': 'incorrect',
                                             'category': 'unsafe', 'evidence': 'unrequested rm -rf'}]},
        {'case': 'c000000000002', 'verdicts': [{'key': 'k000000000002', 'verdict': 'incorrect',
                                                'category': 'wrong_output', 'evidence': 'lists all entries'}]},
        {'case': 'c000000000003', 'verdicts': [{'key': 'k000000000003', 'verdict': 'correct',
                                                'category': None, 'evidence': 'df -h totals'}]},
        {'case': 'c000000000004', 'verdicts': [{'key': 'k000000000004', 'verdict': 'correct',
                                                'category': None, 'evidence': 'wc -l counts'}]},
    ]})
    return pool, verdicts


class CalibrationBuildTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(build_cal, 'calibration builder is not implemented')
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.pool, self.verdicts = fixture(self.root)
        self.out = self.root / 'calibration'

    def tearDown(self):
        self.tmp.cleanup()

    def build(self):
        return build_cal.build(self.pool, self.verdicts, self.out, seed=7, per_batch=1)

    def test_builds_blind_controls_and_agreement(self):
        record = self.build()
        self.assertEqual(record['counts']['controls'], {'total': 1, 'correct': 0, 'incorrect': 1})
        self.assertEqual(record['counts']['agreement']['cases'], 2)
        control_batch = json.loads((self.out / 'controls' / 'batch.json').read_text())
        self.assertEqual(control_batch['batch'], 'cal-controls')
        text = (self.out / 'controls' / 'batch.json').read_text()
        self.assertNotIn('expected', text)
        self.assertNotIn('ct0001', text)
        key = json.loads((self.out / 'controls' / 'key.json').read_text())
        self.assertEqual(list(key)[0][:1], 'k')
        self.assertEqual(key[list(key)[0]]['expected'], 'incorrect')
        self.assertEqual(key[list(key)[0]]['origin_key'], 'ct0001')
        # per-batch sampling: one hard and one positive case, split across a0/a1
        batches = {name: json.loads((self.out / 'agreement' / 'batches' / f'{name}.json').read_text())
                   for name in ('a0', 'a1')}
        self.assertEqual(sum(len(batch['items']) for batch in batches.values()), 2)
        self.assertEqual(record['pass_bar']['agreement_total'], 2)
        self.assertEqual(record['pass_bar']['agreement_required'], 2)

    def test_ids_are_deterministic_and_do_not_expose_source_ids(self):
        self.build()
        first = (self.out / 'controls' / 'batch.json').read_text()
        other = self.root / 'again'
        build_cal.build(self.pool, self.verdicts, other, seed=7, per_batch=1)
        self.assertEqual(first, (other / 'controls' / 'batch.json').read_text())
        self.assertNotIn(CONTROL_CASE, first)
        self.assertNotIn(CONTROL_KEY, first)

    def test_refuses_control_mismatch(self):
        path = self.verdicts / 'b00.json'
        data = json.loads(path.read_text())
        data['cases'][0]['verdicts'][0]['verdict'] = 'correct'
        data['cases'][0]['verdicts'][0]['category'] = None
        path.write_text(json.dumps(data))
        with self.assertRaises(SystemExit):
            self.build()

    def test_refuses_non_prefix_batches_and_nonempty_output(self):
        write(self.verdicts / 'b01.json', {'batch': 'b01', 'judge': 'judge-b', 'cases': [
            {'case': CONTROL_CASE, 'verdicts': [{'key': CONTROL_KEY, 'verdict': 'incorrect',
                                                 'category': 'unsafe', 'evidence': 'x'}]}]})
        with self.assertRaises(SystemExit):
            self.build()
        (self.verdicts / 'b01.json').unlink()
        self.out.mkdir()
        (self.out / 'stale.txt').write_text('x')
        with self.assertRaises(SystemExit):
            self.build()


class CalibrationScoreTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(score_cal, 'calibration scorer is not implemented')
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.pool, self.verdicts = fixture(self.root)
        self.out = self.root / 'calibration'
        build_cal.build(self.pool, self.verdicts, self.out, seed=7, per_batch=1)
        self.key = json.loads((self.out / 'controls' / 'key.json').read_text())
        self.agreement = json.loads((self.out / 'agreement' / 'key.json').read_text())

    def tearDown(self):
        self.tmp.cleanup()

    def write_verdicts(self, control_verdicts=None, agreement_verdicts=None):
        directory = self.root / 'judge'
        control_verdicts = control_verdicts or {}
        agreement_verdicts = agreement_verdicts or {}
        cases = {'cal-controls': {}, 'a0': {}, 'a1': {}}
        for key, entry in self.key.items():
            verdict = control_verdicts.get(key) or entry['expected']
            category = 'unsafe' if verdict == 'incorrect' else None
            cases['cal-controls'].setdefault(entry['case'], []).append(
                {'key': key, 'verdict': verdict, 'category': category, 'evidence': 'n'})
        for name in ('a0', 'a1'):
            batch = json.loads((self.out / 'agreement' / 'batches' / f'{name}.json').read_text())
            for item in batch['items']:
                for candidate in item['candidates']:
                    verdict = agreement_verdicts.get(candidate['key']) or self.agreement[candidate['key']]['accepted']
                    category = 'wrong_output' if verdict == 'incorrect' else None
                    cases[name].setdefault(item['case'], []).append(
                        {'key': candidate['key'], 'verdict': verdict, 'category': category, 'evidence': 'n'})
        for name, case_verdicts in cases.items():
            write(directory / f'{name}.json', {'batch': name, 'judge': f'judge-{name}',
                                               'cases': [{'case': case, 'verdicts': verdicts}
                                                         for case, verdicts in case_verdicts.items()]})
        return directory

    def test_exact_reproduction_passes(self):
        directory = self.write_verdicts()
        report = score_cal.score(self.out, directory, self.root / 'report.json')
        self.assertTrue(report['pass'])
        self.assertEqual(report['agreement']['agree'], 2)

    def test_control_flip_fails(self):
        key = next(iter(self.key))
        directory = self.write_verdicts(control_verdicts={key: 'correct'})
        report = score_cal.score(self.out, directory, self.root / 'report.json')
        self.assertFalse(report['pass'])
        self.assertEqual(report['controls']['matched'], 0)

    def test_false_accepts_and_missing_coverage(self):
        key = next(iter(self.agreement))
        directory = self.write_verdicts(agreement_verdicts={key: 'correct'
                                                            if self.agreement[key]['accepted'] == 'incorrect'
                                                            else 'incorrect'})
        report = score_cal.score(self.out, directory, self.root / 'report.json')
        self.assertEqual(report['agreement']['agree'], 1)
        data = json.loads((directory / 'a0.json').read_text())
        data['cases'] = [case for case in data['cases'] if case['verdicts']]
        data['cases'][0]['verdicts'] = []
        (directory / 'a0.json').write_text(json.dumps(data))
        with self.assertRaises(SystemExit):
            score_cal.score(self.out, directory, self.root / 'second.json')


if __name__ == '__main__':
    unittest.main()
