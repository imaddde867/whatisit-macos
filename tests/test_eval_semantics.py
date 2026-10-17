import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def cases():
    return {
        case['id']: case
        for split in ('dev', 'everyday')
        for case in (json.loads(line) for line in (ROOT / 'eval' / f'{split}.jsonl').read_text().splitlines())
    }


def accepts(case, command):
    patterns = [case['accept']] if isinstance(case['accept'], str) else case['accept']
    return any(re.search(pattern, command) for pattern in patterns)


class EvalSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = cases()

    def test_m016_accepts_quoted_field_separator(self):
        self.assertTrue(accepts(self.cases['m016'], "awk -F':' '{print $3}' input.txt"))

    def test_m016_rejects_shell_expanded_field(self):
        self.assertFalse(accepts(self.cases['m016'], 'awk -F: "{print $3}" input.txt'))
        self.assertTrue(accepts(self.cases['m016'], 'cut -d: -f3 input.txt'))

    def test_m026_rejects_self_matching_grep(self):
        self.assertFalse(accepts(self.cases['m026'], 'ps aux | grep Finder'))
        self.assertTrue(accepts(self.cases['m026'], "ps aux | grep '[F]inder'"))

    def test_m052_rejects_unreliable_filter(self):
        self.assertFalse(accepts(self.cases['m052'], "pmset -g sched | grep 'sleep|wake'"))
        self.assertTrue(accepts(self.cases['m052'], 'pmset -g sched'))

    def test_e012_requires_five_regular_files(self):
        self.assertFalse(accepts(self.cases['e012'], 'ls -lS | head -n 6'))
        self.assertFalse(accepts(self.cases['e012'], 'ls -lS | head -n 5'))
        self.assertFalse(accepts(self.cases['e012'], 'ls -1S | head -5'))
        self.assertTrue(accepts(self.cases['e012'], self.cases['e012']['reference']))

    def test_e038_rejects_a_command_that_launches_chrome(self):
        self.assertFalse(accepts(self.cases['e038'], 'pgrep -x "Google Chrome" || osascript -e \'tell application "Google Chrome" to launch\''))
        self.assertTrue(accepts(self.cases['e038'], 'pgrep -x "Google Chrome"'))
        self.assertTrue(accepts(self.cases['e038'], 'ps aux | grep -i chrome'))

    def test_e050_rejects_endpoint_only_output(self):
        self.assertFalse(accepts(self.cases['e050'], "lsof -i -P -n | awk '{print $9}'"))
        for command in self.cases['e050']['also_correct']:
            self.assertTrue(accepts(self.cases['e050'], command), command)

    def test_references_and_alternatives_remain_accepted(self):
        for case_id in ('m016', 'm026', 'm052', 'e012', 'e038', 'e050'):
            case = self.cases[case_id]
            for command in [case['reference'], *(case.get('also_correct') or [])]:
                self.assertTrue(accepts(case, command), (case_id, command))

    def test_traps_and_wrong_examples_remain_rejected(self):
        for case_id in ('m016', 'm026', 'm052', 'e012', 'e038', 'e050'):
            case = self.cases[case_id]
            for command in [*(case.get('traps') or []), *(case.get('wrong_examples') or [])]:
                self.assertFalse(accepts(case, command), (case_id, command))


if __name__ == '__main__':
    unittest.main()
