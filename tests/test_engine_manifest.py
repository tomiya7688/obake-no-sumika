import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from engine.manifest_loader import load_project_manifest
from engine.process_launcher import ProcessLauncher


class EngineManifestTests(unittest.TestCase):
    def test_current_project_manifest_is_valid(self):
        manifest = load_project_manifest(PROJECT_DIR / "engine_project.json")
        self.assertEqual(manifest.name, "おばけの住処")
        self.assertEqual(manifest.entrypoint, PROJECT_DIR / "game.py")
        self.assertEqual(
            [editor.id for editor in manifest.editors],
            ["character", "conversation_event", "object_room"],
        )
        self.assertEqual(manifest.content["characters"], PROJECT_DIR / "characters.json")
        self.assertEqual(manifest.content["room"], PROJECT_DIR / "placed_objects.json")

    def test_manifest_rejects_paths_outside_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "project.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "test",
                        "entrypoint": "../outside.py",
                        "editors": [],
                        "content": {},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "escapes"):
                load_project_manifest(manifest_path)

    def test_manifest_rejects_duplicate_editor_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "game.py").write_text("", encoding="utf-8")
            (root / "editor.py").write_text("", encoding="utf-8")
            manifest_path = root / "project.json"
            editor = {"id": "same", "label": "editor", "script": "editor.py"}
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "name": "test",
                        "entrypoint": "game.py",
                        "editors": [editor, editor],
                        "content": {},
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                load_project_manifest(manifest_path)

    def test_process_launcher_uses_project_python_and_root(self):
        manifest = load_project_manifest(PROJECT_DIR / "engine_project.json")
        launcher = ProcessLauncher(manifest)
        with patch("engine.process_launcher.subprocess.Popen") as popen:
            launcher.launch_editor("character")
        popen.assert_called_once_with(
            [sys.executable, str(PROJECT_DIR / "character_editor.py")],
            cwd=PROJECT_DIR,
        )

    def test_unknown_editor_id_is_rejected(self):
        manifest = load_project_manifest(PROJECT_DIR / "engine_project.json")
        with self.assertRaises(KeyError):
            manifest.editor("missing")


if __name__ == "__main__":
    unittest.main()
