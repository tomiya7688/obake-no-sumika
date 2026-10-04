from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.context.script.audit import audit_mapping
from tools.context.script.select_files import load_mapping, normalize_path, select_files


ROOT = Path(__file__).resolve().parents[1]


class ContextSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rules = load_mapping()

    def test_game_change_selects_only_game_context_and_related_test(self) -> None:
        result = select_files(["game.py"], self.rules)
        self.assertEqual(result["contexts"], ["docs/context/project.md", "docs/context/game.md"])
        self.assertEqual(result["tests"], ["tests/test_tagged_conversations.py"])
        self.assertEqual(result["unmapped_files"], [])

    def test_editor_change_selects_tool_context(self) -> None:
        result = select_files(["character_editor.py"], self.rules)
        self.assertEqual(result["contexts"], ["docs/context/project.md", "docs/context/developer_tools.md"])
        self.assertEqual(result["tests"], ["tests/test_character_repository.py"])

    def test_engine_repository_selects_engine_and_game_contexts(self) -> None:
        result = select_files(["engine\\room_repository.py"], self.rules)
        self.assertEqual(result["changed_files"], ["engine/room_repository.py"])
        self.assertIn("docs/context/engine.md", result["contexts"])
        self.assertIn("docs/context/game.md", result["contexts"])
        self.assertEqual(result["tests"], ["tests/test_room_repository.py"])

    def test_unknown_path_is_explicitly_reported(self) -> None:
        result = select_files(["new_feature.py", "./new_feature.py"], self.rules)
        self.assertEqual(result["changed_files"], ["new_feature.py"])
        self.assertEqual(result["unmapped_files"], ["new_feature.py"])

    def test_unsafe_or_absolute_path_is_rejected(self) -> None:
        for value in ("../secret.txt", "C:\\outside.py", "/outside.py", "a//b.py"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_path(value)

    def test_shared_contract_selects_portability_without_game_code(self) -> None:
        result = select_files(["spec/engine/project_manifest_cases.json"], self.rules)
        self.assertEqual(result["contexts"], ["docs/context/project.md", "docs/context/portability.md"])
        self.assertEqual(result["tests"], ["tests/test_portable_project_contract.py", "tests/test_engine_manifest.py"])
        self.assertNotIn("game.py", result["related_files"])
        self.assertEqual(result["unmapped_files"], [])

    def test_responsibility_references_exist(self) -> None:
        for rule in self.rules:
            for field in ("context", "related", "tests"):
                paths = [rule[field]] if field == "context" else rule[field]
                for path in paths:
                    with self.subTest(path=path):
                        self.assertTrue((ROOT / path).is_file())

    def test_json_cli_output_is_machine_readable(self) -> None:
        result = subprocess.run(
            [sys.executable, "tools/context/script/select_files.py", "--json", "room.json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(json.loads(result.stdout)["tests"], ["tests/test_room_repository.py"])

    def test_audit_scope_does_not_make_other_rules_look_unused(self) -> None:
        rule = {"paths": ["engine/*.py", "game.py", "stale.py"],
                "context": "docs/context/project.md", "related": [], "tests": []}
        report = audit_mapping(ROOT, ["engine/room_repository.py", "game.py", "unknown.py"],
                               [rule], ("engine/",))
        self.assertEqual(report["errors"], [])
        self.assertEqual(report["unmapped_files"], [])
        self.assertEqual(report["unmatched_patterns"], ["stale.py"])
        unscoped = audit_mapping(ROOT, ["game.py", "unknown.py"], [rule])
        self.assertEqual(unscoped["unmapped_files"], ["unknown.py"])

    def test_audit_reports_missing_and_escaping_references(self) -> None:
        rule = {"paths": ["game.py"], "context": "missing.md",
                "related": ["../outside.py"], "tests": []}
        report = audit_mapping(ROOT, ["game.py"], [rule])
        self.assertEqual(len(report["errors"]), 2)
        self.assertIn("missing file", report["errors"][0])
        self.assertIn("repository-relative", report["errors"][1])

    def test_mapping_rejects_non_object_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "mapping.json"
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "responsibility table"):
                load_mapping(path)


if __name__ == "__main__":
    unittest.main()
