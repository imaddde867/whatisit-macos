import sys
from collections import Counter
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_distill_dataset as builder


class VotingKeyTests(unittest.TestCase):
    def test_surface_forms_merge(self):
        for a, b in [
            ('ls -la ./folder/', 'ls -a -l folder/'),
            ("cat 'a.txt'", 'cat "a.txt"'),
            ('du -sh ~/Documents/', 'du -h -s "$HOME/Documents/"'),
            ('ls --color=always a', 'ls --color always a'),
            ('git status --short ./folder/', 'git status --short folder/'),
            ('cat ./a | sort -r | head -n 5', 'cat a | sort -r | head -n 5'),
            ("df -Pk a | awk '{print $4}'", "df -k -P ./a | awk '{print $4}'"),
            ("grep '*.txt' a", 'grep "*.txt" a'),
            ('system_profiler -xml SPPowerDataType', 'system_profiler SPPowerDataType -xml'),
            ('ls ./a > ./out', 'ls a > out'),
            ("ls './a' && cat './b'", 'ls a && cat b'),
            ('cp -Rpv a b', 'cp -p -R -v ./a b'),
            ('ps -o ruid,uid -p 4200', 'ps -p 4200 -o ruid,uid'),
            ('find workspace -mindepth 1 -maxdepth 2 -type d',
             'find workspace -maxdepth 2 -mindepth 1 -type d'),
            ('mdfind -onlyin paper-tests/ "author == 2"', 'mdfind "author == 2" -onlyin paper-tests'),
            ('mdls -raw -name kMDItemFinderComment a', 'mdls -name kMDItemFinderComment -raw ./a'),
            ('git -C project log --pretty=format:%s v1.0..HEAD',
             'git -C project/ log v1.0..HEAD --pretty=format:%s'),
            ('date -j -u -f "%Y" 2025', 'date -u -j -f "%Y" 2025'),
            ('iostat -d disk4 -w 1 -c 5', 'iostat -d -w 1 -c 5 disk4'),
            ('openssl req -in request.csr -noout -text', 'openssl req -in request.csr -text -noout'),
            ('xcodebuild -project MyApp.xcodeproj -list', 'xcodebuild -list -project MyApp.xcodeproj'),
            ('hdiutil attach backup.dmg -nobrowse', 'hdiutil attach -nobrowse backup.dmg'),
            ('cat ~/a*', 'cat $HOME/a*'),
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
            ("awk '{print $4}' a", 'awk "{print $4}" a'),
            ('cat "$USER/a"', 'cat $USER/a'),
            ("cat '$HOME/a'", "cat '~/a'"),
            ("echo '|' hi", 'echo | hi'),
            ('grep -e "$USER" a', 'grep -e $USER a'),
            ('find . -name a -o -name b -type f', 'find . -type f -name a -o -name b'),
            ('find . -name a -print', 'find . -print -name a'),
            ('cp -R a/ b', 'cp -R a b'), ('ps -w', 'ps -ww'),
            ('cp -f -i a b', 'cp -i -f a b'),
            ('unknown --foo a --bar b', 'unknown --bar a --foo b'),
            ('date -v +1m -v -1d', 'date -v -1d -v +1m'),
            ('lsof -sTCP:LISTEN', 'lsof -sTCP:ESTABLISHED'),
            ('head -n 5 -n 10 a', 'head -n 10 -n 5 a'),
            ("zip -r project.zip project -x 'project/build/*' 'project/build/'",
             "zip -r project.zip project -x 'project/build/*' 'project/build'"),
            ('sysctl -n ./hw.ncpu', 'sysctl -n hw.ncpu'),
            ('networksetup -getinfo Ethernet/', 'networksetup -getinfo Ethernet'),
            ('stat -f foo/ a', 'stat -f foo a'),
            ('du -B 512 -t 1024 a', 'du -t 512 -B 1024 a'),
            ('ls "[ab]"', 'ls [ab]'), ('ls "{a,b}"', 'ls {a,b}'),
            ('du -h -k a', 'du -k -h a'),
            ('python3 -c "./foo"', 'python3 -c "foo"'),
            ('cat < input', "cat '<' input"), ('cat > output', "cat '>' output"),
            ('cat ./', "cat ''"), ('cat .//a', 'cat /a'),
            ('cat file', 'cat file/'), ('ls -l link', 'ls -l link/'),
            ('ls -t -S a', 'ls -S -t a'), ('ls -l -c -u a', 'ls -l -u -c a'),
            ('find -H -L .', 'find -L -H .'),
            ('cat input>output', "cat 'input>output'"),
            ('cat input<other', "cat 'input<other'"),
            ('grep -C ./5 x input', 'grep -C 5 x input'),
            ('cat ~/a*', 'cat "$HOME/a*"'),
            ("echo '$x'$y", "echo $x'$y'"),
            ("cat a'>'b>c", "cat a>'b>c'"),
            ("cat $USER'x'", 'cat $USERx'), ('cat $USER"x"', 'cat $USERx'),
        ]:
            with self.subTest(a=a, b=b):
                self.assertNotEqual(builder.voting_key(a), builder.voting_key(b))

    def test_no_empty_keys_and_invalid_commands_are_singletons(self):
        for command in ('', ' ', '|', 'true', 'echo hi', 'ls | sort', "cat 'bad"):
            self.assertTrue(builder.voting_key(command))
        self.assertNotEqual(builder.voting_key("cat 'bad"), builder.voting_key("cat 'bad2"))

    def test_label_preserves_exact_majority_and_tiebreaks_cluster(self):
        self.assertEqual(builder.command_vote(Counter({'ls -la a': 3, 'ls -a -l ./a': 2}),
                                             'equivalence')[0], 'ls -la a')
        target, size, strings = builder.command_vote(
            Counter({'ls -la a': 2, 'ls -al ./a': 2, 'cat b': 1}), 'equivalence')
        self.assertEqual((target, size, strings), ('ls -la a', 4, ['ls -al ./a', 'ls -la a']))
        self.assertIsNone(builder.command_vote(Counter({'ls -la a': 2, 'ls -al ./a': 2}), 'exact')[0])


if __name__ == '__main__':
    unittest.main()
