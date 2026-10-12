import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_distill_dataset as builder


class DistillDatasetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.requests = root / 'requests.jsonl'
        self.raw = root / 'raw.jsonl'
        self.manifest = root / 'manifest.json'
        self.evals = root / 'eval'
        self.evals.mkdir()
        self.out = root / 'train.jsonl'
        self.report = root / 'quality.md'
        self.review = root / 'review.jsonl'
        self.rows = [
            {'id': 'r00001', 'request': 'show a thing about notes.txt', 'kind': 'answer'},
            {'id': 'r00002', 'request': 'do the unspecified job', 'kind': 'abstain'},
            {'id': 'r00003', 'request': 'inspect a separate widget', 'kind': 'answer'},
        ]
        self.samples = [
            [{'command': 'alpha -q notes.txt', 'parsed': True, 'finish_reason': 'stop', 'completion_tokens': 10}] * 3 +
            [{'command': None, 'parsed': True, 'finish_reason': 'stop', 'completion_tokens': 8}] * 2,
            [{'command': None, 'parsed': True, 'finish_reason': 'stop', 'completion_tokens': 8}] * 3 +
            [{'command': 'beta', 'parsed': True, 'finish_reason': 'stop', 'completion_tokens': 10}] * 2,
            [{'command': 'gamma', 'parsed': True, 'finish_reason': 'stop', 'completion_tokens': 10}] * 2 +
            [{'command': 'delta', 'parsed': True, 'finish_reason': 'stop', 'completion_tokens': 10}] * 2 +
            [{'command': None, 'parsed': True, 'finish_reason': 'stop', 'completion_tokens': 8}],
        ]
        self.write_inputs()

    def write_inputs(self):
        self.requests.write_text(''.join(json.dumps(r) + '\n' for r in self.rows))
        self.raw.write_text(''.join(json.dumps({'id': r['id'], 'request': r['request'], 'samples': s}) + '\n'
                                    for r, s in zip(self.rows, self.samples)))
        manifest = {'model': 'open-teacher', 'quant': 'Q6', 'server': 'test-server 1',
                    'host': 'test-gpu', 'seed_base': 1000, 'temperature': 0.7,
                    'top_p': 0.95, 'max_tokens': 8192, 'wall_seconds_this_run': 42,
                    'requests_total': len(self.rows), 'samples_per_request': 5,
                    'requests_file_sha256': hashlib.sha256(self.requests.read_bytes()).hexdigest(),
                    'system_prompt_sha256': hashlib.sha256(builder.TEACHER_SYSTEM_PROMPT.encode()).hexdigest()}
        self.manifest.write_text(json.dumps(manifest))
        for split in ('dev', 'everyday', 'frozen'):
            (self.evals / f'{split}.jsonl').write_text(json.dumps({
                'request': f'unrelated {split} task', 'reference': 'unrelated -z'}) + '\n')

    def run_builder(self, *, problems=None, safety_findings=None, deletion_issues=None):
        package = types.ModuleType('whatisit')
        config = types.ModuleType('whatisit.config')
        config.SYSTEM_PROMPT = 'Real upstream prompt'
        safety = types.ModuleType('whatisit.safety')
        safety.check = lambda command: (safety_findings or {}).get(command, [])
        safety.PLACEHOLDER_HINT = re.compile(r'/path/to/')
        package.config, package.safety = config, safety
        with patch.object(builder.platform, 'system', return_value='Darwin'), \
                patch.dict(sys.modules, {'whatisit': package, 'whatisit.config': config,
                                         'whatisit.safety': safety}), \
                patch.object(builder, 'problems', side_effect=problems or (lambda command: [])), \
                patch.object(builder, 'unrequested_deletion',
                             side_effect=deletion_issues or (lambda command, request: [])):
            return builder.build(self.requests, self.raw, self.manifest, self.evals,
                                 self.out, self.report, self.review)

    def test_majority_abstention_prompt_and_pending_review(self):
        counts = self.run_builder()
        self.assertEqual((counts['kept'], counts['abstain'], counts['dropped_no_majority']), (1, 1, 1))
        rows = builder.read_jsonl(self.out)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['messages'][0]['content'], 'Real upstream prompt')
        self.assertEqual(rows[0]['messages'][1]['content'], builder.MACOS_PREFIX + self.rows[0]['request'])
        self.assertEqual(rows[0]['messages'][-1]['content'], 'alpha -q notes.txt')
        self.assertEqual(rows[1]['messages'][-1]['content'], '')
        review = builder.read_jsonl(self.review)
        self.assertEqual(len(review), 1)
        self.assertIsNone(review[0]['human_correct'])
        self.assertIn('pending', self.report.read_text())

    def test_only_parsed_stop_samples_vote_and_checks_reject(self):
        self.samples[0][2] = {'command': 'alpha -q notes.txt', 'parsed': False, 'finish_reason': 'stop'}
        self.write_inputs()
        counts = self.run_builder()
        self.assertEqual(counts['kept'], 0)
        self.assertEqual(counts['dropped_no_majority'], 2)
        self.assertEqual(builder.read_jsonl(self.out)[0]['messages'][-1]['content'], '')

    def test_host_checks_and_danger_reject_commands(self):
        counts = self.run_builder(problems=lambda command: ['bad flag'] if command.startswith('alpha') else [],
                                  safety_findings={'beta': [('DANGER', 'unsafe')]})
        self.assertEqual(counts['kept'], 0)
        self.assertIn('macos_lint', self.report.read_text())
        self.assertIn('danger', self.report.read_text())

    def test_deletion_and_placeholder_checks_reject_commands(self):
        self.samples[0] = ([{'command': 'rm surprise.txt', 'parsed': True, 'finish_reason': 'stop'}] * 2 +
                           [{'command': 'cat /path/to/file', 'parsed': True, 'finish_reason': 'stop'}] +
                           [{'command': None, 'parsed': True, 'finish_reason': 'stop'}] * 2)
        self.write_inputs()
        counts = self.run_builder(deletion_issues=lambda command, request:
                                  ['unnamed target'] if command.startswith('rm ') else [])
        self.assertEqual(counts['kept'], 0)
        self.assertIn('deletion_guard', self.report.read_text())
        self.assertIn('placeholder', self.report.read_text())

    def test_refuses_non_mac_and_modified_manifest(self):
        with patch.object(builder.platform, 'system', return_value='Linux'):
            with self.assertRaisesRegex(RuntimeError, 'macOS'):
                builder.build(self.requests, self.raw, self.manifest, self.evals,
                              self.out, self.report, self.review)
        manifest = json.loads(self.manifest.read_text())
        manifest['requests_file_sha256'] = 'wrong'
        self.manifest.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            self.run_builder()
        self.assertFalse(self.out.exists())

    def test_missing_command_is_not_an_abstain_vote(self):
        self.samples[1][0] = {'parsed': True, 'finish_reason': 'stop'}
        self.write_inputs()
        with self.assertRaisesRegex(ValueError, 'invalid sample schema'):
            self.run_builder()

    def test_eval_request_or_normalized_command_overlap_is_quarantined(self):
        (self.evals / 'frozen.jsonl').write_text(json.dumps({
            'request': self.rows[0]['request'], 'reference': 'alpha -q another.txt'}) + '\n')
        self.run_builder()
        self.assertEqual([json.loads(l)['id'] for l in self.out.read_text().splitlines()], ['r00002'])
        text = self.report.read_text()
        self.assertIn('quarantined r00001: request frozen', text)
        self.assertIn('quarantined r00001: normalized command frozen', text)
        self.assertIn('1 rows quarantined', text)

    def test_tool_and_flag_overlap_in_a_pipeline_is_reported_not_gated(self):
        self.samples[0][:3] = [{'command': 'alpha -q notes.txt | sort -r', 'parsed': True,
                                'finish_reason': 'stop', 'completion_tokens': 10}] * 3
        self.write_inputs()
        (self.evals / 'frozen.jsonl').write_text(json.dumps({
            'request': 'unrelated frozen task', 'reference': 'alpha -q other.txt | sort -r'}) + '\n')
        self.run_builder()
        self.assertTrue(self.out.exists())
        self.assertIn('tool+flags vs frozen: 1 rows', self.report.read_text())

    def test_operand_overlap_is_gated_and_shell_glue_is_ignored(self):
        self.assertEqual(builder.normalized('sysctl -n hw.pagesize'), (('sysctl', ('-n',), frozenset({'hw.pagesize'})),))
        self.assertNotEqual(builder.normalized('sysctl -n hw.pagesize'), builder.normalized('sysctl -n hw.ncpu'))
        self.assertEqual(builder.signature('[ -t 1 ] && echo yes || echo no'), ())
        self.assertEqual(builder.normalized('du -sh . | sort -h'), ())

    def test_signature_handles_shell_punctuation_and_refuses_broken_quotes(self):
        self.assertEqual(builder.signature('git status&&ls -al;ls -a -l'),
                         (('git status', ()), ('ls', ('-a', '-l')), ('ls', ('-a', '-l'))))
        self.assertEqual(builder.signature('find . -print0|xargs -0 rm'),
                         (('find', ('-print0',)), ('xargs', ('-0',))))
        with self.assertRaisesRegex(ValueError, 'tokenize'):
            builder.signature("echo 'unclosed")


if __name__ == '__main__':
    unittest.main()
