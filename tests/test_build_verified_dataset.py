import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(TESTS.parents[0] / 'tools'))

import build_verified_dataset as builder
from v4_campaign import Campaign, stub_effective, tree_bytes, write_jsonl
from whatisit_macos.local_recovery_worker import MACOS_PREFIX


class SelectTests(unittest.TestCase):
    def test_none_correct_gives_no_label(self):
        self.assertIsNone(builder.select({}))

    def test_largest_equivalence_cluster_wins_over_single_most_frequent_string(self):
        counts = {'ls -l -a': 1, 'ls -a -l': 1, 'ls -la .': 0, 'find . -maxdepth 1': 2}
        self.assertIn(builder.select(counts), {'ls -l -a', 'ls -a -l'})

    def test_within_cluster_most_frequent_then_shortest(self):
        self.assertEqual(builder.select({'stat -f %B a.txt': 2, 'stat  -f %B a.txt': 3}),
                         'stat  -f %B a.txt')
        self.assertEqual(builder.select({'wc -l a': 1, 'wc -l  a': 1}), 'wc -l a')


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.campaign = Campaign(self.root)
        self.pass1 = self.campaign.write_pass1(overrides={
            self.campaign.key('r00003', 'uname -a'): 'incorrect',
            self.campaign.key('r00009', 'whoami'): 'incorrect',
            self.campaign.key('r00006', 'ls -lt'): 'incorrect',
        })
        self.campaign.make_confirm(sample=1.0, seed=13)
        self.confirm = self.campaign.confirm_dir
        self.rejections = {
            self.campaign.key('r00004', 'pwd -P'): 'incorrect',
            self.campaign.key('r00011', 'cal'): 'incorrect',
        }
        self.pass2 = self.campaign.write_pass2(overrides=self.rejections)

    def build(self, out='out', **kwargs):
        kwargs.setdefault('sample', 1.0)
        kwargs.setdefault('seed', 13)
        return self.campaign.build_verified(self.root / out, **kwargs)

    def test_policy_change_requires_regeneration_before_build(self):
        path = self.campaign.pool / 'manifest.json'
        manifest = json.loads(path.read_text())
        manifest['validation'] = {'old': 'policy'}
        path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'validation policy or environment changed'):
            self.build()

    def test_happy_path_keeps_drops_and_adds_by_verdict(self):
        manifest = self.build()
        rows = builder.read_jsonl(self.root / 'out/train.jsonl')
        self.assertEqual([row['id'] for row in rows],
                         ['r00001', 'r00002', 'r00005', 'r00006', 'r00007',
                          'r00012', 'r00014'])
        self.assertEqual(rows[1]['messages'][-1]['content'], '')
        self.assertEqual(rows[0]['messages'][1]['content'],
                         'Show the Working  Directory')
        self.assertEqual(rows[3]['messages'][1]['content'],
                         MACOS_PREFIX + 'list files by size')
        self.assertEqual(rows[3]['messages'][-1]['content'], 'ls -lS')
        self.assertEqual((manifest['rows'], manifest['commands'], manifest['empty_targets']),
                         (7, 6, 1))
        self.assertEqual(manifest['actions'], {
            'add_verified': 4, 'drop_duplicate_request': 1, 'drop_eval_leakage': 1,
            'drop_no_correct': 1, 'drop_quarantine': 1, 'drop_second_pass_rejected': 1,
            'drop_v3_first_pass_incorrect': 1, 'drop_v3_second_pass_rejected': 1,
            'keep_v3': 3})
        audit = builder.read_jsonl(self.root / 'out/audit.jsonl')
        self.assertIn({'id': 'r00003', 'action': 'drop_v3_first_pass_incorrect',
                       'target': 'uname -a'}, audit)
        self.assertIn({'id': 'r00004', 'action': 'drop_v3_second_pass_rejected',
                       'target': 'pwd -P'}, audit)
        self.assertIn({'id': 'r00011', 'action': 'drop_second_pass_rejected'}, audit)
        self.assertIn({'id': 'r00008', 'action': 'drop_duplicate_request',
                       'duplicate_of': 'r00007'}, audit)
        self.assertIn({'id': 'r00010', 'action': 'drop_quarantine'}, audit)
        self.assertIn({'id': 'r00013', 'action': 'drop_eval_leakage'}, audit)

    def test_controls_are_graded_and_not_revealed_in_output(self):
        manifest = self.build()
        self.assertEqual(manifest['actions'].get('add_verified'), 4)
        for row in builder.read_jsonl(self.root / 'out/train.jsonl'):
            self.assertNotIn(row['id'], {control['case'] for control in
                                         self.campaign.controls_map.values()})
        self.assertFalse((self.root / 'out/controls-map.json').exists())

    def test_control_verdict_mismatch_fails_closed(self):
        control = self.campaign.control_key('ct0002')
        self.campaign.write_pass1(overrides={control: 'correct'})
        with self.assertRaisesRegex(ValueError, 'control .*expected'):
            self.build()

    def test_pool_batch_without_mixed_controls_is_rejected(self):
        v3 = builder.read_jsonl(self.root / 'data/distill/stage2-v3/train.jsonl')
        raw = {row['id']: row for row in builder.read_jsonl(
            self.root / 'data/teacher/roihu_full_raw_samples.jsonl')}
        v3_requests = {row['id']: row for row in builder.read_jsonl(
            self.root / 'data/distill/stage2-v3/requests.jsonl')}
        control_cases = {entry['case'] for entry in self.campaign.controls_map.values()}
        without_controls = json.loads(json.dumps(self.campaign.pool_batches))
        without_controls['b00']['items'] = [
            item for item in without_controls['b00']['items']
            if item['case'] not in control_cases]
        with self.assertRaisesRegex(ValueError, 'batch has no controls'):
            builder.verify_pool_batches(without_controls, self.campaign.keymap,
                                        self.campaign.controls_map, v3, raw,
                                        v3_requests, stub_effective)
        only_correct = json.loads(json.dumps(self.campaign.pool_batches))
        only_correct['b00']['items'] = [
            item for item in only_correct['b00']['items']
            if self.campaign.controls_map.get(item['candidates'][0]['key'], {}).get(
                'expected') != 'incorrect']
        with self.assertRaisesRegex(ValueError, 'lacks one control of each polarity'):
            builder.verify_pool_batches(only_correct, self.campaign.keymap,
                                        self.campaign.controls_map, v3, raw,
                                        v3_requests, stub_effective)

    def test_control_map_must_recompute_from_controls_jsonl(self):
        # A consistently rewritten controls map, pool manifest and pass-1 verdicts must
        # still fail: every control entry is recomputed from the tracked controls source.
        path = self.campaign.pool / 'controls-map.json'
        controls_map = json.loads(path.read_text())
        key = next(iter(sorted(controls_map)))
        was = controls_map[key]['expected']
        flipped = 'incorrect' if was == 'correct' else 'correct'
        controls_map[key]['expected'] = flipped
        path.write_text(json.dumps(controls_map, indent=2) + '\n')
        manifest_path = self.campaign.pool / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['artifacts_sha256']['controls_map'] = builder.sha256_file(path)
        case = controls_map[key]['case']
        for batch in self.campaign.pool_batches.values():
            if any(item['case'] == case for item in batch['items']):
                summary = manifest['controls_by_batch'][batch['batch']]
                summary[flipped] += 1
                summary[was] -= 1
                break
        else:
            self.fail('flipped control appears in no pool batch')
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        self.campaign.write_pass1(overrides={
            self.campaign.key('r00003', 'uname -a'): 'incorrect',
            self.campaign.key('r00009', 'whoami'): 'incorrect',
            self.campaign.key('r00006', 'ls -lt'): 'incorrect',
            key: flipped})
        confirm = self.root / 'confirm-map-tamper'
        pass2 = self.root / 'confirm-verdicts-map-tamper'
        self.campaign.make_confirm(out_dir=confirm, sample=1.0, seed=13)
        self.campaign.write_pass2(confirm_dir=confirm, directory=pass2)
        with self.assertRaisesRegex(ValueError, 'does not recompute from controls.jsonl'):
            self.build(confirm=confirm, pass2=pass2)

    def test_custom_controls_path_is_bound_to_the_pool(self):
        custom = self.campaign.judge_dir / 'controls-custom.jsonl'
        shutil.copy(self.campaign.judge_dir / 'controls.jsonl', custom)
        manifest = self.build(out='out-custom-controls', controls_path=custom)
        self.assertEqual(manifest['inputs_sha256']['controls'],
                         builder.sha256_file(custom))
        custom.write_text(custom.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'pool input digests'):
            self.build(out='out-changed-controls', controls_path=custom)

    def test_director_map_must_match_the_pool_sources(self):
        path = self.campaign.pool / 'director-map.json'
        director = json.loads(path.read_text())
        case = next(case for case, entry in sorted(director.items())
                    if entry['kind'] == 'real')
        director[case]['rid'] = 'r99999'
        path.write_text(json.dumps(director, indent=2) + '\n')
        manifest_path = self.campaign.pool / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['artifacts_sha256']['director_map'] = builder.sha256_file(path)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        with self.assertRaisesRegex(ValueError, 'director map does not match'):
            self.build()

    def test_every_batch_has_mixed_controls(self):
        for name, batch in self.campaign.pool_batches.items():
            expected = {self.campaign.controls_map[item['candidates'][0]['key']]['expected']
                        for item in batch['items']
                        if item['candidates'][0]['key'] in self.campaign.controls_map}
            self.assertEqual(expected, {'correct', 'incorrect'}, name)

    def test_strict_verdict_loader_rejects_malformed_verdicts(self):
        path = self.pass1 / 'b00.json'
        original = path.read_text()

        def mutate(change):
            data = json.loads(original)
            change(data)
            path.write_text(json.dumps(data))

        def verdicts(data):
            return data['cases'][0]['verdicts']

        def drop_one_key(data):
            case = next(case for case in data['cases'] if len(case['verdicts']) > 1)
            case['verdicts'].pop()

        cases = [
            ('top-level extra field', lambda d: d.update(extra=1),
             'must contain exactly batch, judge, cases'),
            ('batch field mismatch', lambda d: d.update(batch='b01'),
             'does not match filename'),
            ('empty judge', lambda d: d.update(judge='  '),
             'judge identity'),
            ('case extra field', lambda d: d['cases'][0].update(extra=1),
             'must contain exactly case and verdicts'),
            ('unknown case', lambda d: d['cases'][0].update(case='unknown'),
             'unknown or misplaced case'),
            ('duplicate case', lambda d: d['cases'].append(d['cases'][0]),
             'judged twice'),
            ('missing case', lambda d: d['cases'].pop(),
             'missing verdicts for cases'),
            ('verdict extra field', lambda d: verdicts(d)[0].update(extra=1),
             'must contain exactly key, verdict'),
            ('unknown key', lambda d: verdicts(d)[0].update(key='kdeadbeefdead'),
             'misplaced or unknown key'),
            ('duplicate key', lambda d: verdicts(d).append(verdicts(d)[0]),
             'judged twice in case'),
            ('invalid verdict', lambda d: verdicts(d)[0].update(verdict='maybe'),
             'invalid verdict'),
            ('incorrect without category',
             lambda d: verdicts(d)[0].update(verdict='incorrect', category=None),
             'needs a valid category'),
            ('incorrect with bogus category',
             lambda d: verdicts(d)[0].update(verdict='incorrect', category='bogus'),
             'needs a valid category'),
            ('correct with category',
             lambda d: verdicts(d)[0].update(verdict='correct', category='other'),
             'must have null category'),
            ('unsure with category',
             lambda d: verdicts(d)[0].update(verdict='unsure', category='other'),
             'must have null category'),
            ('empty evidence', lambda d: verdicts(d)[0].update(evidence=''),
             'needs non-empty evidence'),
            ('missing key', drop_one_key,
             'missing verdicts for'),
        ]
        for name, change, message in cases:
            with self.subTest(name=name):
                mutate(change)
                with self.assertRaisesRegex(ValueError, message):
                    builder.load_verdicts(self.pass1, self.campaign.pool_batches,
                                          keymap=self.campaign.keymap,
                                          controls=self.campaign.controls_map)
                path.write_text(original)

    def test_pool_batches_require_opaque_identifiers(self):
        path = self.campaign.pool / 'batches/b00.json'
        data = json.loads(path.read_text())
        data['items'][0]['case'] = 'r00001'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'opaque c\\+12hex id'):
            builder.load_batches(self.campaign.pool / 'batches', 'pool')

    def test_verdict_command_must_match_the_keymap(self):
        key = next(key for key in self.campaign.keymap
                   if self.campaign.keymap[key]['case'] in
                   {item['case'] for item in self.campaign.pool_batches['b00']['items']})
        keymap = json.loads(json.dumps(self.campaign.keymap))
        keymap[key]['command'] = 'tampered -x'
        with self.assertRaisesRegex(ValueError, 'command does not match keymap'):
            builder.load_verdicts(self.pass1, self.campaign.pool_batches,
                                  keymap=keymap, controls=self.campaign.controls_map)

    def test_verdict_loader_rejects_unexpected_and_missing_files(self):
        (self.pass1 / 'notes.txt').write_text('extra')
        with self.assertRaisesRegex(ValueError, 'unexpected files'):
            builder.load_verdicts(self.pass1, self.campaign.pool_batches)
        (self.pass1 / 'notes.txt').unlink()
        (self.pass1 / 'b02.json').unlink()
        with self.assertRaisesRegex(ValueError, 'missing batches'):
            builder.load_verdicts(self.pass1, self.campaign.pool_batches)

    def test_pool_artifact_tamper_is_rejected(self):
        path = self.campaign.pool / 'batches/b00.json'
        path.write_text(path.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'pool artifacts do not match'):
            self.build()

    def test_pool_manifest_count_tamper_is_rejected(self):
        manifest_path = self.campaign.pool / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['counts']['items'] += 1
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        with self.assertRaisesRegex(ValueError, 'item count does not match'):
            self.build(out='out-counts')

    def test_corpus_and_raw_request_mismatch_is_rejected(self):
        raw_path = self.root / 'data/teacher/roihu_full_raw_samples.jsonl'
        raw = builder.read_jsonl(raw_path)
        next(row for row in raw if row['id'] == 'r00015')['request'] = 'changed request'
        write_jsonl(raw_path, raw)
        manifest_path = self.campaign.pool / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['inputs_sha256']['raw_samples'] = builder.sha256_file(raw_path)
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
        with self.assertRaisesRegex(ValueError, 'corpus and raw teacher requests differ'):
            self.build(out='out-corpus')

    def test_stale_pool_inputs_are_rejected(self):
        path = self.root / 'data/teacher/roihu_full_raw_samples.jsonl'
        path.write_text(path.read_text() + '\n')
        with self.assertRaisesRegex(ValueError, 'input digests do not match'):
            self.build()

    def test_keymap_must_match_the_pool(self):
        with self.assertRaisesRegex(ValueError, 'passed keymap does not match'):
            builder.build({'k000000000000': {}}, self.pass1, self.confirm,
                          self.pass2, self.root / 'out', pool_dir=self.campaign.pool)

    def test_candidate_frequency_drift_is_rejected(self):
        raw = {row['id']: row for row in builder.read_jsonl(
            self.root / 'data/teacher/roihu_full_raw_samples.jsonl')}
        raw['r00006']['samples'] = [{'cmd': 'ls -lS'}, {'cmd': 'ls -lS'},
                                    {'cmd': 'ls -lS'}, {'cmd': 'ls -lt'}]
        with self.assertRaisesRegex(ValueError, 'frequency changed'):
            builder.verify_keymap(self.campaign.keymap, builder.read_jsonl(
                self.root / 'data/distill/stage2-v3/train.jsonl'), raw, stub_effective)

    def test_keymap_candidate_missing_from_fresh_counts_is_rejected(self):
        key = self.campaign.key('r00006', 'ls -lt')
        keymap = json.loads(json.dumps(self.campaign.keymap))
        keymap[key]['command'] = 'ls -lT'
        raw = {row['id']: row for row in builder.read_jsonl(
            self.root / 'data/teacher/roihu_full_raw_samples.jsonl')}
        with self.assertRaisesRegex(ValueError, "r00006.*ls -lT"):
            builder.verify_keymap(keymap, builder.read_jsonl(
                self.root / 'data/distill/stage2-v3/train.jsonl'), raw, stub_effective)

    def test_confirm_batch_tamper_is_rejected(self):
        path = self.confirm / 'b00.json'
        data = json.loads(path.read_text())
        data['items'][0]['request'] += ' tampered'
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'does not match the deterministic sample'):
            self.build()

    def test_confirm_directory_unexpected_file_is_rejected(self):
        (self.confirm / 'b02.json').write_text(json.dumps(
            {'batch': 'b02', 'items': []}))
        with self.assertRaisesRegex(ValueError, 'complete sequence'):
            self.build()
        (self.confirm / 'b02.json').unlink()
        (self.confirm / 'notes.txt').write_text('extra')
        with self.assertRaisesRegex(ValueError, 'unexpected files'):
            self.build()

    def test_confirm_manifest_tamper_is_rejected(self):
        path = self.confirm / 'manifest.json'
        original = path.read_text()
        for name, change, message in (
                ('sampled', lambda d: d.update(sampled=99), 'sampled'),
                ('selected', lambda d: d['selected'].pop(), 'selected labels'),
                ('missing field', lambda d: d.pop('seed'), 'exactly'),
                ('stale pass1 hash',
                 lambda d: d['inputs_sha256'].update(pass1_verdicts='0' * 64),
                 'bound to different inputs')):
            with self.subTest(name=name):
                data = json.loads(original)
                change(data)
                path.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, message):
                    self.build(confirm=self.confirm)
        path.write_text(original)

    def test_confirm_verdicts_must_be_exactly_the_sample(self):
        path = self.pass2 / 'b00.json'
        original = path.read_text()
        data = json.loads(original)
        case = next(case for case in data['cases'] if len(case['verdicts']) > 1)
        case['verdicts'].pop()
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'missing verdicts for'):
            self.build()
        path.write_text(original)
        with self.assertRaisesRegex(ValueError, 'outside the required candidate set'):
            builder.load_verdicts(
                self.pass2,
                builder.load_batches(self.confirm, 'confirm', allow_manifest=True),
                keymap=self.campaign.keymap, require_keys=set())

    def test_quarantine_tamper_after_confirm_is_rejected(self):
        path = self.root / 'data/distill/quarantine_ids.txt'
        path.write_text(path.read_text() + '# added after confirmation\n')
        with self.assertRaisesRegex(ValueError, 'bound to different inputs'):
            self.build()

    def test_confirm_judge_reuse_is_rejected(self):
        self.campaign.write_pass2(judge='fixture-pass1')
        with self.assertRaisesRegex(ValueError, 'fresh judge'):
            self.build()

    def test_judge_sessions_are_recorded(self):
        manifest = self.build()
        self.assertEqual(manifest['judge_sessions']['pass1'], ['fixture-pass1'])
        self.assertEqual(manifest['judge_sessions']['pass2'], ['fixture-pass2'])
        self.assertRegex(manifest['judge_sessions']['case_pairs_sha256'],
                         r'^[0-9a-f]{64}$')

    def test_twenty_percent_sample_is_recomputed_exactly(self):
        confirm = self.root / 'confirm20'
        pass2 = self.root / 'confirm-verdicts20'
        self.campaign.make_confirm(out_dir=confirm, sample=0.2, seed=13)
        self.campaign.write_pass2(confirm_dir=confirm, directory=pass2)
        manifest = self.build(out='out20', confirm=confirm, pass2=pass2, sample=0.2)
        self.assertEqual(manifest['rows'], 9)
        self.assertNotIn('drop_v3_second_pass_rejected', manifest['actions'])
        self.assertNotIn('drop_second_pass_rejected', manifest['actions'])
        self.assertEqual(len(json.loads((confirm / 'manifest.json').read_text())['sample_cases']),
                         2)
        self.assertEqual(json.loads((confirm / 'manifest.json').read_text())['sampled'], 2)
        sample = json.loads((confirm / 'b00.json').read_text())
        self.assertEqual(len(sample['items']), 2)

    def test_leakage_review_artifact_and_duplicate_order(self):
        manifest = self.build()
        review = builder.read_jsonl(self.root / 'out/eval_leakage_review.jsonl')
        self.assertIn({'id': 'r00012', 'kind': 'tool+flags', 'split': 'dev'},
                      review)
        self.assertIn({'id': 'r00013', 'kind': 'tool+flags', 'split': 'heldout'},
                      review)
        self.assertEqual(manifest['eval_leakage_review'], review)
        self.assertEqual(manifest['eval_leakage_review_count'], len(review))
        audit = builder.read_jsonl(self.root / 'out/audit.jsonl')
        self.assertIn({'id': 'r00013', 'action': 'drop_eval_leakage'}, audit)
        self.assertIn({'id': 'r00014', 'action': 'add_verified', 'target': 'wc -l clean.log'},
                      audit)
        self.assertFalse([entry for entry in audit
                          if entry['id'] == 'r00014' and entry['action'].startswith('drop_')])

    def test_output_is_deterministic_and_hashes_cover_inputs(self):
        first = self.build(out='out1')
        second = self.build(out='out2')
        self.assertEqual(first, second)
        self.assertEqual(tree_bytes(self.root / 'out1'), tree_bytes(self.root / 'out2'))
        self.assertEqual(set(first['inputs_sha256']), {
            'corpus', 'raw_samples', 'v3_train', 'v3_requests', 'controls', 'keymap',
            'pool_manifest', 'pool_batches', 'controls_map', 'director_map',
            'quarantine_ids', 'roihu_full_quarantine_ids',
            'pass1_verdicts', 'pass1_verdict_files', 'confirm_manifest',
            'confirm_batches', 'confirm_verdicts', 'confirm_verdict_files', 'eval'})
        for name in ('quarantine_ids', 'roihu_full_quarantine_ids'):
            self.assertEqual(first['inputs_sha256'][name],
                             builder.sha256_file(self.root / f'data/distill/{name}.txt'))
        for name, digest in first['outputs_sha256'].items():
            path = self.root / f'out1/{name}.jsonl'
            self.assertEqual(digest, builder.sha256_file(path))
        self.assertEqual(first['train_sha256'], first['outputs_sha256']['train'])

    def test_nonempty_output_directory_fails(self):
        out = self.root / 'out-nonempty'
        out.mkdir()
        (out / 'stale.json').write_text('{}')
        with self.assertRaisesRegex(ValueError, 'not empty'):
            self.build(out=out)

    def test_module_import_needs_no_upstream_whatisit_and_stays_lazy(self):
        repo = Path(__file__).resolve().parents[1]
        env = {**os.environ,
               'PYTHONPATH': os.pathsep.join([str(repo / 'src'), str(repo / 'tools')])}
        code = ("import sys; sys.modules['whatisit'] = None; import build_verified_dataset; "
                "assert 'score_teacher_eval' not in sys.modules, 'scorer imported eagerly'")
        import subprocess
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True,
                                env=env)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
