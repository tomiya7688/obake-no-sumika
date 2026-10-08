"""Python/Godot adapters for the language-neutral project-manifest cases."""

from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

from engine.manifest_loader import load_project_manifest
from tests.godot_support import find_test_godot


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "spec" / "engine" / "project_manifest_cases.json"
GODOT = find_test_godot()


def make_contract_fixture(root: Path, suite: dict, case: dict,
                          filename: str = "engine_project.json") -> Path:
    root.mkdir(parents=True)
    (root.parent / "outside.entry").write_text("", encoding="utf-8")
    for directory in suite["directories"]:
        (root / directory).mkdir(parents=True, exist_ok=True)
    for name, value in {**suite["files"], **case.get("files", {})}.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        path.write_text(text, encoding="utf-8")
    manifest_path = root / filename
    manifest_path.write_text(json.dumps(case["manifest"], ensure_ascii=False), encoding="utf-8")
    return manifest_path


class PortableProjectContractTests(unittest.TestCase):
    def test_shared_cases_against_python_loader(self) -> None:
        suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        self.assertEqual(suite["schema_version"], 1)
        cases = suite["cases"]
        self.assertTrue(cases)
        self.assertEqual(len({case["id"] for case in cases}), len(cases))
        self.assertEqual({case["expected"]["status"] for case in cases}, {"accepted", "rejected"})
        temp_base = ROOT / "tmp" / "contract-tests"
        temp_base.mkdir(parents=True, exist_ok=True)
        for case in cases:
            with self.subTest(case=case["id"]), tempfile.TemporaryDirectory(dir=temp_base) as temp_dir:
                root = Path(temp_dir) / "project"
                manifest_path = make_contract_fixture(root, suite, case)
                expected = case["expected"]
                if expected["status"] == "rejected":
                    with self.assertRaises(ValueError):
                        load_project_manifest(manifest_path)
                    continue
                manifest = load_project_manifest(manifest_path)
                root = root.resolve()

                def relative(path: Path) -> str:
                    return path.relative_to(root).as_posix()

                result = {
                    "schema_version": manifest.schema_version,
                    "name": manifest.name,
                    "project_type": manifest.project_type,
                    "entrypoint": relative(manifest.entrypoint),
                    "editors": [
                        {"id": editor.id, "label": editor.label, "script": relative(editor.script)}
                        for editor in manifest.editors
                    ],
                    "content": {name: relative(path) for name, path in manifest.content.items()},
                    "content_manifest": relative(manifest.content_manifest) if manifest.content_manifest else None,
                }
                self.assertEqual(result, expected["result"])


