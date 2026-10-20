import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('audit_command_policy', ROOT / 'tools/audit_command_policy.py')
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class AuditPolicyTests(unittest.TestCase):
    def test_counts_categories_and_bounded_examples(self):
        candidates = [('list', None, command) for command in ('same', 'reject', 'recover', 'reject')]
        result = audit.compare(candidates, lambda command, request, path: command == 'recover',
                               lambda command, request, path: {'deletion_guard': ['reason']}
                               if command == 'reject' else {}, example_limit=1)
        self.assertEqual(result['counts'], {'total': 4, 'before_accepted': 3, 'after_accepted': 2,
                                           'newly_rejected': 2, 'newly_accepted': 1})
        self.assertEqual(result['new_rejection_categories'], {'deletion_guard': 2})
        self.assertEqual(len(result['examples']), 1)

    def test_candidates_include_only_training_targets_and_complete_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def write(name, rows):
                path = root / name
                path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
                return path
            requests = write('requests', [{'id': 'a', 'request': 'list', 'path': '/tmp/a'}])
            train = write('train', [{'id': 'a', 'messages': [{'content': 'ls'}]},
                                    {'id': 'a', 'messages': [{'content': ''}]}])
            raw = write('raw', [{'request': 'show', 'samples': [
                {'parsed': True, 'finish_reason': 'stop', 'command': 'cat a'},
                {'parsed': False, 'finish_reason': 'stop', 'command': 'bad'},
                {'parsed': True, 'finish_reason': 'length', 'command': 'bad'},
                {'parsed': True, 'finish_reason': 'stop', 'command': None}]}])
            result = audit.training_candidates(train, requests, raw)
            self.assertEqual(result['v3_nonempty_targets'], [('list', '/tmp/a', 'ls')])
            self.assertEqual(result['parsed_complete_teacher_samples'], [('show', None, 'cat a')])

    def test_non_mac_default_refuses_before_loading_scanner_or_baseline(self):
        with patch.object(audit.platform, 'system', return_value='Linux'), \
                patch.object(audit.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'macOS'):
                audit.audit_policy()
            run.assert_not_called()

    def test_cli_refuses_to_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.json'
            output.write_text('existing')
            with patch.object(audit, 'audit_policy') as run:
                with self.assertRaises(FileExistsError):
                    audit.main(['--output', str(output), '--structural-only'])
                run.assert_not_called()
            self.assertEqual(output.read_text(), 'existing')


if __name__ == '__main__':
    unittest.main()
