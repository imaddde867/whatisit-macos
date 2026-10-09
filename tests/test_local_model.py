import tempfile
import unittest
from pathlib import Path

try:
    from whatisit_macos import local_model
except ImportError:
    local_model = None
from whatisit_macos.retrieval import Manual, build_index


class LocalModelTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(local_model, 'Optional local adapter is not implemented')
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.index = Path(self.directory.name) / 'docs.sqlite3'
        build_index(self.index, [Manual('codesign', 'test:codesign', '/usr/bin/codesign',
                                       '27.0.1', '2026-10-09', 'Verify app signature integrity.')])

    def answer(self, output, *, path=None, request='Check this app signature', system='Darwin'):
        return local_model.suggest_with_model(
            request, index=self.index, select=lambda messages: output,
            system=system, which=lambda tool: tool, path=path)

    def test_selected_template_uses_only_supplied_path(self):
        answer = self.answer('{"operation":"app-signature"}', path="/tmp/a'; $(touch nope).app")
        self.assertEqual(answer['argv'], ['codesign', '--verify', '--deep', '--strict',
                                          '--verbose=2', "/tmp/a'; $(touch nope).app"])
        self.assertEqual(answer['documentation'][0]['source'], 'test:codesign')

    def test_missing_input_is_derived_from_catalog(self):
        answer = self.answer('{"operation":"app-signature"}')
        self.assertEqual(answer['status'], 'needs-input')
        self.assertEqual(answer['missing'], ['path'])
        self.assertIsNone(answer['command'])

    def test_model_cannot_supply_commands_arguments_or_unknown_operations(self):
        for output in ['{"operation":"rm"}', '{"operation":"app-signature","path":"/invented.app"}',
                       '{"operation":"app-signature","command":"rm -rf /"}', '[]',
                       '{"operation":42}', '```json\n{"operation":"app-signature"}\n```',
                       '{"operation":null}', 'not JSON']:
            with self.subTest(output=output):
                answer = self.answer(output, path='/tmp/app.app')
                self.assertEqual(answer['status'], 'unsupported')
                self.assertIsNone(answer['command'])

    def test_model_cannot_bypass_platform_scope_or_path_validation(self):
        for kwargs in [dict(system='Linux'), dict(request='Check app signature and Gatekeeper'),
                       dict(path='/tmp/a\n.app'), dict(request='Verify app signature recursively')]:
            with self.subTest(kwargs=kwargs):
                answer = self.answer('{"operation":"app-signature"}', **kwargs)
                self.assertIsNone(answer['command'])

    def test_model_cannot_return_one_part_of_two_baseline_operations(self):
        answer = self.answer('{"operation":"battery-cycles"}',
                             request='Show battery cycle count and sleep assertions')
        self.assertEqual(answer['status'], 'unsupported')
        self.assertIsNone(answer['command'])

    def test_missing_evidence_does_not_call_model(self):
        self.index = self.index.with_name('missing.sqlite3')
        answer = local_model.suggest_with_model(
            'Verify app signature', index=self.index,
            select=lambda _: self.fail('Model called without evidence'),
            system='Darwin', which=lambda tool: tool)
        self.assertEqual(answer['status'], 'unsupported')
        self.assertIn('documentation_error', answer)
        self.assertFalse(self.index.exists())

    def test_prompt_bounds_evidence_and_does_not_include_private_path(self):
        messages = local_model.messages('Verify app signature', [{'text': 'x' * 10000}] * 10,
                                        path_supplied=True)
        content = messages[1]['content']
        self.assertLess(len(content), 13000)
        self.assertNotIn('/Users/', content)
        self.assertIn('path_supplied', content)

    def test_local_directory_required_before_runtime_import(self):
        with self.assertRaises(ValueError):
            local_model.LocalModel(Path('/not/a/model')).load()


if __name__ == '__main__':
    unittest.main()
