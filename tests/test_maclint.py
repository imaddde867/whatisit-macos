import sys
import unittest

from whatisit_macos.maclint import problems, unrequested_deletion

GOOD = ["command -v python3", "hdiutil attach -readonly -nobrowse d.iso", "launchctl print gui/$(id -u)", "sysctl -n hw.memsize", "du -h -d 1 . | sort -h", "lsof -nP -iTCP:8080 -sTCP:LISTEN", "sed -i '' 's/a/b/' f",
        "date -v-1d +%F", "stat -f %m f", "find . -size +100M", "tar -czf logs.tar.gz logs/",
        "sysctl -n hw.ncpu", "vm_stat", "find . -name '*.log' -exec ls -l {} \\;",
        "git log --oneline -5", "git log --oneline -n 5", "grep -rn TODO .", "cp -r a b", "chmod -w notes.txt",
        ": > todo.txt", "nohup ./backup.sh &", "perl -pi -e 's/a/b/' f"]
BAD = ["touch -d @{{1}} {{f}}", "sysctl -n vm.mem_free_bytes", "tail -n 50 /var/log/nope-missing.log", "cat /proc/cpuinfo", "du -h --max-depth=1 | sort -rh", "sed -i 's/a/b/g' f", "stat -c %y f",
       "date -d '1 day ago' +%F", "free -m", "xclip -selection clipboard < f", "nproc",
       "find . -maxdepth 1 -type f -printf '%s %p\\n'", "ps aux --sort=-%mem | head",
       "grep -P 'a+' f", "find . -name '*.jpeg' -exec rename 's/a/b/' {} +"]


@unittest.skipUnless(sys.platform == 'darwin', 'lint reads this Mac\'s PATH and man pages')
class MacLintTests(unittest.TestCase):
    def test_accepts_macos_commands(self):
        for command in GOOD:
            with self.subTest(command=command):
                self.assertEqual(problems(command), [])

    def test_rejects_gnu_and_linux_commands(self):
        for command in BAD:
            with self.subTest(command=command):
                self.assertTrue(problems(command))

    def test_deletion_requires_a_named_target(self):
        for request, command in [
                ('delete notes.txt', 'rm notes.txt'),
                ('remove the .tmp files in this folder', "find . -name '*.tmp' -delete"),
                ('delete the old-build directory', 'rm -rf old-build'),
                ('delete all .DS_Store files here', 'find . -name .DS_Store -print0 | xargs -0 rm')]:
            with self.subTest(command=command):
                self.assertEqual(unrequested_deletion(command, request), [])
        for request, command in [
                ('delete every app cache', 'rm -rf ~/Library/Caches'),
                ('delete all the duplicate photos', 'mdfind -name dup | xargs rm -f'),
                ('free some space', 'find /Applications -name "*.app" -exec rm -rfv {} \\;'),
                ('delete everything', 'rm -rf *')]:
            with self.subTest(command=command):
                self.assertTrue(unrequested_deletion(command, request))


if __name__ == '__main__':
    unittest.main()
