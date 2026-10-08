import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from whatisit_macos.build_docs import main
from whatisit_macos.retrieval import search


class CaptureTests(unittest.TestCase):
    def test_existing_capture_is_preserved_without_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / 'manuals.sqlite3'
            index.write_bytes(b'previous capture')
            with patch('sys.argv', ['build-docs', str(index)]), \
                    patch('whatisit_macos.build_docs.platform.system', return_value='Darwin'), \
                    patch('subprocess.run', side_effect=AssertionError('unexpected execution')), \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main()
            self.assertEqual(error.exception.code, 2)
            self.assertEqual(index.read_bytes(), b'previous capture')

    def test_shadowed_path_cannot_bind_apple_manual_to_gnu_stat(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shadow = root / 'stat'
            shadow.write_text('#!/bin/sh\nexit 99\n')
            shadow.chmod(0o755)
            index = root / 'manuals.sqlite3'
            recipe = {'id': 'stat-fixture', 'title': 'stat file status',
                      'argv': ['stat', '/tmp/public-fixture'], 'match_groups': [['stat']],
                      'notes': ['File status report.'], 'sources': ['man stat']}

            def render(command, **kwargs):
                if command == ['/usr/bin/sw_vers', '-productVersion']:
                    output = '27.0.1\n'
                elif command == ['/usr/bin/man', '-M', '/usr/share/man', '-w', '1', 'stat']:
                    output = '/usr/share/man/man1/stat.1\n'
                elif command == ['/usr/bin/man', '-M', '/usr/share/man', '1', 'stat']:
                    output = 'stat file status: BSD -f format\n'
                elif command == ['/usr/bin/col', '-b']:
                    output = kwargs['input']
                else:
                    raise AssertionError(f'Unexpected command: {command}')
                return subprocess.CompletedProcess(command, 0, stdout=output, stderr='')

            stdout = io.StringIO()
            with patch.dict(os.environ, {'PATH': str(root)}), \
                    patch('sys.argv', ['build-docs', str(index)]), \
                    patch('whatisit_macos.build_docs.platform.system', return_value='Darwin'), \
                    patch('whatisit_macos.build_docs.TOOLS', (('stat', '1'),)), \
                    patch('whatisit_macos.build_docs.load_recipes', return_value=[recipe]), \
                    patch('subprocess.run', side_effect=render), contextlib.redirect_stdout(stdout):
                main()
            inventory = json.loads(stdout.getvalue())['inventory']
            self.assertEqual(inventory[0]['tool_path'], '/usr/bin/stat')
            hits = search(index, 'stat')
            self.assertEqual({hit['source'] for hit in hits},
                             {'/usr/share/man/man1/stat.1', 'catalog:stat-fixture'})
            self.assertEqual({hit['tool_path'] for hit in hits}, {'/usr/bin/stat'})
