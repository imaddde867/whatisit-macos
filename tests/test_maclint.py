import unittest

from whatisit_macos.maclint import problems

GOOD = ["sysctl -n hw.memsize", "du -h -d 1 . | sort -h", "lsof -nP -iTCP:8080 -sTCP:LISTEN", "sed -i '' 's/a/b/' f",
        "date -v-1d +%F", "stat -f %m f", "find . -size +100M", "tar -czf logs.tar.gz logs/",
        "sysctl -n hw.ncpu", "vm_stat", "find . -name '*.log' -exec ls -l {} \\;"]
BAD = ["sysctl -n vm.mem_free_bytes", "tail -n 50 /var/log/nope-missing.log", "cat /proc/cpuinfo", "du -h --max-depth=1 | sort -rh", "sed -i 's/a/b/g' f", "stat -c %y f",
       "date -d '1 day ago' +%F", "free -m", "xclip -selection clipboard < f", "nproc",
       "find . -maxdepth 1 -type f -printf '%s %p\\n'", "ps aux --sort=-%mem | head",
       "grep -P 'a+' f"]


class MacLintTests(unittest.TestCase):
    def test_accepts_macos_commands(self):
        for command in GOOD:
            with self.subTest(command=command):
                self.assertEqual(problems(command), [])

    def test_rejects_gnu_and_linux_commands(self):
        for command in BAD:
            with self.subTest(command=command):
                self.assertTrue(problems(command))


if __name__ == '__main__':
    unittest.main()
