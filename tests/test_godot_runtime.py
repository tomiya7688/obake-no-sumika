"""Optional real Godot checks: set GODOT_BIN to the Godot 4 console executable."""

from __future__ import annotations

import os
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
GODOT = os.environ.get("GODOT_BIN") or shutil.which("godot")


@unittest.skipUnless(GODOT, "Godot runtime unavailable; set GODOT_BIN")
class GodotRuntimeTests(unittest.TestCase):
    def engine_playtest(self, manifest: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "engine_app.py"), "--project", str(manifest),
             "--playtest-godot", "--godot-bin", str(GODOT), "--headless",
             "--test-frames", "180", "--seed", "12345"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
        )

    def source_fixture(self, root: Path) -> Path:
        # Only shared data/images are copied, never .git/.venv or Python gameplay.
        for name in ("engine_project.json", "game_content.json", "characters.json",
                     "room.json", "placed_objects.json", "conversations.json", "events.json"):
            shutil.copy2(ROOT / name, root / name)
        for name in ("assets", "objects"):
            shutil.copytree(ROOT / name, root / name)
        manifest = json.loads((root / "engine_project.json").read_text(encoding="utf-8"))
        for editor in manifest["editors"]:
            (root / editor["script"]).write_text("", encoding="utf-8")
        (root / manifest["entrypoint"]).write_text(
            "raise RuntimeError('Python gameplay must not run')\n", encoding="utf-8",
        )
        return root / "engine_project.json"

    def run_godot(self, *arguments: str) -> str:
        result = subprocess.run(
            [GODOT, "--headless", "--path", str(ROOT / "godot"), *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn("SCRIPT ERROR:", output)
        self.assertNotIn("\nERROR:", output)
        return output

    def test_simulation_and_shared_content(self) -> None:
        output = self.run_godot("--script", "res://tests/test_runtime.gd")
        self.assertIn("failures=0", output)
        self.assertIn("GODOT_TESTS", output)

    def test_source_game_smoke(self) -> None:
        output = self.run_godot("--", "--test-frames", "180", "--seed", "12345")
        self.assertIn("GODOT_SMOKE_OK frames=180 ghosts=2", output)

    def test_conversation_choreography_and_deck(self) -> None:
        output = self.run_godot("--script", "res://tests/test_conversations.gd")
        self.assertIn("failures=0", output)
        self.assertIn("GODOT_CONVERSATION_TESTS", output)

    def test_tagged_object_sequence_and_render_state(self) -> None:
        output = self.run_godot("--script", "res://tests/test_objects.gd")
        self.assertIn("failures=0", output)
        self.assertIn("GODOT_OBJECT_TESTS", output)

    def test_scripted_events_and_cleanup(self) -> None:
        output = self.run_godot("--script", "res://tests/test_events.gd")
        self.assertIn("failures=0", output)
        self.assertIn("GODOT_EVENT_TESTS", output)

    def test_name_hover_and_stretched_pointer_input(self) -> None:
        output = self.run_godot("--script", "res://tests/test_hover.gd")
        self.assertIn("failures=0", output)
        self.assertIn("GODOT_HOVER_TESTS", output)

    def test_floor_shadows_and_loop_continuity(self) -> None:
        output = self.run_godot("--script", "res://tests/test_shadows.gd")
        self.assertIn("failures=0", output)
        self.assertIn("GODOT_SHADOW_TESTS", output)

    def test_background_vignette_and_layering(self) -> None:
        output = self.run_godot("--script", "res://tests/test_vignette.gd")
        self.assertIn("failures=0", output)
        self.assertIn("GODOT_VIGNETTE_TESTS", output)

    def test_ambient_motes_and_rng_isolation(self) -> None:
        output = self.run_godot("--script", "res://tests/test_motes.gd")
        self.assertIn("failures=0", output)
        self.assertIn("GODOT_MOTE_TESTS", output)

    def test_engine_cli_playtest_runs_real_godot(self) -> None:
        result = self.engine_playtest(ROOT / "engine_project.json")
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertIn("GODOT_SMOKE_OK frames=180 ghosts=2", output)
        self.assertNotIn("SCRIPT ERROR:", output)
        self.assertNotIn("\nERROR:", output)

    def test_engine_cli_reads_edited_selected_project_not_python(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sumika project 日本語 ") as directory:
            root = Path(directory)
            manifest = self.source_fixture(root)
            (root / "conversations.json").write_text("[]\n", encoding="utf-8")
            before = {path.name: path.read_bytes() for path in root.glob("*.json")}
            result = self.engine_playtest(manifest)
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("CONVERSATION_DECK runnable=0", output)
            self.assertIn("GODOT_SMOKE_OK frames=180 ghosts=2", output)
            self.assertNotIn("Python gameplay must not run", output)
            self.assertEqual({path.name: path.read_bytes() for path in root.glob("*.json")}, before)

    def test_engine_cli_propagates_real_content_validation_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sumika invalid ") as directory:
            root = Path(directory)
            manifest = self.source_fixture(root)
            room = json.loads((root / "room.json").read_text(encoding="utf-8"))
            room["motes"]["count"] = -1
            (root / "room.json").write_text(json.dumps(room), encoding="utf-8")
            result = self.engine_playtest(manifest)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Invalid motes.count", result.stdout + result.stderr)
            self.assertNotIn("GODOT_SMOKE_OK", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
