import json
import tempfile
import unittest
from pathlib import Path

from tools.evaluate import load_cases, evaluate


class EvaluationTests(unittest.TestCase):
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
