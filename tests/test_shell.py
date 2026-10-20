import unittest

from whatisit_macos.shell import Command, Word, parse


class ShellTests(unittest.TestCase):
    def test_compact_operators_and_redirects_preserve_all_commands(self):
        commands = parse('cat<input|sort 2>&1&&echo ok||printf fail;: >output &')
        self.assertEqual([c.name for c in commands], ['cat', 'sort', 'echo', 'printf', ':'])
        self.assertEqual(commands[0].redirects, (Word('input'),))
        self.assertEqual(commands[1].redirects, (Word('1'),))
        self.assertEqual(commands[-1].redirects, (Word('output'),))
        self.assertEqual([c.name for c in parse('ls|&head')], ['ls', 'head'])

    def test_quotes_escapes_and_empty_words_are_data(self):
        command, = parse(r'''printf '' ';' "&&" a\ b '\$(rm f)' '$HOME' \* "~" ''')
        self.assertEqual([w.value for w in command.words],
                         ['printf', '', ';', '&&', 'a b', r'\$(rm f)', '$HOME', '*', '~'])
        self.assertFalse(any(w.dynamic or w.home for w in command.words))

    def test_expanded_operands_are_distinguished_from_literals(self):
        command, = parse('ls $HOME "${USER}" *.txt ~/notes "*" \'~/notes\'')
        self.assertEqual([(w.dynamic, w.home) for w in command.words[1:]],
                         [(True, False), (True, False), (True, False), (False, True),
                          (False, False), (False, False)])

    def test_wrappers_resolve_the_actual_command(self):
        for text in ('sudo -n -u root /bin/rm notes', 'env -i LANG=C rm notes',
                     'command -p rm notes', 'exec rm notes', 'nohup rm notes',
                     'time -p rm notes', 'LANG=C sudo -- rm notes'):
            with self.subTest(command=text):
                command, = parse(text)
                self.assertEqual(command.name, 'rm')
                self.assertEqual(command.words[-1], Word('notes'))
        command, = parse('command -v missing-tool')
        self.assertTrue(command.lookup)
        self.assertEqual(command.name, 'missing-tool')

    def test_wrappers_preserve_original_executable_paths(self):
        command, = parse('/tmp/sudo /usr/bin/env LANG=C /bin/rm notes')
        self.assertEqual(command.wrappers, (Word('/tmp/sudo'), Word('/usr/bin/env')))

    def test_quoted_assignment_name_is_a_command(self):
        command, = parse("'FOO=bar' ls")
        self.assertEqual(command.words[0], Word('FOO=bar'))
        command, = parse("FOO='bar' ls")
        self.assertEqual(command.name, 'ls')

    def test_find_exec_child_and_terminator_remain_distinct(self):
        commands = parse(r"find . -name '*.log' -exec ls -l '{}' \;")
        self.assertEqual([c.name for c in commands], ['find', 'ls'])
        self.assertEqual([w.value for w in commands[0].words], ['find', '.', '-name', '*.log'])
        self.assertTrue(commands[1].indirect)
        self.assertEqual([c.name for c in parse("find . -exec ls '{}' '+'")], ['find', 'ls'])
        with self.assertRaises(ValueError):
            parse('find . -exec ls {} ; echo unseen')

    def test_xargs_marks_child_as_indirect(self):
        command, = parse('xargs -0 -n 1 -I {} /bin/ls {}')
        self.assertEqual(command.name, 'ls')
        self.assertTrue(command.indirect)

    def test_xargs_replacement_cannot_construct_a_command(self):
        for text in ('xargs -I ls ls notes', 'xargs -Ifoo /bin/foo notes',
                     'xargs -J ls ls notes'):
            with self.subTest(command=text), self.assertRaises(ValueError):
                parse(text)

    def test_find_plus_is_data_unless_it_terminates_a_batch(self):
        commands = parse(r'find . -exec printf + {} \;')
        self.assertEqual([w.value for w in commands[1].words], ['printf', '+', '{}'])
        with self.assertRaises(ValueError):
            parse('find . -exec ls +')

    def test_find_expression_cannot_be_supplied_by_expansion_or_input(self):
        for text in ('find . "$ACTION"', 'find *.txt -print',
                     r"printf '%s\n' -delete | xargs find .",
                     r'find . -exec find {} \;', 'xargs command find .'):
            with self.subTest(command=text), self.assertRaises(ValueError):
                parse(text)

    def test_find_predicate_operands_are_literal_data(self):
        for text in ("find . -name '-delete' -print", "find . -name '-exec' -print",
                     "find . -path '-execdir' -print", "find . -newer '-delete' -print"):
            with self.subTest(command=text):
                command, = parse(text)
                self.assertEqual(command.name, 'find')
        for text in ('find . -delete', "find . '-delete'", 'find . -name x -delete',
                     'find . -unsupported x -print', 'find . -name',
                     r"find . -name '-exec' -exec ls {} \; -delete"):
            with self.subTest(command=text), self.assertRaises(ValueError):
                parse(text)

    def test_dynamic_assignments_cannot_change_executable_resolution(self):
        for text in ('printf PATH | xargs -I VAR env VAR=/tmp echo hello',
                     'xargs -I VAR env VAR=/tmp command echo hello',
                     'xargs -I VAR VAR=/tmp echo hello', 'VAR=$HOME echo hello'):
            with self.subTest(command=text), self.assertRaises(ValueError):
                parse(text)

    def test_unsupported_execution_wrappers_are_not_ordinary_commands(self):
        for wrapper in ('nice', 'caffeinate', 'arch', 'builtin', 'doas', 'busybox',
                        'toybox', 'timeout', 'ionice', 'stdbuf', 'setsid', 'chroot',
                        'xcrun', 'taskpolicy'):
            for prefix in ('', '/usr/bin/'):
                with self.subTest(wrapper=prefix + wrapper), self.assertRaises(ValueError):
                    parse(f'{prefix}{wrapper} rm /tmp/other')

    def test_launchctl_execution_subcommands_fail_closed(self):
        for text in ('launchctl asuser 501 rm /tmp/other',
                     '/bin/launchctl bsexec 1 rm /tmp/other',
                     'launchctl submit -l job -- rm /tmp/other',
                     'launchctl "$ACTION" 501 rm /tmp/other',
                     'xargs launchctl'):
            with self.subTest(command=text), self.assertRaises(ValueError):
                parse(text)
        command, = parse('launchctl print gui/501')
        self.assertEqual(command.name, 'launchctl')
        self.assertEqual(command.words[-1], Word('gui/501'))

    def test_literal_bracket_builtin_is_not_a_dynamic_command(self):
        commands = parse('[ -t 1 ] && echo yes || echo no')
        self.assertEqual([c.name for c in commands], ['[', 'echo', 'echo'])
        self.assertFalse(commands[0].words[0].dynamic)
        with self.assertRaises(ValueError):
            parse("xargs -I '[' '[' -t 1 ]")

    def test_zsh_numeric_globs_cannot_be_misread_as_redirects(self):
        for text in ('rm foo<1-10>bar', 'rm <->', 'rm foo<1->bar', 'rm <-10>'):
            with self.subTest(command=text), self.assertRaises(ValueError):
                parse(text)
        command, = parse("rm 'foo<1-10>bar'")
        self.assertEqual(command.words[-1], Word('foo<1-10>bar'))
        self.assertEqual(command.redirects, ())

    def test_active_interactive_history_expansion_is_rejected(self):
        for text in ('echo !!', 'echo !-1', 'rm !:1', 'echo "!!"', 'echo !previous'):
            with self.subTest(command=text), self.assertRaises(ValueError):
                parse(text)
        for text in ("echo '!!'", r'echo \!\!', "find . ! -name '*.log'", 'echo !='):
            with self.subTest(command=text):
                self.assertTrue(parse(text))

    def test_plain_scripts_and_text_processors_are_retained(self):
        for text in ("awk '{print $1}' file", "sed -i '' 's/a/b/' file",
                     "perl -pi -e 's/a/b/' file", './backup.sh', 'nohup ./backup.sh &',
                     "printf '%s' '#literal'", "'if' argument", ': >file', '>file'):
            with self.subTest(command=text):
                self.assertTrue(parse(text))

    def test_fixed_read_only_substitutions_are_dynamic_data(self):
        for sub in ('$(pwd)', '$(pwd -P)', '$(whoami)', '$(id -un)', '$(id -u)',
                    '$(sw_vers -productVersion)', '$(uname -m)', '$(date +%Y%m%d)'):
            for text in (f'ln -s "{sub}/notes.md" notes-link', f'echo {sub}'):
                with self.subTest(command=text):
                    command, = parse(text)
                    self.assertTrue(any(w.dynamic and sub in w.value for w in command.words[1:]))

    def test_other_substitutions_stay_rejected(self):
        for text in ('echo $(id)', 'echo $(pwd; rm f)', 'echo $(pwd) $(rm f)', 'echo "$(id -un; id)"',
                     'echo $(date +%s;rm f)', 'echo $(date -f x)', 'echo $(whoami -x)',
                     'echo $(cat f)', 'echo $(pwd | sh)', '$(pwd)', 'x=$(pwd) ls'):
            with self.subTest(command=text), self.assertRaises(ValueError):
                parse(text)

    def test_zsh_only_dollar_expansions_are_rejected_unless_literal(self):
        for expansion in ('$[1]', '$~HOME', '$+HOME', '$=HOME', '$^HOME', '$.'):
            for text in (f'rm {expansion}', f'rm "{expansion}"', f'rm a{expansion}'):
                with self.subTest(command=text), self.assertRaises(ValueError):
                    parse(text)
            for text in (f"rm '{expansion}'", f'rm "\\{expansion}"', f'rm \\{expansion}'):
                with self.subTest(command=text):
                    self.assertEqual(parse(text)[0].words[1].value, expansion)
        for text in ('rm $', 'rm a$', 'rm $ b', 'rm "$ b"'):
            with self.subTest(command=text):
                self.assertTrue(parse(text))

    def test_unsupported_or_malformed_syntax_fails_closed(self):
        rejected = [
            '', '   ', 'ls |', '| ls', 'ls &&', 'ls;;echo no', 'ls & echo no',
            'echo "unterminated', 'echo trailing\\', 'cat >', 'cat <<EOF',
            'echo $(id)', 'echo "$(id)"', 'echo `id`', 'echo "`id`"',
            'cat <(ls)', 'echo $((1+2))', 'echo ${HOME:-/tmp}',
            'echo ${HOME%/*}', '$COMMAND file', '${COMMAND} file',
            'if true; then ls; fi', 'for x in a; do echo x; done',
            '(ls)', '{ ls; }', 'f() { ls; }', '! ls', 'ls\npwd',
            'eval ls', 'source script', '. script', 'sh -c ls', 'bash',
            'env -S "rm notes"', 'env -u VAR ls', 'sudo --unknown ls',
            'command -x ls', 'exec -a alias ls', 'nohup -x ls', 'time -x ls',
            'xargs --unknown ls', 'xargs', 'find . -exec ls {}',
            'PATH=/tmp ls', 'IFS=x rm notes', 'env PATH=/tmp ls',
            'echo hi # ignored command', 'echo a{b,c}',
            '=ls', 'export PATH=/tmp; ls', 'alias rm=ls; rm notes',
            'unset PATH; ls', 'set -f; rm notes', 'read COMMAND; $COMMAND',
            r'find . -exec {} \;', r'find . -exec /bin/{} \;',
            'xargs -I rm command rm notes',
            "trap 'rm notes' EXIT", 'HOME=/tmp :; rm ~/notes',
            'repeat 2 rm notes', 'autoload rm; rm notes',
        ]
        for text in rejected:
            with self.subTest(command=text), self.assertRaises(ValueError):
                parse(text)


if __name__ == '__main__':
    unittest.main()
