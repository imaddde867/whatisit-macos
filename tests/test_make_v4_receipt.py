"""Tests for tools/make_v4_receipt.py against a synthetic campaign dir and OpenCode store."""
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parents[0] / 'tools'))

import make_v4_receipt

VALIDATOR_SRC = (TESTS.parents[0] / 'data/distill/stage2-v4/campaign-20261022/validate_verdict.py')
LABEL = 'p1-20260101-b00-a1'


def make_campaign(root):
    c = Path(root)
    batch = {'batch': 'b00', 'items': [{'case': 'c000000000001', 'candidates': [
        {'key': 'k000000000001', 'command': 'ls'},
        {'key': 'k000000000002', 'command': 'rm -rf /'}]}]}
    verdict = {'batch': 'b00', 'judge': LABEL, 'cases': [{'case': 'c000000000001', 'verdicts': [
        {'key': 'k000000000001', 'verdict': 'correct', 'category': None, 'evidence': 'ls is stock'},
        {'key': 'k000000000002', 'verdict': 'incorrect', 'category': 'unsafe', 'evidence': 'destroys root'}]}]}
    (c / 'pool/batches').mkdir(parents=True)
    (c / 'pool/batches/b00.json').write_text(json.dumps(batch))
    (c / 'pool/manifest.json').write_text(json.dumps({'counts': {'batches': 1}}))
    (c / 'pool/controls-map.json').write_text(json.dumps(
        {'k000000000002': {'expected': 'incorrect'}}))
    (c / 'verdicts').mkdir()
    (c / 'verdicts/b00.json').write_text(json.dumps(verdict))
    prompt = (f'Read data/distill/stage2-v4/LABEL.md and pool/batches/b00.json. '
              f'Write {{"batch": "b00", "judge": "{LABEL}"}} to verdicts/b00.json.')
    (c / 'receipts/pass1/b00/inputs').mkdir(parents=True)
    (c / 'receipts/pass1/b00/prompt.txt').write_text(prompt)
    shutil.copyfile(c / 'pool/batches/b00.json', c / 'receipts/pass1/b00/inputs/b00.json')
    shutil.copyfile(VALIDATOR_SRC, c / 'validate_verdict.py')
    return prompt


def make_db(root, sessions, name='opencode'):
    db_path = Path(root) / f'{name}.db'
    db = sqlite3.connect(db_path)
    db.execute('create table session_v2 (id, directory, title, agent, model, '
               'time_created, time_updated)')
    db.execute('create table session_message (id, session_id, type, seq, data)')
    for sid, prompt_text, tools in sessions:
        db.execute('insert into session_v2 values (?,?,?,?,?,?,?)',
                   (sid, '/repo', 'judge', 'build', 'model-x', 1761100000000, 1761103600000))
        db.execute('insert into session_message values (?,?,?,?,?)',
                   (sid + 'm1', sid, 'user', 1, json.dumps({'text': prompt_text})))
        content = [{'type': 'tool', 'name': name, 'state': {'input': inp}}
                   for name, inp in tools]
        db.execute('insert into session_message values (?,?,?,?,?)',
                   (sid + 'm2', sid, 'assistant', 2, json.dumps({'content': content})))
    db.commit()
    db.close()
    return db_path


