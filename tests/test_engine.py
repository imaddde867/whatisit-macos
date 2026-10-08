import json
import os
import shlex
import unittest
from pathlib import Path

from whatisit_macos.engine import load_recipes, suggest


def available(tool):
    return f"/usr/bin/{tool}"


def query(request, **kwargs):
    return suggest(request, system="Darwin", which=available, **kwargs)


class EngineTests(unittest.TestCase):
    def test_seed_cases(self):
        fixture = Path(__file__).resolve().parents[1] / "eval" / "cases.jsonl"
        for line in fixture.read_text().splitlines():
            case = json.loads(line)
            with self.subTest(case=case["id"]):
                answer = query(case["request"], path=case.get("path"))
                self.assertEqual(answer["status"], case["expected_status"])
                self.assertEqual(answer.get("recipe_id"), case.get("expected_recipe"))

    def test_sleep_uses_assertion_report(self):
        self.assertEqual(query("show sleep assertions")["argv"], ["pmset", "-g", "assertions"])

    def test_battery_uses_power_report(self):
        self.assertEqual(query("battery cycle count")["argv"], ["system_profiler", "SPPowerDataType"])

    def test_missing_path_has_no_command(self):
        answer = query("show file metadata")
        self.assertEqual(answer["missing"], ["path"])
        self.assertIsNone(answer["command"])

    def test_metacharacters_remain_one_argument(self):
        path = "/tmp/a file'; $(touch /tmp/not-executed).pdf"
        answer = query("show file metadata", path=path)
        self.assertEqual(shlex.split(answer["command"]), ["mdls", path])

    def test_option_looking_path_becomes_absolute(self):
        answer = query("show file metadata", path="-name")
        self.assertEqual(answer["argv"], ["mdls", os.path.abspath("-name")])

    def test_control_characters_do_not_produce_command(self):
        for path in ["/tmp/a\nb", "/tmp/a\rb", "/tmp/a\x00b"]:
            with self.subTest(path=repr(path)):
                answer = query("show file metadata", path=path)
                self.assertEqual(answer["status"], "needs-input")
                self.assertIsNone(answer["command"])

    def test_non_macos_does_not_suggest(self):
        for system in ["Linux", "Windows"]:
            answer = suggest("show sleep assertions", system=system, which=available)
            self.assertEqual(answer["status"], "unsupported")
            self.assertIsNone(answer["command"])

    def test_missing_tool_does_not_suggest(self):
        answer = suggest("show sleep assertions", system="Darwin", which=lambda _: None)
        self.assertEqual(answer["status"], "unavailable")
        self.assertIsNone(answer["command"])

    def test_irrelevant_path_is_not_silently_ignored(self):
        self.assertEqual(query("battery cycle count", path="/tmp/example")["status"], "needs-input")

    def test_unsupported_qualifiers_do_not_return_partial_answers(self):
        requests = [
            "Report my battery cycle count and maximum capacity as JSON",
            "Print only the battery cycle count number",
            "Show battery cycles as XML", "Show battery cycles and health",
            "Show only kMDItemContentType from file metadata",
            "Show metadata for every file recursively",
            "Show Spotlight attributes for all documents",
            "Show file metadata and verify its signature",
            "Show sleep assertions over the last 24 hours",
            "Continuously monitor sleep assertions",
            "Show yesterday's sleep assertions", "Watch sleep assertions live",
            "Show battery cycle count and unified logs",
        ]
        for request in requests:
            with self.subTest(request=request):
                answer = query(request, path="/tmp/example" if "metadata" in request else None)
                self.assertEqual(answer["status"], "unsupported")
                self.assertIsNone(answer["command"])

    def test_spotlight_attribute_paraphrases_require_and_quote_path(self):
        for request in ["Which Spotlight attributes belong to this document?",
                        "List indexed attributes for a file"]:
            with self.subTest(request=request):
                answer = query(request)
                self.assertEqual(answer["status"], "needs-input")
                self.assertEqual(answer["missing"], ["path"])
                self.assertEqual(query(request, path="/tmp/a file.pdf")["argv"],
                                 ["mdls", "/tmp/a file.pdf"])

    def test_broad_wake_diagnosis_is_not_an_assertion_snapshot(self):
        self.assertEqual(query("What is keeping my computer awake?")["status"], "unsupported")
        self.assertEqual(query("show current sleep assertions")["argv"],
                         ["pmset", "-g", "assertions"])

    def test_catalog_has_unique_ids_and_sources(self):
        recipes = load_recipes()
        self.assertEqual(len({r["id"] for r in recipes}), len(recipes))
        for recipe in recipes:
            self.assertTrue(recipe["sources"])
            self.assertTrue(recipe["notes"])
            self.assertEqual(set(recipe["parameters"]), {arg[1:-1] for arg in recipe["argv"] if arg.startswith("{")})


if __name__ == "__main__":
    unittest.main()
