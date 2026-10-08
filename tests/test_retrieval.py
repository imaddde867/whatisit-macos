import tempfile
import unittest
from pathlib import Path

from whatisit_macos import retrieval


class RetrievalTests(unittest.TestCase):
    def test_search_returns_matching_evidence_with_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / 'docs.sqlite3'
            manuals = [retrieval.Manual('pmset', '/usr/share/man/man1/pmset.1',
                       '/usr/bin/pmset', '27.0.1', '2026-10-08',
                       'GETTING\n\n-g assertions displays a summary of power assertions.'),
                       retrieval.Manual('mdls', '/usr/share/man/man1/mdls.1',
                       '/usr/bin/mdls', '27.0.1', '2026-10-08',
                       'DESCRIPTION\n\nLists metadata attributes for a file.')]
            retrieval.build_index(index, manuals)
            hits = retrieval.search(index, 'sleep power assertions')
            self.assertEqual(hits[0]['tool'], 'pmset')
            self.assertIn('-g assertions', hits[0]['text'])
            self.assertEqual(hits[0]['source'], '/usr/share/man/man1/pmset.1')
            self.assertEqual(hits[0]['macos_version'], '27.0.1')
            self.assertEqual(len(hits[0]['sha256']), 64)
            self.assertEqual(retrieval.search(index, 'zzzz_unknown'), [])
            self.assertEqual(retrieval.search(index, '" OR *'), [])
            with self.assertRaises(FileExistsError):
                retrieval.build_index(index, manuals)

    def test_missing_index_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / 'absent.sqlite3'
            with self.assertRaises((OSError, retrieval.sqlite3.Error)):
                retrieval.search(index, 'power assertions')
            self.assertFalse(index.exists())

    def test_empty_capture_does_not_leave_an_index(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory) / 'docs.sqlite3'
            with self.assertRaises(ValueError):
                retrieval.build_index(index, [])
            self.assertFalse(index.exists())