GOOD_TOOLS = [('read', {'path': 'data/distill/stage2-v4/LABEL.md'}),
              ('read', {'path': 'pool/batches/b00.json'}),
              ('shell', {'command': 'man -P cat ls | col -b'}),
              ('shell', {'command': 'ls /usr/bin'}),
              ('shell', {'command': 'python3 -c "import json; '
                                    'print(len(json.load(open(\'pool/batches/b00.json\'))))"'}),
              ('write', {'path': 'verdicts/b00.json'})]


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.campaign = Path(self.tmp.name) / 'campaign'
        self.prompt = make_campaign(self.campaign)
        self._probe = 0
        self.db = make_db(self.tmp.name, [
            ('ses_good', self.prompt, GOOD_TOOLS),
            ('ses_peek', self.prompt, GOOD_TOOLS + [('read', {'path': 'pool/controls-map.json'})]),
            ('ses_other', 'unrelated session about something else',
             [('read', {'path': 'README.md'})]),
        ])

    def tearDown(self):
        self.tmp.cleanup()

    def receipt(self, tools, session='ses_probe', prompt=None):
        self._probe += 1
        fake_db = make_db(self.tmp.name, [(session, prompt or self.prompt, tools)],
                          name=f'probe{self._probe}')
        return make_v4_receipt.build_receipt(
            fake_db, self.campaign, 'b00', session)

    def test_find_lists_matching_sessions(self):
        db = make_v4_receipt.open_db(self.db)
        try:
            hits = make_v4_receipt.find_sessions(db, LABEL, 'b00')
        finally:
            db.close()
        ids = {h['session_id'] for h in hits}
        self.assertEqual(ids, {'ses_good', 'ses_peek'})

    def test_clean_session_receipts_with_true(self):
        receipt, out_path, ok = make_v4_receipt.build_receipt(
            self.db, self.campaign, 'b00', 'ses_good')
        self.assertTrue(ok)
        self.assertTrue(receipt['result'])
        self.assertEqual(receipt['judge_label'], LABEL)
        self.assertEqual(receipt['attempt'], 'a1')
        self.assertEqual(receipt['batch_sha256'],
                         hashlib.sha256((self.campaign / 'pool/batches/b00.json').read_bytes()).hexdigest())
        self.assertEqual(receipt['verdict_sha256'],
                         hashlib.sha256((self.campaign / 'verdicts/b00.json').read_bytes()).hexdigest())
        self.assertEqual(receipt['manifest_sha256'],
                         hashlib.sha256((self.campaign / 'pool/manifest.json').read_bytes()).hexdigest())
        self.assertIn('"pass": true', receipt['verdict_validator'])
        self.assertEqual(receipt['audit']['flags'], [])
        out_path.write_text(json.dumps(receipt))

    def test_forbidden_tool_read_voids_result(self):
        receipt, _, ok = make_v4_receipt.build_receipt(
            self.db, self.campaign, 'b00', 'ses_peek')
        self.assertFalse(ok)
        self.assertFalse(receipt['result'])
        self.assertEqual(receipt['audit']['forbidden_reads'], ['pool/controls-map.json'])

    def test_shell_forbidden_read_voids_result(self):
        receipt, _, ok = self.receipt(
            GOOD_TOOLS + [('shell', {'command': 'cat pool/controls-map.json'})])
        self.assertFalse(ok)
        self.assertTrue(receipt['audit']['shell_violations'])

    def test_allowlist_prefix_cannot_be_chained(self):
        for command in ('ls /usr/bin && cat keymap.json',
                        'man ls; cat keymap.json',
                        'sha256sum pool/batches/b00.json; cat controls.jsonl'):
            receipt, _, ok = self.receipt(
                GOOD_TOOLS + [('shell', {'command': command})])
            self.assertFalse(ok, command)
            self.assertTrue(receipt['audit']['shell_violations'], command)

    def test_python_c_cannot_read_the_keymap(self):
        receipt, _, ok = self.receipt(GOOD_TOOLS + [(
            'shell', {'command': 'python3 -c "import json; '
                                 'print(json.load(open(\'keymap.json\')))"'})])
        self.assertFalse(ok)
        self.assertTrue(receipt['audit']['shell_violations'])

    def test_ls_outside_stock_directories_is_rejected(self):
        receipt, _, ok = self.receipt(
            GOOD_TOOLS + [('shell', {'command': 'ls /home/imad'})])
        self.assertFalse(ok)
        self.assertTrue(receipt['audit']['shell_violations'])

    def test_execute_and_network_tools_are_audited(self):
        receipt, _, ok = self.receipt(
            GOOD_TOOLS + [('execute', {'code': 'console.log(1)'}),
                          ('webfetch', {'url': 'https://example.com'})])
        self.assertFalse(ok)
        self.assertTrue(receipt['audit']['shell_violations'])
        self.assertEqual(receipt['audit']['network_or_subagent'][0]['tool'], 'webfetch')

    def test_grep_outside_the_batch_is_rejected(self):
        receipt, _, ok = self.receipt(
            GOOD_TOOLS + [('grep', {'path': 'data/distill/stage2-v4/campaign-20261022',
                                    'pattern': 'expected'})])
        self.assertFalse(ok)
        self.assertTrue(receipt['audit']['search_violations'])

    def test_cross_batch_read_is_rejected(self):
        other = self.campaign / 'receipts/pass1/b01/inputs'
        other.mkdir(parents=True)
        (other / 'b01.json').write_text('{}')
        receipt, _, ok = self.receipt(
            GOOD_TOOLS + [('read', {'path': 'receipts/pass1/b01/inputs/b01.json'})])
        self.assertFalse(ok)
        self.assertTrue(receipt['audit']['disallowed_reads'])

    def test_write_outside_verdict_is_rejected(self):
        receipt, _, ok = self.receipt(
            GOOD_TOOLS + [('write', {'path': 'README.md'})])
        self.assertFalse(ok)
        self.assertEqual(receipt['audit']['writes_outside_verdict'], ['README.md'])

    def test_verdict_label_mismatch_is_rejected(self):
        path = self.campaign / 'verdicts/b00.json'
        original = path.read_text()
        try:
            verdict = json.loads(original)
            verdict['judge'] = 'some-other-judge'
            path.write_text(json.dumps(verdict))
            receipt, _, ok = make_v4_receipt.build_receipt(
                self.db, self.campaign, 'b00', 'ses_good')
        finally:
            path.write_text(original)
        self.assertFalse(ok)
        self.assertTrue(any('!= prompt label' in f for f in receipt['audit']['flags']))

    def test_session_reuse_is_flagged(self):
        other = self.campaign / 'receipts/pass1/b01'
        other.mkdir(parents=True)
        (other / 'receipt.json').write_text(json.dumps(
            {'agent_session_id': 'ses_good', 'judge_label': 'p1-20260101-b01-a1'}))
        receipt, _, ok = make_v4_receipt.build_receipt(
            self.db, self.campaign, 'b00', 'ses_good')
        self.assertFalse(ok)
        self.assertTrue(any('already receipted' in f for f in receipt['audit']['flags']))

    def test_calibration_session_reuse_is_flagged(self):
        other = self.campaign / 'calibration/attempts/20261022-a1'
        other.mkdir(parents=True)
        (other / 'receipt.json').write_text(json.dumps({'agent_session_id': 'ses_good'}))
        receipt, _, ok = make_v4_receipt.build_receipt(
            self.db, self.campaign, 'b00', 'ses_good')
        self.assertFalse(ok)
        self.assertTrue(any('calibration' in f for f in receipt['audit']['flags']))

    def test_unknown_session_is_an_input_error(self):
        with self.assertRaises(SystemExit) as caught:
            make_v4_receipt.build_receipt(self.db, self.campaign, 'b00', 'ses_missing')
        self.assertEqual(caught.exception.code, 2)

    def test_find_without_prompt_is_an_input_error(self):
        (self.campaign / 'receipts/pass1/b00/prompt.txt').unlink()
        with self.assertRaises(SystemExit) as caught:
            make_v4_receipt.main(['find', '--campaign', str(self.campaign),
                                  '--batch', 'b00', '--db', str(self.db)])
        self.assertEqual(caught.exception.code, 2)


if __name__ == '__main__':
    unittest.main()
