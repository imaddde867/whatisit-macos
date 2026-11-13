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
    (c / 'pool/manifest.json').write_text(json.dumps({'batch_size': 2}))
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


def make_db(root):
    db_path = Path(root) / 'opencode.db'
    db = sqlite3.connect(db_path)
    db.execute('create table session_v2 (id, directory, title, agent, model, '
               'time_created, time_updated)')
    db.execute('create table session_message (id, session_id, type, seq, data)')
    db.commit()
    db.close()
    return db_path


def add_session(db_path, sid, prompt_text, tools):
    db = sqlite3.connect(db_path)
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


GOOD_TOOLS = [('read', {'path': 'data/distill/stage2-v4/LABEL.md'}),
              ('read', {'path': 'pool/batches/b00.json'}),
              ('shell', {'command': 'man -P cat ls | col -b'}),
              ('write', {'path': 'verdicts/b00.json'})]


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.campaign = Path(self.tmp.name) / 'campaign'
        self.prompt = make_campaign(self.campaign)
        self.db = make_db(self.tmp.name)
        add_session(self.db, 'ses_good', self.prompt, GOOD_TOOLS)
        add_session(self.db, 'ses_peek', self.prompt,
                    GOOD_TOOLS + [('read', {'path': 'pool/controls-map.json'})])
        add_session(self.db, 'ses_other', 'unrelated session about something else',
                    [('read', {'path': 'README.md'})])

    def tearDown(self):
        self.tmp.cleanup()

    def receipt_for(self, sid):
        return make_v4_receipt.build_receipt(self.db, self.campaign, 'b00', sid)

    def add(self, sid, tools):
        add_session(self.db, sid, self.prompt, GOOD_TOOLS + tools)
        return sid

    def test_find_lists_matching_sessions(self):
        db = make_v4_receipt.open_db(self.db)
        try:
            hits = make_v4_receipt.find_sessions(db, LABEL, 'b00')
        finally:
            db.close()
        self.assertEqual({h['session_id'] for h in hits}, {'ses_good', 'ses_peek'})

    def test_clean_session_receipts_with_true(self):
        receipt, out_path, ok = self.receipt_for('ses_good')
        self.assertTrue(ok)
        self.assertTrue(receipt['result'])
        self.assertEqual(receipt['judge_label'], LABEL)
        self.assertEqual(receipt['attempt'], 'a1')
        self.assertEqual(receipt['batch_sha256'],
                         hashlib.sha256((self.campaign / 'pool/batches/b00.json').read_bytes()).hexdigest())
        self.assertEqual(receipt['manifest_sha256'],
                         hashlib.sha256((self.campaign / 'pool/manifest.json').read_bytes()).hexdigest())
        self.assertIn('"pass": true', receipt['verdict_validator'])
        out_path.write_text(json.dumps(receipt))

    def test_forbidden_tool_read_voids_result(self):
        receipt, _, ok = self.receipt_for('ses_peek')
        self.assertFalse(ok)
        self.assertEqual(receipt['audit']['forbidden_reads'], ['pool/controls-map.json'])

    def test_shell_cat_of_forbidden_file_voids_result(self):
        sid = self.add('ses_cat', [('shell', {'command': 'cat pool/controls-map.json'})])
        receipt, _, ok = self.receipt_for(sid)
        self.assertFalse(ok)
        self.assertEqual(receipt['audit']['forbidden_shell'],
                         ['cat pool/controls-map.json'])

    def test_chained_shell_bypass_is_not_safe(self):
        sid = self.add('ses_chain', [('shell', {'command': 'ls && cat keymap.json'})])
        receipt, _, ok = self.receipt_for(sid)
        self.assertFalse(ok)
        self.assertTrue(receipt['audit']['forbidden_shell'])
        sid2 = self.add('ses_chain2', [('shell', {'command': 'ls && cat notes.txt'})])
        receipt2, _, ok2 = self.receipt_for(sid2)
        self.assertFalse(ok2)
        self.assertTrue(receipt2['audit']['shell_needs_review'])

    def test_python_json_load_of_forbidden_file_voids_result(self):
        sid = self.add('ses_py', [('shell', {'command':
                         "python3 -c \"import json; print(json.load(open('keymap.json')))\""})])
        receipt, _, ok = self.receipt_for(sid)
        self.assertFalse(ok)
        self.assertTrue(receipt['audit']['forbidden_shell'])

    def test_execute_and_web_tools_are_visible(self):
        sid = self.add('ses_exec', [('execute', {'code': 'print(1)'}),
                                    ('websearch', {'query': 'answer'})])
        receipt, _, ok = self.receipt_for(sid)
        self.assertFalse(ok)
        self.assertIn('print(1)', receipt['audit']['shells'])
        self.assertTrue(any('network/delegation' in f for f in receipt['audit']['flags']))

    def test_grep_directory_search_voids_result(self):
        sid = self.add('ses_grep', [('grep', {'path': 'data/distill/stage2-v4',
                                              'pattern': 'expected'})])
        receipt, _, ok = self.receipt_for(sid)
        self.assertFalse(ok)
        self.assertTrue(receipt['audit']['forbidden_reads'])

    def test_cross_batch_read_voids_result(self):
        sid = self.add('ses_xb', [('read', {'path': 'pool/batches/b01.json'})])
        receipt, _, ok = self.receipt_for(sid)
        self.assertFalse(ok)
        self.assertEqual(receipt['audit']['forbidden_reads'], ['pool/batches/b01.json'])

    def test_write_outside_verdict_voids_result(self):
        sid = self.add('ses_write', [('write', {'path': 'notes.txt'})])
        receipt, _, ok = self.receipt_for(sid)
        self.assertFalse(ok)
        self.assertEqual(receipt['audit']['writes_outside_verdict'], ['notes.txt'])

    def test_verdict_judge_mismatch_voids_result(self):
        verdict_path = self.campaign / 'verdicts/b00.json'
        verdict = json.loads(verdict_path.read_text())
        verdict['judge'] = 'p1-20260101-b00-a9'
        verdict_path.write_text(json.dumps(verdict))
        receipt, _, ok = self.receipt_for('ses_good')
        self.assertFalse(ok)
        self.assertTrue(any('!= prompt label' in f for f in receipt['audit']['flags']))

    def test_unknown_session_fails_closed(self):
        with self.assertRaises(SystemExit) as ctx:
            self.receipt_for('ses_missing')
        self.assertEqual(ctx.exception.code, 2)

    def test_missing_db_exits_two(self):
        with self.assertRaises(SystemExit) as ctx:
            make_v4_receipt.open_db(Path(self.tmp.name) / 'nope.db')
        self.assertEqual(ctx.exception.code, 2)

    def test_session_reuse_is_flagged(self):
        other = self.campaign / 'receipts/pass1/b01'
        other.mkdir(parents=True)
        (other / 'receipt.json').write_text(json.dumps(
            {'agent_session_id': 'ses_good', 'judge_label': 'p1-20260101-b01-a1'}))
        _, _, ok = self.receipt_for('ses_good')
        self.assertFalse(ok)
        self.assertTrue(any('already receipted' in f for f in
                            self.receipt_for('ses_good')[0]['audit']['flags']))

    def test_reuse_against_calibration_receipt_is_flagged(self):
        cal = self.campaign / 'calibration/attempts/20260101-a1'
        cal.mkdir(parents=True)
        (cal / 'receipt.json').write_text(json.dumps(
            {'agent_session_id': 'ses_good', 'judge_label': 'cal-20260101-a1'}))
        _, _, ok = self.receipt_for('ses_good')
        self.assertFalse(ok)

    def test_receipt_mode_returns_one_on_failure(self):
        code = make_v4_receipt.main(['receipt', '--campaign', str(self.campaign),
                                     '--batch', 'b00', '--session', 'ses_peek',
                                     '--db', str(self.db)])
        self.assertEqual(code, 1)
        written = self.campaign / 'receipts/pass1/b00/receipt.json'
        self.assertFalse(json.loads(written.read_text())['result'])


if __name__ == '__main__':
    unittest.main()
