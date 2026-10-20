"""The pool, confirm sample and final labels share the real command policy."""
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from v4_campaign import Campaign, write_jsonl
from build_v4_pool import build_pool
from repair_distill_dataset import validate_command, validation_fingerprint


class RejectedCampaign(Campaign):
    def _write_inputs(self):
        super()._write_inputs()
        path = self.root / 'data/distill/stage2-v3/train.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]['messages'][-1]['content'] = 'rm victim.txt'
        write_jsonl(path, rows)
        path = self.root / 'data/teacher/roihu_full_raw_samples.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        for row in rows:
            if row['id'] == 'r00009':
                row['samples'] = [{'cmd': 'rm victim.txt'}] * 2
        write_jsonl(path, rows)


class ValidationCampaignTests(unittest.TestCase):
    def test_fingerprint_does_not_read_home_sources_outside_workspace(self):
        safety = types.ModuleType('whatisit.safety')
        safety.__file__ = '/home/other/whatisit/safety.py'
        package = types.ModuleType('whatisit')
        package.safety = safety
        with patch.dict(sys.modules, {'whatisit': package, 'whatisit.safety': safety}):
            record = validation_fingerprint()
        self.assertEqual(record['code_sha256']['upstream_safety'],
                         'source_outside_task_workspace')

    def test_complete_teacher_rejection_is_audited_before_effective_abstention(self):
        safety = types.ModuleType('whatisit.safety')
        safety.check = lambda command: []
        safety.PLACEHOLDER_HINT = re.compile(r'/path/to/')
        package = types.ModuleType('whatisit')
        package.safety = safety
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {
                'whatisit': package, 'whatisit.safety': safety}):
            spec = importlib.util.spec_from_file_location(
                'v4_policy_teacher_eval', Path(__file__).resolve().parents[1] /
                'tools/score_teacher_eval.py')
            teacher = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(teacher)
            root = Path(tmp)
            write_jsonl(root / 'corpus.jsonl', [
                {'id': 'bad', 'request': 'Show directory.'},
                {'id': 'good', 'request': 'Show directory.'}])
            write_jsonl(root / 'raw.jsonl', [
                {'id': 'bad', 'request': 'Show directory.', 'samples': [
                    {'parsed': True, 'finish_reason': 'stop', 'command': 'rm victim.txt'}] * 2 + [
                    {'parsed': True, 'finish_reason': 'length', 'command': 'rm truncated.txt'}]},
                {'id': 'good', 'request': 'Show directory.', 'samples': [
                    {'parsed': True, 'finish_reason': 'stop', 'command': 'pwd'}]}])
            write_jsonl(root / 'v3/train.jsonl', [])
            write_jsonl(root / 'v3/requests.jsonl', [])
            manifest = build_pool(root / 'corpus.jsonl', root / 'raw.jsonl', root / 'v3',
                                  root / 'out', effective=teacher.effective_command,
                                  validate=validate_command)
            self.assertEqual(len(manifest['excluded_candidates']), 1)
            excluded = manifest['excluded_candidates'][0]
            self.assertEqual((excluded['rid'], excluded['command']), ('bad', 'rm victim.txt'))
            self.assertIn('reason', excluded)
            self.assertIn('not an unambiguous named literal target', excluded['reason'])
            self.assertEqual(manifest['counts']['excluded_candidates'], 1)
            self.assertIn({'rid': 'bad', 'reason': 'all_candidates_excluded'}, manifest['warnings'])
            keymap = json.loads((root / 'out/keymap.json').read_text())
            self.assertEqual([(e['rid'], e['command']) for e in keymap.values()], [('good', 'pwd')])

    def test_rejected_old_and_new_commands_never_enter_confirm_or_training(self):
        safety = types.ModuleType('whatisit.safety')
        safety.check = lambda command: []
        safety.PLACEHOLDER_HINT = re.compile(r'/path/to/')
        package = types.ModuleType('whatisit')
        package.safety = safety
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {
                'whatisit': package, 'whatisit.safety': safety}):
            root = Path(tmp)
            campaign = RejectedCampaign(root, controls_per_batch=3, validate=validate_command)
            self.assertEqual(campaign.pool_manifest['counts']['v3_policy_rejected'], 1)
            self.assertFalse({'r00001', 'r00009'} & {e['rid'] for e in campaign.keymap.values()})
            campaign.write_pass1()
            confirm = campaign.make_confirm(sample=0.2)
            self.assertFalse({'r00001', 'r00009'} & {e['rid'] for e in confirm['selected']})
            self.assertEqual(confirm['sampled'], round(confirm['selected_total'] * 0.2))
            campaign.write_pass2()
            manifest = campaign.build_verified(root / 'out', sample=0.2)
            rows = [json.loads(line) for line in (root / 'out/train.jsonl').read_text().splitlines()]
            targets = {row['id']: row['messages'][-1]['content'] for row in rows}
            self.assertNotIn('r00001', targets)
            self.assertNotIn('r00009', targets)
            self.assertEqual(targets['r00002'], '')
            self.assertEqual(targets['r00003'], 'uname -a')
            self.assertEqual(manifest['actions']['drop_v3_policy_rejected'], 1)
            audit = [json.loads(line) for line in (root / 'out/audit.jsonl').read_text().splitlines()]
            dropped = next(e for e in audit if e['id'] == 'r00001')
            self.assertIn('reason', dropped)
            self.assertEqual(campaign.pool_manifest['validation'], confirm['validation'])
            self.assertEqual(confirm['validation'], manifest['validation'])
