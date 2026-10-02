"""Python adapter for the language-neutral project-manifest cases."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from engine.manifest_loader import load_project_manifest


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "spec" / "engine" / "project_manifest_cases.json"


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
                root.mkdir()
                (root.parent / "outside.entry").write_text("", encoding="utf-8")
                for directory in suite["directories"]:
                    (root / directory).mkdir(parents=True, exist_ok=True)
                for name, value in {**suite["files"], **case.get("files", {})}.items():
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                    path.write_text(text, encoding="utf-8")
                manifest_path = root / "engine_project.json"
                manifest_path.write_text(json.dumps(case["manifest"], ensure_ascii=False), encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