@unittest.skipUnless(GODOT, "Godot runtime unavailable; set GODOT_BIN")
class GodotManifestContractTests(unittest.TestCase):
    def setUp(self) -> None:
        temp_base = ROOT / "tmp" / "contract-tests"
        temp_base.mkdir(parents=True, exist_ok=True)
        directory = tempfile.TemporaryDirectory(prefix="godot manifest 日本語 ", dir=temp_base)
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    def run_manifests(self, requests: list[dict]) -> list[dict]:
        request_path = self.root / "requests.json"
        report_path = self.root / "results.json"
        request_path.write_text(json.dumps(requests, ensure_ascii=False), encoding="utf-8")

        def snapshot() -> dict:
            # pathlib.rglob on Python 3.10 follows Windows junctions. Prune
            # reparse points before traversing so linked cycles stay unread.
            def linked(path: Path) -> bool:
                attributes = getattr(path.lstat(), "st_file_attributes", 0)
                return path.is_symlink() or bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))

            files = {}
            for directory, subdirs, names in os.walk(self.root, followlinks=False):
                base = Path(directory)
                subdirs[:] = [name for name in subdirs if not linked(base / name)]
                for name in names:
                    path = base / name
                    if path != report_path and not linked(path):
                        files[path.relative_to(self.root).as_posix()] = path.read_bytes()
            return files

        before = snapshot()
        process = subprocess.run(
            [str(GODOT), "--headless", "--path", str(ROOT / "godot"),
             "--script", "res://tests/test_project_manifest.gd", "--", str(request_path), str(report_path)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
        )
        output = process.stdout + process.stderr
        self.assertEqual(process.returncode, 0, output)
        self.assertNotIn("SCRIPT ERROR:", output)
        self.assertNotIn("\nERROR:", output)
        self.assertEqual(snapshot(), before, "Manifest reads must not write project files")
        self.assertIn(f"GODOT_MANIFEST_TESTS cases={len(requests)}", output)
        results = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual([result["id"] for result in results], [item["id"] for item in requests])
        return results

    def test_shared_cases_against_godot_loader(self) -> None:
        self.assertEqual(self.suite["schema_version"], 1)
        requests = []
        for case in self.suite["cases"]:
            path = make_contract_fixture(self.root / case["id"] / "project", self.suite, case)
            requests.append({"id": case["id"], "manifest": str(path)})
        results = self.run_manifests(requests)
        for case, result in zip(self.suite["cases"], results):
            with self.subTest(case=case["id"]):
                expected = case["expected"]
                self.assertEqual(result["status"], expected["status"], result)
                if result["status"] == "accepted":
                    self.assertEqual(result["result"], expected["result"])
                else:
                    self.assertTrue(result["error"])
                    self.assertNotIn("result", result)

    def test_godot_path_boundaries_and_alternate_filename(self) -> None:
        requests = []
        paths = ["../outside.entry", "data/../../outside.entry", "C:/outside.entry",
                 "res://main.tscn", "user://outside.entry", "../project-sibling/play.entry"]
        for index, entrypoint in enumerate(paths):
            case = {"manifest": {"schema_version": 1, "name": "test", "entrypoint": entrypoint}}
            root = self.root / str(index) / "project"
            path = make_contract_fixture(root, self.suite, case)
            sibling = root.parent / "project-sibling"
            sibling.mkdir()
            (sibling / "play.entry").write_text("", encoding="utf-8")
            requests.append({"id": str(index), "manifest": str(path)})
        case = self.suite["cases"][0]
        accepted = make_contract_fixture(self.root / "valid" / "project", self.suite, case,
                                         filename="別名-project.json")
        # Even an existing absolute path inside root is outside Godot's source policy.
        absolute_case = {"manifest": {"schema_version": 1, "name": "test",
                                       "entrypoint": str(accepted.parent / "play.entry")}}
        absolute = accepted.parent / "absolute.json"
        absolute.write_text(json.dumps(absolute_case["manifest"]), encoding="utf-8")
        requests.extend([{"id": "absolute", "manifest": str(absolute)},
                         {"id": "valid-after-rejection", "manifest": str(accepted)}])
        results = self.run_manifests(requests)
        self.assertTrue(all(result["status"] == "rejected" for result in results[:-1]), results)
        self.assertEqual(results[-1]["result"], case["expected"]["result"])

    def test_godot_rejects_linked_paths_before_parent_normalization(self) -> None:
        case = self.suite["cases"][0]
        root = self.root / "project"
        valid = make_contract_fixture(root, self.suite, case)
        try:
            (root / "linked.entry").symlink_to(root.parent / "outside.entry")
            (root / "linked-dir").symlink_to(root.parent, target_is_directory=True)
            (root / "internal.entry").symlink_to(root / "play.entry")
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"Symlink creation unavailable: {exc}")
        requests = []
        for index, entrypoint in enumerate(["linked.entry", "linked-dir/outside.entry",
                                            "linked-dir/../play.entry", "internal.entry"]):
            manifest = {**case["manifest"], "entrypoint": entrypoint}
            path = root / f"link-{index}.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            requests.append({"id": str(index), "manifest": str(path)})
        # A link to the manifest itself must not bypass the reader's path check.
        linked_manifest = root / "linked-manifest.json"
        linked_manifest.symlink_to(valid)
        requests.append({"id": "manifest-link", "manifest": str(linked_manifest)})
        requests.append({"id": "valid", "manifest": str(valid)})
        results = self.run_manifests(requests)
        self.assertTrue(all(result["status"] == "rejected" for result in results[:-1]), results)
        self.assertEqual(results[-1]["result"], case["expected"]["result"])

    @unittest.skipUnless(os.name == "nt", "Windows junction policy test")
    def test_godot_rejects_windows_junction_before_parent_normalization(self) -> None:
        # Junctions need no symlink privilege. Both ends stay in this test's
        # owned TemporaryDirectory, whose cleanup does not follow junctions.
        case = self.suite["cases"][0]
        root = self.root / "project"
        valid = make_contract_fixture(root, self.suite, case)
        link = root / "linked-dir"
        def quote(value: Path) -> str:
            return "'" + str(value).replace("'", "''") + "'"
        command = f"New-Item -ItemType Junction -Path {quote(link)} -Value {quote(root.parent)} -ErrorAction Stop | Out-Null"
        created = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if created.returncode:
            self.skipTest("Windows junction creation unavailable")
        requests = []
        for index, entrypoint in enumerate(["linked-dir/outside.entry", "linked-dir/../play.entry"]):
            path = root / f"junction-{index}.json"
            path.write_text(json.dumps({**case["manifest"], "entrypoint": entrypoint}), encoding="utf-8")
            requests.append({"id": str(index), "manifest": str(path)})
        requests.append({"id": "valid", "manifest": str(valid)})
        results = self.run_manifests(requests)
        self.assertTrue(all(result["status"] == "rejected" for result in results[:-1]), results)
        self.assertEqual(results[-1]["result"], case["expected"]["result"])


if __name__ == "__main__":
    unittest.main()
