"""Compare room geometry without claiming full background or JSON-number parity."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from engine.room_repository import RoomRepository
from tests.godot_support import find_test_godot

GODOT = find_test_godot()
CASES_PATH = ROOT / "spec/map/room_geometry_cases.json"


def document_for(suite: dict, case: dict) -> object:
    if "document" in case:
        return copy.deepcopy(case["document"])
    result = {**copy.deepcopy(suite["base_definition"]), **copy.deepcopy(case.get("changes", {}))}
    for field in case.get("remove", []):
        result.pop(field)
    return result


def geometry_result(raw: dict) -> dict:
    return {field: raw[field] for field in ("size", "fps", "movement_bounds", "conversation_distance")} | {
        "water_rest": raw["zones"]["water_rest"],
    }


class PortableRoomContractTests(unittest.TestCase):
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
                    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
                    before = path.read_bytes()
                    if case["expected"]["status"] == "rejected":
                        with self.assertRaises(ValueError):
                            repository.load()
                    else:
                        room = repository.load()
                        result = {"size": {"width": room.width, "height": room.height}, "fps": room.fps,
                                  "movement_bounds": list(room.movement_bounds),
                                  "water_rest": list(room.water_rest_area),
                                  "conversation_distance": room.conversation_distance}
                        self.assertEqual(result, geometry_result(document))
                    self.assertEqual(path.read_bytes(), before)


@unittest.skipUnless(GODOT, "Godot runtime unavailable; set GODOT_BIN")
class GodotRoomContractTests(unittest.TestCase):
    def run_requests(self, requests: list[dict]) -> list[dict]:
        with tempfile.TemporaryDirectory(prefix="room contract 日本語 ") as directory:
            path, report = Path(directory) / "requests.json", Path(directory) / "report.json"
            path.write_text(json.dumps(requests, ensure_ascii=False), encoding="utf-8")
            before = path.read_bytes()
            process = subprocess.run(
                [str(GODOT), "--headless", "--path", str(ROOT / "godot"), "--script",
                 "res://tests/test_room_geometry.gd", "--", str(path), str(report)],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            output = process.stdout + process.stderr
            self.assertEqual(process.returncode, 0, output)
            self.assertNotIn("SCRIPT ERROR:", output)
            self.assertNotIn("\nERROR:", output)
            self.assertIn(f"GODOT_ROOM_TESTS cases={len(requests)}", output)
            self.assertEqual(path.read_bytes(), before)
            results = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual([result["id"] for result in results], [item["id"] for item in requests])
            return results

    def test_shared_cases_against_godot_reader(self) -> None:
        suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        requests = [{"id": case["id"], "document": document_for(suite, case)} for case in suite["cases"]]
        for case, result in zip(suite["cases"], self.run_requests(requests)):
            with self.subTest(case=case["id"]):
                self.assertEqual(result["status"], case["expected"]["status"], result)
                if result["status"] == "accepted":
                    # Compare the entire copied dictionary to cover untouched metadata too.
                    self.assertEqual(result["result"], document_for(suite, case))
                else:
                    self.assertTrue(result["error"])
                    self.assertNotIn("result", result)

    def test_json_numeric_boundary_non_finite_and_recovery(self) -> None:
        suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        requests = [{"id": field, "document": document_for(suite, {}), "non_finite": field}
                    for field in ("width", "movement", "water", "fps", "distance")]
        requests.append({"id": "boolean-schema", "document": document_for(suite, {"changes": {"schema_version": True}})})
        requests.append({"id": "whole-floats", "document": document_for(suite, {"changes": {
            "size": {"width": 960.0, "height": 540.0}, "fps": 60.0,
            "movement_bounds": [74.0, 80.0, 812.0, 446.0],
        }})})
        requests.append({"id": "valid-after-failure", "document": document_for(suite, {})})
        results = self.run_requests(requests)
        self.assertTrue(all(result["status"] == "rejected" for result in results[:-2]), results)
        for result in results[-2:]:
            self.assertEqual(result["status"], "accepted", result)
            self.assertEqual(result["result"], suite["base_definition"])
        # Python rejects 60.0 for an integer field, while Godot JSON loses that
        # lexical distinction. Test and document the boundary instead of hiding it.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "room.json"
            path.write_text(json.dumps(requests[-2]["document"]), encoding="utf-8")
            with self.assertRaises(ValueError):
                RoomRepository(path).load()


if __name__ == "__main__":
    unittest.main()
