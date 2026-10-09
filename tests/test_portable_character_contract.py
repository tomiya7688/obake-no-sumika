"""Shared basic character validation; filesystem and Python coercion parity are separate."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from engine.character_repository import CharacterRepository
from tests.godot_support import find_test_godot


GODOT = find_test_godot()
CASES_PATH = ROOT / "spec/character/characters_cases.json"


def document_for(suite: dict, case: dict) -> object:
    if "document" in case:
        return copy.deepcopy(case["document"])
    item = {**copy.deepcopy(suite["base_definition"]), **copy.deepcopy(case.get("changes", {}))}
    for field in case.get("remove", []):
        item.pop(field)
    extras = [{**copy.deepcopy(suite["base_definition"]), **extra}
              for extra in case.get("extra_characters", [])]
    return {"schema_version": case.get("schema_version", 1), "characters": [item, *extras]}


def expected_result(suite: dict, case: dict) -> list[dict]:
    return [{**suite["base_definition"], "bubble_y_offset": 0, "behavior_weights": {},
             **case["expected"].get("changes", {})}]


class PortableCharacterContractTests(unittest.TestCase):
    def test_shared_cases_against_python_repository(self) -> None:
        suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        self.assertEqual(suite["schema_version"], 1)
        self.assertEqual(len({case["id"] for case in suite["cases"]}), len(suite["cases"]))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ghost.png").touch()
            data_path = root / "characters.json"
            repository = CharacterRepository(root, data_path, tuple(suite["room_size"]))
            for case in suite["cases"]:
                with self.subTest(case=case["id"]):
                    data_path.write_text(json.dumps(document_for(suite, case), ensure_ascii=False), encoding="utf-8")
                    before = data_path.read_bytes()
                    if case["expected"]["status"] == "rejected":
                        with self.assertRaises(ValueError):
                            repository.load()
                    else:
                        results = [{"id": item.id, "display_name": item.display_name,
                                    "image": item.image.relative_to(root).as_posix(),
                                    "start_position": [item.start_x, item.start_y],
                                    "display_height": item.display_height, "personality": item.personality,
                                    "native_facing": item.native_facing, "bubble_y_offset": item.bubble_y_offset,
                                    "behavior_weights": dict(item.behavior_weights)} for item in repository.load()]
                        self.assertEqual(results, expected_result(suite, case))
                    self.assertEqual(data_path.read_bytes(), before)


@unittest.skipUnless(GODOT, "Godot runtime unavailable; set GODOT_BIN")
class GodotCharacterContractTests(unittest.TestCase):
    def run_requests(self, requests: list[dict]) -> list[dict]:
        with tempfile.TemporaryDirectory(prefix="character contract 日本語 ") as directory:
            root = Path(directory)
            path, report = root / "requests.json", root / "report.json"
            path.write_text(json.dumps(requests, ensure_ascii=False), encoding="utf-8")
            before = path.read_bytes()
            process = subprocess.run(
                [str(GODOT), "--headless", "--path", str(ROOT / "godot"), "--script",
                 "res://tests/test_character_schema.gd", "--", str(path), str(report)],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            output = process.stdout + process.stderr
            self.assertEqual(process.returncode, 0, output)
            self.assertNotIn("SCRIPT ERROR:", output)
            self.assertNotIn("\nERROR:", output)
            self.assertIn(f"GODOT_CHARACTER_TESTS cases={len(requests)}", output)
            self.assertEqual(path.read_bytes(), before)
            results = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual([result["id"] for result in results], [item["id"] for item in requests])
            return results

    def test_shared_cases_against_godot_reader(self) -> None:
        suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        requests = [{"id": case["id"], "document": document_for(suite, case), "room_size": suite["room_size"]}
                    for case in suite["cases"]]
        for case, result in zip(suite["cases"], self.run_requests(requests)):
            with self.subTest(case=case["id"]):
                self.assertEqual(result["status"], case["expected"]["status"], result)
                if result["status"] == "accepted":
                    self.assertEqual(result["result"], expected_result(suite, case))
                else:
                    self.assertTrue(result["error"])
                    self.assertNotIn("result", result)

    def test_stricter_godot_boundaries_and_non_finite_values(self) -> None:
        suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        requests = []
        for index, changes in enumerate(({"id": 1}, {"display_height": "64"},
                                          {"personality": "1.0"}, {"start_position": [1e100, 200]})):
            requests.append({"id": str(index), "document": document_for(suite, {"changes": changes}),
                             "room_size": suite["room_size"]})
        for field in ("display_height", "personality", "native_facing", "bubble_y_offset"):
            requests.append({"id": field, "document": document_for(suite, {}), "non_finite": field,
                             "room_size": suite["room_size"]})
        requests.append({"id": "valid-after-failure", "document": document_for(suite, {}),
                         "room_size": suite["room_size"]})
        results = self.run_requests(requests)
        self.assertTrue(all(result["status"] == "rejected" for result in results[:-1]), results)
        self.assertEqual(results[-1]["result"], expected_result(suite, {"expected": {}}))


if __name__ == "__main__":
    unittest.main()
