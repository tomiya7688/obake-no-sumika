from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
