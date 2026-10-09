import json
import tempfile
import unittest
from pathlib import Path

from tools.evaluate import load_cases, evaluate


class EvaluationTests(unittest.TestCase):
    def test_log_inputs_reach_router_without_leaking_into_report(self):
        filters = dict(subsystem='com.private.workload', pid=876543, level='error',
                       start='2026-09-14 10:00:00+0300', end='2026-09-14 10:01:00+0300')
        case = {'id': 'log-filters', 'split': 'dev', 'request': 'Filter unified logs',
                'log_filter': filters, 'expected_status': 'suggestion',
                'expected_recipe': 'unified-log-filter', 'expected_docs': ['log']}
        report = evaluate([case])
        self.assertTrue(report['cases'][0]['contract_match'])
        for value in ['com.private.workload', '876543', '2026-09-14']:
            self.assertNotIn(value, json.dumps(report))

    def test_log_fixture_schema_rejects_unknown_or_wrongly_typed_inputs(self):
        case = {'id': 'log', 'split': 'dev', 'request': 'Filter unified logs',
                'expected_status': 'needs-input', 'expected_recipe': 'unified-log-filter',
                'expected_docs': ['log'], 'rubric': 'Never invent inputs.', 'manual_validation': 'pending'}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cases.jsonl'
            for inputs in [{'pid': '123'}, {'pid': True}, {'predicate': 'TRUEPREDICATE'},
                           {'start': 123}, [], None]:
                with self.subTest(inputs=inputs):
                    path.write_text(json.dumps(case | {'log_filter': inputs}) + '\n')
                    with self.assertRaises(ValueError):
                        load_cases(path)

    def test_incomplete_suggestion_is_reported_as_mismatch(self):
        cases = [{'id': 'snapshot-is-not-history', 'split': 'heldout',
                  'request': 'show sleep assertions',
                  'expected_status': 'unsupported', 'expected_docs': ['pmset'],
                  'rubric': 'A snapshot does not provide history.', 'manual_validation': 'pending'}]
        report = evaluate(cases)
        self.assertEqual(report['splits']['heldout']['contract_matches'], 0)
        self.assertEqual(report['splits']['heldout']['suggestions'], 1)
        self.assertEqual(report['cases'][0]['status'], 'suggestion')
        self.assertFalse(report['cases'][0]['contract_match'])

    def test_report_does_not_include_supplied_private_path(self):
        case = {'id': 'private-path', 'split': 'dev', 'request': 'show file metadata',
                'path': '/Users/private/secret.pdf', 'expected_status': 'suggestion',
                'expected_recipe': 'file-metadata', 'expected_docs': ['mdls']}
        report = evaluate([case])
        self.assertNotIn('/Users/private', json.dumps(report))
        self.assertEqual(report['cases'][0]['command'], "mdls '<path>'")

    def test_duplicate_case_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'cases.jsonl'
            case = {'id': 'same', 'split': 'dev', 'request': 'show sleep assertions',
                    'expected_status': 'suggestion', 'expected_recipe': 'sleep-assertions',
                    'expected_docs': ['pmset'], 'rubric': 'Assertion snapshot.',
                    'manual_validation': 'pending'}
            path.write_text((json.dumps(case) + '\n') * 2)
            with self.assertRaises(ValueError):
                load_cases(path)

    def test_release_fixture_has_disjoint_splits_and_manual_rubrics(self):
        cases = load_cases(Path('eval/macos.jsonl'))
        self.assertEqual(len(cases), 40)
        self.assertEqual({c['split'] for c in cases}, {'dev', 'heldout'})
        self.assertTrue(all(c['rubric'] and c['manual_validation'] == 'pending' for c in cases))
