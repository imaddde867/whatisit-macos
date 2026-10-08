import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from whatisit_macos.build_docs import main


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
