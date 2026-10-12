"""Shared RGB/gradient-spacing contract, not all background geometry or rendering."""

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

from engine.room_repository import RoomRepository
from tests.godot_support import find_test_godot


GODOT = find_test_godot()
CASES_PATH = ROOT / "spec/map/background_palette_cases.json"


def document_for(suite: dict, case: dict) -> object:
    if "document" in case:
        return copy.deepcopy(case["document"])
    result = copy.deepcopy(suite["base_definition"])
    for path, value in case.get("set", {}).items():
        parent, field = parent_for(result, path)
        parent[field] = copy.deepcopy(value)
    for path in case.get("remove", []):
        parent, field = parent_for(result, path)
        del parent[field]
    return result


def parent_for(document: dict, path: str) -> tuple[object, str | int]:
    parts = path.split(".")
    current = document
    for part in parts[:-1]:
        current = current[int(part) if isinstance(current, list) else part]
    return current, int(parts[-1]) if isinstance(current, list) else parts[-1]


def room_for(suite: dict, background: object) -> dict:
    raw = json.loads((ROOT / suite["base_room_fixture"]).read_text(encoding="utf-8"))["base_definition"]
    # Supply only the unrelated required vignette, never fill in fields that a
    # rejection case deliberately removed from its gradient/polygon palette.
    raw["background"] = {"vignette": raw["background"]["vignette"], **background} if isinstance(background, dict) else background
    return raw


class PortablePaletteContractTests(unittest.TestCase):
    def test_shared_cases_against_python_repository(self) -> None:
        suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        self.assertEqual(suite["schema_version"], 1)
        self.assertEqual(len({case["id"] for case in suite["cases"]}), len(suite["cases"]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "room.json"
            repository = RoomRepository(path)
            for case in suite["cases"]:
                with self.subTest(case=case["id"]):
                    document = document_for(suite, case)
                    raw = room_for(suite, document)
                    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
                    before = path.read_bytes()
                    if case["expected"]["status"] == "rejected":
                        with self.assertRaises(ValueError):
                            repository.load()
                    else:
                        room = repository.load()
                        self.assertEqual(room.height, suite["room_height"])
                        self.assertEqual(list(room.gradient_top), document["gradient"]["top"])
                        self.assertEqual(list(room.gradient_bottom), document["gradient"]["bottom"])
                        self.assertEqual(room.gradient_step, document["gradient"]["step"])
                        self.assertEqual([list(layer[0]) for layer in room.polygon_layers],
                                         [layer["color"] for layer in document["polygons"]])
                    self.assertEqual(path.read_bytes(), before)


@unittest.skipUnless(GODOT, "Godot runtime unavailable; set GODOT_BIN")
class GodotPaletteContractTests(unittest.TestCase):
    def run_requests(self, requests: list[dict]) -> list[dict]:
        with tempfile.TemporaryDirectory(prefix="palette contract 日本語 ") as directory:
            path, report = Path(directory) / "requests.json", Path(directory) / "report.json"
            path.write_text(json.dumps(requests, ensure_ascii=False), encoding="utf-8")
            before = path.read_bytes()
            process = subprocess.run(
                [str(GODOT), "--headless", "--path", str(ROOT / "godot"), "--script",
                 "res://tests/test_background_palette.gd", "--", str(path), str(report)],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            output = process.stdout + process.stderr
            self.assertEqual(process.returncode, 0, output)
            self.assertNotIn("SCRIPT ERROR:", output)
            self.assertNotIn("\nERROR:", output)
            self.assertIn(f"GODOT_PALETTE_TESTS cases={len(requests)}", output)
            self.assertEqual(path.read_bytes(), before)
            results = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual([result["id"] for result in results], [item["id"] for item in requests])
            return results

    def test_shared_cases_against_godot_reader(self) -> None:
        suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        requests = [{"id": case["id"], "document": document_for(suite, case), "room_height": suite["room_height"]}
                    for case in suite["cases"]]
        for case, result in zip(suite["cases"], self.run_requests(requests)):
            with self.subTest(case=case["id"]):
                self.assertEqual(result["status"], case["expected"]["status"], result)
                if result["status"] == "accepted":
                    self.assertEqual(result["result"], document_for(suite, case))
                else:
                    self.assertTrue(result["error"])
                    self.assertNotIn("result", result)

    def test_non_finite_values_and_json_number_boundary(self) -> None:
        suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        requests = [{"id": field, "document": document_for(suite, {}), "room_height": 540, "non_finite": field}
                    for field in ("top", "bottom", "step", "polygon")]
        requests.append({"id": "invalid-height", "document": document_for(suite, {}), "room_height": 0})
        requests.append({"id": "oversized-height", "document": document_for(suite, {}), "room_height": 2161})
        floating = document_for(suite, {"set": {"gradient.top": [8.0, 10.0, 20.0], "gradient.step": 8.0}})
        requests.append({"id": "whole-floats", "document": floating, "room_height": 540})
        requests.append({"id": "valid-after-failure", "document": document_for(suite, {}), "room_height": 540})
        results = self.run_requests(requests)
        self.assertTrue(all(result["status"] == "rejected" for result in results[:-2]), results)
        for result in results[-2:]:
            self.assertEqual(result["status"], "accepted", result)
            self.assertEqual(result["result"], suite["base_definition"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "room.json"
            path.write_text(json.dumps(room_for(suite, floating)), encoding="utf-8")
            with self.assertRaises(ValueError):
                RoomRepository(path).load()
        low_height = document_for(suite, {"set": {"gradient.step": 180}})
        too_wide = document_for(suite, {"set": {"gradient.step": 181}})
        results = self.run_requests([
            {"id": "at-height", "document": low_height, "room_height": 180},
            {"id": "over-height", "document": too_wide, "room_height": 180},
        ])
        self.assertEqual(results[0]["result"], low_height)
        self.assertEqual(results[1]["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
