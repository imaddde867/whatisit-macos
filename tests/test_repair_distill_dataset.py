import copy
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import repair_distill_dataset as repair
from whatisit_macos.local_recovery_worker import MACOS_PREFIX


class RepairTests(unittest.TestCase):
    def setUp(self):
        package = types.ModuleType('whatisit')
        safety = types.ModuleType('whatisit.safety')
        safety.check = lambda command: []
        safety.PLACEHOLDER_HINT = re.compile(r'/path/to/')
        package.safety = safety
        modules = patch.dict(sys.modules, {'whatisit': package, 'whatisit.safety': safety})
        modules.start()
        self.addCleanup(modules.stop)
        self.request = {'id': 'r1', 'request': 'Read metadata for sample.pdf.', 'kind': 'answer'}
        self.label = {'id': 'r1', 'messages': [
            {'role': 'system', 'content': 'system'},
            {'role': 'user', 'content': MACOS_PREFIX + self.request['request']},
            {'role': 'assistant', 'content': 'mdls sample.pdf'}]}
        self.raw = {'id': 'r1', 'request': self.request['request'], 'samples': [
            {'parsed': True, 'finish_reason': 'stop', 'command': 'mdls sample.pdf'}] * 5}
        self.edit = {'id': 'r1', 'original_request': self.request['request'],
                     'original_target': 'mdls sample.pdf', 'request': 'Read metadata for this file.',
                     'path': 'sample.pdf', 'reason': 'Move named operand to explicit path.'}

    def test_path_repair_preserves_target_and_records_source(self):
        rows, requests, audit = repair.repair([self.request], [self.label], [self.raw], [self.edit])
        self.assertEqual(rows[0]['messages'][1]['content'], MACOS_PREFIX +
                         'Read metadata for this file.\nExplicit inputs: {"path": "sample.pdf"}')
        self.assertEqual(rows[0]['messages'][-1]['content'], 'mdls sample.pdf')
        self.assertEqual(audit[0]['teacher_votes'], 5)
        self.assertEqual(rows[0]['source_id'], 'r1')
        self.assertEqual(requests[0]['path'], 'sample.pdf')
        self.assertNotIn('path', self.request)

    def test_cluster_majority_is_verified_and_audited(self):
        raw = {**self.raw, 'samples': [{'parsed': True, 'finish_reason': 'stop', 'command': c}
               for c in ('mdls sample.pdf', 'mdls ./sample.pdf', 'mdls "sample.pdf"', None, None)]}
        provenance = {'r1': {'vote_mode': 'equivalence', 'cluster_votes': 3,
                            'strings': ['mdls "sample.pdf"', 'mdls ./sample.pdf', 'mdls sample.pdf']}}
        rows, _, audit = repair.repair([self.request], [self.label], [raw], [], provenance)
        self.assertEqual(len(rows), 1)
        self.assertEqual((audit[0]['teacher_votes'], audit[0]['cluster_votes'], audit[0]['vote_mode']),
                         (1, 3, 'equivalence'))
        raw['samples'][1]['command'] = 'mdls other.pdf'
        with self.assertRaisesRegex(ValueError, 'cluster'):
            repair.repair([self.request], [self.label], [raw], [], provenance)

    def test_v3_summary_counts_only_retained_recovered_rows(self):
        row = {**self.label, 'source_id': 'r1'}
        request = {**self.request, 'category': 'metadata'}
        provenance = {'r1': {'cluster_votes': 4, 'strings': ['mdls sample.pdf', 'mdls ./sample.pdf']},
                      'excluded': {'cluster_votes': 3, 'strings': ['x', 'y']}}
        report = repair.v3_summary([row], [request], provenance, [])
        self.assertEqual(report['recovered_rows'], 1)
        self.assertEqual(report['recovered_by_agreement'], {'4': 1})
        self.assertEqual(report['recovered_by_category'], {'metadata': 1})
        self.assertEqual(report['recovered_multistring_rows'], 1)
        self.assertEqual(report['new_tool_flag_signatures'], 1)

    def test_stale_annotation_and_missing_teacher_votes_fail_closed(self):
        stale = {**self.edit, 'original_target': 'other'}
        with self.assertRaisesRegex(ValueError, 'stale'):
            repair.repair([self.request], [self.label], [self.raw], [stale])
        raw = {**self.raw, 'samples': self.raw['samples'][:2]}
        with self.assertRaisesRegex(ValueError, 'majority'):
            repair.repair([self.request], [self.label], [raw], [])

    def test_exclusion_and_duplicate_requests_are_audited(self):
        edit = {**self.edit, 'exclude': True, 'reason': 'uncertain label'}
        rows, _, audit = repair.repair([self.request], [self.label], [self.raw], [edit])
        self.assertEqual(rows, [])
        self.assertEqual(audit[0]['action'], 'exclude')
        second = copy.deepcopy(self.label)
        second['id'] = 'r2'
        rows, _, audit = repair.repair([self.request, {**self.request, 'id': 'r2'}],
                                      [self.label, second], [self.raw, {**self.raw, 'id': 'r2'}], [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(audit[1]['reason'], 'duplicate request of r1')

    def test_rewrite_cannot_invent_explicit_path(self):
        with self.assertRaisesRegex(ValueError, 'path'):
            repair.repair([self.request], [self.label], [self.raw],
                          [{**self.edit, 'path': 'invented.pdf'}])

    def test_duplicate_source_ids_fail_with_value_error(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            repair.repair([self.request, self.request], [self.label], [self.raw], [])

    def test_missing_teacher_source_fails_with_value_error(self):
        with self.assertRaisesRegex(ValueError, 'source id'):
            repair.repair([self.request], [self.label], [], [])

    def test_corrected_target_is_separate_from_teacher_vote(self):
        edit = {**self.edit, 'request': self.request['request'], 'target': 'mdls -name kMDItemFSName sample.pdf',
                'provenance': 'reviewed correction', 'verification': 'manually checked'}
        rows, _, audit = repair.repair([self.request], [self.label], [self.raw], [edit])
        self.assertEqual(rows[0]['messages'][-1]['content'], edit['target'])
        self.assertEqual(audit[0]['original_target_votes'], 5)
        self.assertEqual(audit[0]['action'], 'corrected_target')

    def test_addition_uses_source_prompt_and_records_family(self):
        addition = {'id': 's2add001', 'source_id': 's2family01', 'request': 'Read this file.',
                    'path': 'sample.pdf', 'target': 'mdls sample.pdf', 'category': 'metadata',
                    'kind': 'answer', 'provenance': 'model-authored', 'reason': 'path variation',
                    'verification': 'macOS syntax checked'}
        rows, requests, audit = repair.add_additions([], [], [addition], self.label['messages'][0]['content'])
        self.assertEqual(rows[0]['messages'][1]['content'], MACOS_PREFIX +
                         'Read this file.\nExplicit inputs: {"path": "sample.pdf"}')
        self.assertEqual(requests[0]['source_id'], 's2family01')
        self.assertEqual(rows[0]['source_id'], 's2family01')
        self.assertEqual(audit[0]['source_id'], 's2family01')

    def test_command_request_rewrite_requires_review_provenance(self):
        edit = {**self.edit, 'request': 'Read this metadata.', 'reason': 'Clarify wording.'}
        edit.pop('path')
        with self.assertRaisesRegex(ValueError, 'provenance'):
            repair.repair([self.request], [self.label], [self.raw], [edit])

    def test_command_request_clarification_is_not_an_abstention(self):
        edit = {**self.edit, 'request': 'Read the Spotlight metadata of sample.pdf.',
                'reason': 'Clarify wording.', 'provenance': 'reviewed rewrite'}
        edit.pop('path')
        rows, _, audit = repair.repair([self.request], [self.label], [self.raw], [edit])
        self.assertEqual(rows[0]['messages'][-1]['content'], 'mdls sample.pdf')
        self.assertEqual(audit[0]['action'], 'clarified_request')

    def test_corrected_target_votes_count_the_new_target(self):
        edit = {**self.edit, 'request': self.request['request'], 'target': 'mdls -name kMDItemFSName sample.pdf',
                'provenance': 'reviewed correction', 'verification': 'manually checked'}
        edit.pop('path')
        _, _, audit = repair.repair([self.request], [self.label], [self.raw], [edit])
        self.assertEqual((audit[0]['teacher_votes'], audit[0]['original_target_votes']), (0, 5))

    def test_leakage_blocks_whole_source_family(self):
        rows = [{'id': 'a1', 'source_id': 'fam'}, {'id': 'a2', 'source_id': 'fam'},
                {'id': 'b1', 'source_id': 'other'}]
        hard = [('a2', 'normalized command', 'heldout')]
        self.assertEqual(repair.leakage_blocked(hard, rows), {'a1', 'a2'})


if __name__ == '__main__':
    unittest.main()
