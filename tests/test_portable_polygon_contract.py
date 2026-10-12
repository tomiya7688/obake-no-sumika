"""Shared polygon shapes/integer coordinates, not renderer or full room parity."""

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
CASES_PATH = ROOT / "spec/map/polygon_geometry_cases.json"


def document_for(suite: dict, case: dict) -> object:
    if "document" in case:
        return copy.deepcopy(case["document"])
    document = copy.deepcopy(suite["base_definition"])
    for path, value in case.get("set", {}).items():
        parent, key = parent_for(document, path)
        parent[key] = copy.deepcopy(value)
    for path in case.get("remove", []):
        parent, key = parent_for(document, path)
        del parent[key]
    return document


def parent_for(document: object, path: str) -> tuple[object, str | int]:
    parts = path.split(".")
    current = document
    for part in parts[:-1]:
        current = current[int(part) if isinstance(current, list) else part]
    return current, int(parts[-1]) if isinstance(current, list) else parts[-1]


def room_for(suite: dict, polygons: object) -> dict:
    raw = json.loads((ROOT / suite["base_room_fixture"]).read_text(encoding="utf-8"))["base_definition"]
    raw["background"]["polygons"] = copy.deepcopy(polygons)
    return raw


class PortablePolygonContractTests(unittest.TestCase):
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
                    path.write_text(json.dumps(room_for(suite, document), ensure_ascii=False), encoding="utf-8")
                    before = path.read_bytes()
                    if case["expected"]["status"] == "rejected":
                        with self.assertRaises(ValueError):
                            repository.load()
                    else:
                        layers = repository.load().polygon_layers
                        self.assertEqual([{"color": list(color), "points": [list(point) for point in points]}
                                          for color, points in layers],
                                         [{"color": layer["color"], "points": layer["points"]} for layer in document])
                    self.assertEqual(path.read_bytes(), before)


@unittest.skipUnless(GODOT, "Godot runtime unavailable; set GODOT_BIN")
class GodotPolygonContractTests(unittest.TestCase):
    def run_requests(self, requests: list[dict]) -> list[dict]:
        with tempfile.TemporaryDirectory(prefix="polygon contract 日本語 ") as directory:
            path, report = Path(directory) / "requests.json", Path(directory) / "report.json"
            path.write_text(json.dumps(requests, ensure_ascii=False), encoding="utf-8")
            before = path.read_bytes()
            process = subprocess.run(
                [str(GODOT), "--headless", "--path", str(ROOT / "godot"), "--script",
                 "res://tests/test_polygon_geometry.gd", "--", str(path), str(report)],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            output = process.stdout + process.stderr
            self.assertEqual(process.returncode, 0, output)
            self.assertNotIn("SCRIPT ERROR:", output)
            self.assertNotIn("\nERROR:", output)
            self.assertIn(f"GODOT_POLYGON_TESTS cases={len(requests)}", output)
            self.assertEqual(path.read_bytes(), before)
            results = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual([item["id"] for item in results], [item["id"] for item in requests])
            return results

    def test_shared_cases_against_godot_reader(self) -> None:
        suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        requests = [{"id": case["id"], "document": document_for(suite, case)} for case in suite["cases"]]
        for case, result in zip(suite["cases"], self.run_requests(requests)):
            with self.subTest(case=case["id"]):
                self.assertEqual(result["status"], case["expected"]["status"], result)
                if result["status"] == "accepted":
                    self.assertEqual(result["result"], document_for(suite, case))
                else:
                    self.assertTrue(result["error"])
                    self.assertNotIn("result", result)

    def test_precision_non_finite_and_whole_float_boundaries(self) -> None:
        suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        requests = [{"id": value, "document": document_for(suite, {}), "non_finite": value}
                    for value in ("nan", "inf", "negative-inf")]
        oversized = []
        for value in (2**53, -(2**53), 2**63 - 1, -(2**63), 10**100):
            document = document_for(suite, {"set": {"0.points.0.0": value}})
            oversized.append(document)
            requests.append({"id": str(value), "document": document})
        for value in (2**53, -(2**53)):
            requests.append({"id": f"native-{value}", "document": document_for(suite, {}), "native_int": str(value)})
        rejected_count = len(requests)
        floating = document_for(suite, {"set": {"0.points.0.0": 0.0, "0.points.1.1": -0.0}})
        requests.extend([{"id": "whole-floats", "document": floating},
                         {"id": "recovery", "document": document_for(suite, {})}])
        for value in (2**53 - 1, -(2**53 - 1)):
            requests.append({"id": f"native-{value}", "document": document_for(suite, {}), "native_int": str(value)})
        results = self.run_requests(requests)
        self.assertTrue(all(item["status"] == "rejected" for item in results[:rejected_count]), results)
        for result in results[rejected_count:rejected_count + 2]:
            self.assertEqual(result["status"], "accepted", result)
            self.assertEqual(result["result"], suite["base_definition"])
        for value, result in zip((2**53 - 1, -(2**53 - 1)), results[-2:]):
            self.assertEqual(result["status"], "accepted", result)
            self.assertEqual(result["result"][0]["points"][0][0], value)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "room.json"
            for document in oversized:
                path.write_text(json.dumps(room_for(suite, document)), encoding="utf-8")
                RoomRepository(path).load()  # Python has arbitrary-precision ints.
            path.write_text(json.dumps(room_for(suite, floating)), encoding="utf-8")
            with self.assertRaises(ValueError):
                RoomRepository(path).load()


if __name__ == "__main__":
    unittest.main()
