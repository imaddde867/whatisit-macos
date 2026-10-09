import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

try:
    from tools import experiment
except ImportError:
    experiment = None


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(experiment, 'Comparison measurement harness is not implemented')

    def test_frozen_baseline_stays_three_recipe_router(self):
        router = experiment.baseline()
        answer = router('Verify app signature', system='Darwin', which=lambda tool: tool,
                        path='/tmp/example.app')
        self.assertEqual(answer['status'], 'unsupported')
        self.assertIsNone(answer['command'])
        self.assertEqual(router('show sleep assertions', system='Darwin', which=lambda tool: tool)['argv'],
                         ['pmset', '-g', 'assertions'])

    def test_tree_rss_includes_all_descendants_not_unrelated_processes(self):
        processes = [(10, 1, 100), (11, 10, 200), (12, 11, 300), (13, 1, 9999)]
        self.assertEqual(experiment.tree_rss(10, processes), 600 * 1024)

    def test_hash_is_content_based(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data'
            path.write_text('abc')
            self.assertEqual(experiment.sha256(path),
                             'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')

    def test_worker_expanded_renders_without_executing_task_command(self):
        with tempfile.TemporaryDirectory() as directory:
            from whatisit_macos.retrieval import Manual, build_index
            index = Path(directory) / 'docs.sqlite3'
            build_index(index, [Manual('codesign', 'test:codesign', '/usr/bin/codesign',
                                       '27.0.1', '2026-10-09', 'Verify app signature integrity.')])
            with patch.object(experiment, 'rss_bytes', return_value=1024), \
                    patch('tools.experiment.platform.system', return_value='Darwin'), \
                    patch('tools.experiment.shutil.which', side_effect=lambda tool: tool), \
                    patch('subprocess.run', side_effect=AssertionError('Task command executed')):
                report = experiment.worker('B', [{'id': 'app', 'request': 'verify app signature',
                                                  'path': '/tmp/example.app', 'expected_status': 'suggestion',
                                                  'expected_recipe': 'app-signature'}], index, None, 2)
            self.assertEqual(report['rows'][0]['answer']['argv'],
                             ['codesign', '--verify', '--deep', '--strict', '--verbose=2', '/tmp/example.app'])
            self.assertEqual(report['contract_matches'], 2)
            self.assertEqual(report['warm_ms']['samples'], 1)
            self.assertIsNone(report['model_load_ms'])
