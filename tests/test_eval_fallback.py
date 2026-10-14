from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import eval_fallback


class EvalDetailTests(unittest.TestCase):
    def test_detail_preserves_labels_and_distinguishes_rejections(self):
        reasons = ['Local generation returned no complete command.',
                   'Generated command is not valid on macOS: placeholder',
                   'Local generation returned a command flagged as dangerous.',
                   'Local generation failed: test', '']
        commands = [None, None, None, None, 'pwd']
        cases = [{'id': str(i), 'request': 'probe', 'accept': 'pwd', 'reference': 'pwd'}
                 for i in range(5)]
        writes = {}
        with patch.object(sys, 'argv', ['eval_fallback.py', 'dev', 'lint', '-q']), \
             patch.object(Path, 'read_text', return_value='\n'.join(map(json.dumps, cases))), \
             patch.object(Path, 'write_text', autospec=True,
                          side_effect=lambda p, s: writes.update({str(p): json.loads(s)})), \
             patch.object(eval_fallback.local_recovery_worker, 'suggest',
                          side_effect=[{'command': c, 'reason': r} for c, r in zip(commands, reasons)]):
            self.assertEqual(eval_fallback.main(), 0)
        labels = writes['/tmp/eval-dev-lint.json']
        self.assertEqual(labels, {str(i): 'rejected' if i < 4 else 'pass' for i in range(5)})
        detail = writes['/tmp/eval-dev-lint-detail.json']
        for i, kind in enumerate(['empty_output', 'lint', 'danger', 'other', 'other']):
            self.assertEqual(detail[str(i)], {'label': labels[str(i)], 'command': commands[i],
                                             'reason': reasons[i], 'no_command_kind': kind})
