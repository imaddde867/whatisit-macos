"""Structural safety checks never execute the candidate commands."""
import unittest
from unittest.mock import patch

from whatisit_macos import maclint


class CommandSafetyTests(unittest.TestCase):
    def test_rejects_hidden_execution_without_host_or_scanner_help(self):
        commands = [
            'echo ok;rm /tmp/other.txt', 'echo ok&&rm /tmp/other.txt',
            'echo ok||rm /tmp/other.txt', 'echo ok|rm /tmp/other.txt',
            '/bin/rm /tmp/other.txt', "sh -c 'rm /tmp/other.txt'",
            "eval 'rm /tmp/other.txt'", 'echo $(rm /tmp/other.txt)',
            'echo `rm /tmp/other.txt`', '(rm /tmp/other.txt)',
            'if true; then rm /tmp/other.txt; fi',
            "find . -name '*.tmp' -o -delete",
            "find . -exec sh -c 'rm /tmp/other.txt' \\;",
            "find . -name '*.tmp';echo /tmp/other.txt|xargs rm",
            'xargs -0 /bin/rm', 'env X=1 /bin/rm /tmp/other.txt',
        ]
        with patch.object(maclint, '_man_text', return_value=''), \
                patch.object(maclint.shutil, 'which', side_effect=lambda c: '/usr/bin/' + c):
            for command in commands:
                with self.subTest(command=command):
                    self.assertTrue(maclint.problems(command) +
                                    maclint.unrequested_deletion(command, 'list files'))

    def test_requires_whole_case_sensitive_target(self):
        for request, command in [
            ('delete ~/Downloads/notes.txt', 'rm /tmp/other/notes.txt'),
            ('delete old-notes.txt', 'rm notes.txt'),
            ('delete Notes.txt', 'rm notes.txt'),
            ('delete notes.txt', 'rm notes.txt*'),
            ('delete notes.txt*', 'rm notes.txt*'),
            ('delete notes.txt', 'rm "$TARGET"'),
            ('delete archive-old/log-old', 'rmdir -p archive-old/log-old'),
            ('delete notes.txt', 'cd /tmp/other;rm notes.txt'),
            ('delete everything', 'rm -- -notes.txt'),
            ('delete notes.txt', 'rm -unknown notes.txt'),
            ('delete notes.txt', 'rm notes.txt other.txt'),
            ('delete ////', 'rm -rf ////'),
            ('delete ./././', 'rm -rf ./././'),
            ('delete /tmp/../', 'rm -rf /tmp/../'),
            ('delete ~/notes.txt', 'rm "~/notes.txt"'),
        ]:
            with self.subTest(command=command, request=request):
                self.assertTrue(maclint.unrequested_deletion(command, request))

    def test_accepts_exact_literal_targets(self):
        for request, command in [
            ('delete notes.txt', 'rm notes.txt'),
            ('delete ./notes.txt', 'rm notes.txt'),
            ('delete notes.txt', 'rm ./notes.txt'),
            ('delete "notes old.txt"', "rm 'notes old.txt'"),
            ('delete ~/notes.txt', 'rm ~/notes.txt'),
            ('delete /tmp/notes.txt', '/bin/rm /tmp/notes.txt'),
            ('delete -notes.txt', 'rm -- -notes.txt'),
            ('delete notes.txt*', "rm 'notes.txt*'"),
            ('delete old-build', 'sudo -u nobody rm -rf old-build'),
            ('delete shortcut.pdf', 'unlink shortcut.pdf'),
            ('delete old-previews', 'rmdir old-previews'),
        ]:
            with self.subTest(command=command):
                self.assertEqual(maclint.unrequested_deletion(command, request), [])

    def test_structured_path_does_not_authorize_other_targets(self):
        self.assertEqual(maclint.unrequested_deletion('rm /tmp/my-file', 'delete this file',
                                                      path='/tmp/my-file'), [])
        self.assertTrue(maclint.unrequested_deletion('rm /elsewhere/my-file', 'delete this file',
                                                     path='/tmp/my-file'))
        self.assertTrue(maclint.unrequested_deletion('rm /tmp/my-file',
                            'delete this file. Explicit inputs: {"path":"/tmp/my-file"}'))

    def test_plain_commands_preserve_literal_operators_and_redirects(self):
        for command in ["printf '%s' ';'", r'echo \; rm', "echo '$(rm /tmp/x)'",
                        'echo hello>/tmp/output', 'cat<input|sort>output',
                        "find . -name '*.log' -exec ls -l {} \\;", 'nohup ./backup.sh &']:
            with patch.object(maclint, '_man_text', return_value=''), \
                    patch.object(maclint.shutil, 'which', side_effect=lambda c: '/usr/bin/' + c):
                with self.subTest(command=command):
                    self.assertEqual(maclint.problems(command), [])
                    self.assertEqual(maclint.unrequested_deletion(command, 'show files'), [])

    def test_malformed_deletion_fails_closed(self):
        self.assertTrue(maclint.unrequested_deletion("rm 'notes.txt", 'delete notes.txt'))


if __name__ == '__main__':
    unittest.main()
