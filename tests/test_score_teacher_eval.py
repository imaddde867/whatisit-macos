import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from score_teacher_eval import (effective_command, label_case, lint_reject,  # noqa: E402
                                majority, score_case)


def sample(command, parsed=True, finish='stop'):
    return {'command': command, 'reason': '', 'parsed': parsed,
            'finish_reason': finish, 'raw': None}


def case(accept, reference='ref'):
    return {'id': 't001', 'request': 'do the thing', 'reference': reference,
            'accept': accept}


class LabelCaseTests(unittest.TestCase):
    def test_pass_wrong_and_rejected(self):
        c = case(r'^stat -f %B notes\.txt$')
        self.assertEqual(label_case(c, 'stat -f %B notes.txt'), 'pass')
        self.assertEqual(label_case(c, 'stat -c %W notes.txt'), 'wrong')
        self.assertEqual(label_case(c, None), 'rejected')

    def test_accept_list_matches_any(self):
        c = case([r'\bmkdir\b', r'\binstall\b'])
        self.assertEqual(label_case(c, 'install -d dir'), 'pass')

    def test_null_accept_is_abstention(self):
        c = case(None)
        self.assertEqual(label_case(c, None), 'abstain-ok')
        self.assertEqual(label_case(c, 'rm note.txt'), 'abstain-missed')


class MajorityTests(unittest.TestCase):
    def test_three_of_five_agree(self):
        samples = [sample('stat -f %B notes.txt')] * 3 + [sample('ls'), sample('pwd')]
        self.assertEqual(majority(samples), ('stat -f %B notes.txt', 'command'))

    def test_three_nulls_are_an_abstention(self):
        samples = [sample(None)] * 3 + [sample('ls'), sample('pwd')]
        self.assertEqual(majority(samples), (None, 'abstention'))

    def test_no_majority(self):
        samples = [sample('ls')] * 2 + [sample('pwd')] * 2 + [sample(None)]
        self.assertEqual(majority(samples), (None, 'none'))

    def test_unparsed_and_non_stop_samples_do_not_vote(self):
        samples = [sample('ls'), sample('ls'), sample('ls'),
                   sample('pwd', parsed=False), sample('ls', finish='length')]
        self.assertEqual(majority(samples), ('ls', 'command'))

    def test_majority_counts_raw_strings_before_linting(self):
        # Three identical commands that the lint would reject still form a
        # majority; score_case then reports the lint rejection separately.
        samples = [sample('rm -rf /')] * 3 + [sample('ls'), sample('pwd')]
        self.assertEqual(majority(samples), ('rm -rf /', 'command'))
        result = score_case(case(r'^rm\b'), samples)
        self.assertEqual(result['majority'], 'rejected')
        self.assertEqual(result['rejection_cause'], 'lint/safety rejected')


class LintRejectTests(unittest.TestCase):
    def test_control_chars_and_length(self):
        self.assertTrue(lint_reject('echo a\r\nb', 'request'))
        self.assertTrue(lint_reject('echo ' + 'x' * 4097, 'request'))
        self.assertFalse(lint_reject('echo xx', 'request'))

    def test_safety_danger(self):
        self.assertTrue(lint_reject('rm -rf /', 'delete the root'))
        self.assertTrue(lint_reject('rm -rf $EMPTY/', 'delete a thing'))

    def test_maclint_rejects_tool_missing_from_path(self):
        original = os.environ.get('PATH')
        try:
            os.environ['PATH'] = '/nonexistent-bin'
            self.assertTrue(lint_reject('stat -f %B notes.txt', 'notes'))
        finally:
            os.environ['PATH'] = original

    def test_placeholder_hint_rule_uses_the_request(self):
        # `/path/to/` matches the hint only when the request does not name it.
        self.assertTrue(lint_reject('cat /path/to/file.txt', 'show the file'))
        self.assertFalse(lint_reject('cat /path/to/file.txt',
                                     'cat /path/to/file.txt please'))


class EffectiveCommandTests(unittest.TestCase):
    def test_unparsed_or_non_stop_is_no_command(self):
        self.assertIsNone(effective_command(sample('ls', parsed=False), 'r'))
        self.assertIsNone(effective_command(sample('ls', finish='length'), 'r'))
        self.assertIsNone(effective_command(sample(None), 'r'))

    def test_lint_rejected_sample_contributes_no_command(self):
        self.assertIsNone(effective_command(sample('rm -rf /'), 'r'))
        self.assertEqual(effective_command(sample('echo hi'), 'r'), 'echo hi')


class ScoreCaseTests(unittest.TestCase):
    def test_sample_and_oracle_counts(self):
        samples = [sample('stat -f %B notes.txt')] * 3 + [
            sample('stat -c %W notes.txt'), sample('ls')]
        result = score_case(case(r'^stat -f %B notes\.txt$'), samples)
        self.assertEqual(result['majority'], 'pass')
        self.assertEqual(result['sample_correct'], 3)
        self.assertTrue(result['oracle'])

    def test_oracle_false_when_no_sample_passes(self):
        result = score_case(case(r'^stat\b'), [sample('ls'), sample('pwd'),
                                               sample('ls'), sample('pwd'),
                                               sample('ls')])
        self.assertEqual(result['majority'], 'wrong')
        self.assertFalse(result['oracle'])


if __name__ == '__main__':
    unittest.main()
