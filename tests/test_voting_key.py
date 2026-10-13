import sys
from collections import Counter
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_distill_dataset as builder


class VotingKeyTests(unittest.TestCase):
    def test_surface_forms_merge(self):
        for a, b in [
            ('ls -la ./folder/', 'ls -a -l folder'),
            ("cat 'a.txt'", 'cat "a.txt"'),
            ('du -sh ~/Documents/', 'du -h -s "$HOME/Documents"'),
            ('ls --color=always a', 'ls --color always a'),
            ('git status --short ./folder/', 'git status --short folder'),
            ('cat ./a | sort -r | head -n 5', 'cat a | sort -r | head -n 5'),
        ]:
            with self.subTest(a=a, b=b):
                self.assertEqual(builder.voting_key(a), builder.voting_key(b))

    def test_meaning_does_not_merge(self):
        for a, b in [
            ('head -n 5 a', 'head -n 10 b'),
            ('head -n 5 a', 'head -n 10 a'),
            ('head -n 5 a', 'head -n 5 b'),
            ("grep 'foo' a", "grep 'bar' a"),
            ('sysctl -n hw.ncpu', 'sysctl -n hw.pagesize'),
            ('curl https://a.example/x', 'curl https://b.example/x'),
            ('ls -l', 'ls -la'), ('grep foo a', 'grep -i foo a'),
            ('ls a', 'cat a'), ('ls a', 'ls a | sort'),
            ('ls | sort', 'ls | head'), ('ls a && cat b', 'ls a; cat b'),
            ('cp a b', 'cp b a'), ('head -n 5 -c 10 a', 'head -n 10 -c 5 a'),
            ('cat a a', 'cat a'), ('cat -- -x', 'cat -x'),
            ('cat a > x', 'cat a > y'), ('sudo ls', 'ls'),
            ('cat "$HOME/a"', "cat '$HOME/a'"),
            ('ls "*.txt"', 'ls *.txt'), ('echo "~"', 'echo ~'),
            ('grep "./foo" a', 'grep foo a'),
            ('/tmp/ls a', '/bin/ls a'),
            ('echo ./foo', 'echo foo'), ('ls a |', 'ls a'),
            ('sort -n -g a', 'sort -g -n a'), ('head -c 10 -n 5 a', 'head -n 5 -c 10 a'),
            ('head -bogus a', 'head -b a'),
        ]:
            with self.subTest(a=a, b=b):
                self.assertNotEqual(builder.voting_key(a), builder.voting_key(b))

    def test_no_empty_keys_and_invalid_commands_are_singletons(self):
        for command in ('', ' ', '|', 'true', 'echo hi', 'ls | sort', "cat 'bad"):
            self.assertTrue(builder.voting_key(command))
        self.assertNotEqual(builder.voting_key("cat 'bad"), builder.voting_key("cat 'bad2"))

    def test_label_preserves_exact_majority_and_tiebreaks_cluster(self):
        self.assertEqual(builder.command_vote(Counter({'ls -la a': 3, 'ls -a -l ./a/': 2}),
                                             'equivalence')[0], 'ls -la a')
        target, size, strings = builder.command_vote(
            Counter({'ls -la a': 2, 'ls -al ./a/': 2, 'cat b': 1}), 'equivalence')
        self.assertEqual((target, size, strings), ('ls -la a', 4, ['ls -al ./a/', 'ls -la a']))
        self.assertIsNone(builder.command_vote(Counter({'ls -la a': 2, 'ls -al ./a/': 2}), 'exact')[0])


if __name__ == '__main__':
    unittest.main()
