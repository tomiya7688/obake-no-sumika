"""Optional real Godot checks: set GODOT_BIN to the Godot 4 console executable."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    # Direct file execution starts in tests/, not at the repository root.
    sys.path.insert(0, str(ROOT))

from tests.godot_support import find_test_godot
from engine.manifest_loader import load_project_manifest
from engine.process_launcher import ProcessLauncher


GODOT = find_test_godot()


@unittest.skipUnless(GODOT, "Godot runtime unavailable; set GODOT_BIN")
class GodotRuntimeTests(unittest.TestCase):
    def cleanup_launched(self, child) -> None:
        # Terminate only the child started by this test, never other Godot instances.
        if child.poll() is None:
            child.process.terminate()
        child.process.wait(timeout=10)

    def test_process_launcher_returns_while_real_godot_is_running(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            launcher = ProcessLauncher(load_project_manifest(ROOT / "engine_project.json"), log_dir=Path(directory))
            child = launcher.launch_godot(executable=GODOT, headless=True, test_frames=60_000, seed=12345)
            try:
                self.assertIsNone(child.poll())
                self.assertTrue(child.log_path.is_file())
            finally:
                self.cleanup_launched(child)

    def test_process_launcher_records_real_godot_success(self) -> None:
        with tempfile.TemporaryDirectory(prefix="Godot launch 日本語 ") as directory:
            root = Path(directory)
            manifest = self.source_fixture(root)
            (root / "conversations.json").write_text("[]\n", encoding="utf-8")
            before = {path.name: path.read_bytes() for path in root.glob("*.json")}
            child = ProcessLauncher(load_project_manifest(manifest)).launch_godot(
                executable=GODOT, headless=True, test_frames=180, seed=12345,
            )
            try:
                self.assertEqual(child.process.wait(timeout=60), 0, child.log_tail())
                self.assertEqual(child.poll(), 0)
                output = child.log_tail()
                self.assertIn("CONVERSATION_DECK runnable=0", output)
                self.assertIn("GODOT_SMOKE_OK frames=180 ghosts=2", output)
                self.assertNotIn("Python gameplay must not run", output)
                self.assertNotIn("SCRIPT ERROR:", output)
                self.assertEqual({path.name: path.read_bytes() for path in root.glob("*.json")}, before)
            finally:
                self.cleanup_launched(child)

    def test_process_launcher_records_real_godot_failure_in_utf8(self) -> None:
        with tempfile.TemporaryDirectory(prefix="Godot failure 日本語 ") as directory:
            root = Path(directory)
            manifest = self.source_fixture(root)
            path = root / "characters.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["characters"][0]["image"] = "見つからない画像.png"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            before = {path.name: path.read_bytes() for path in root.glob("*.json")}
            child = ProcessLauncher(load_project_manifest(manifest)).launch_godot(
                executable=GODOT, headless=True, test_frames=180, seed=12345,
            )
            try:
                self.assertNotEqual(child.process.wait(timeout=30), 0)
                self.assertIsNotNone(child.poll())
                output = child.log_tail()
                self.assertIn("Missing content: 見つからない画像.png", output)
                self.assertNotIn("GODOT_SMOKE_OK", output)
                self.assertNotIn("SCRIPT ERROR:", output)
                self.assertEqual({path.name: path.read_bytes() for path in root.glob("*.json")}, before)
            finally:
                self.cleanup_launched(child)

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
            [str(GODOT), "--headless", "--path", str(ROOT / "godot"), *arguments],
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

    def test_source_game_accepts_relative_content_root(self) -> None:
        # Godot's relative resource paths start at godot/, not the shell cwd.
        output = self.run_godot("--", "--content-root", "..", "--test-frames", "1", "--seed", "12345")
        self.assertIn("GODOT_SMOKE_OK frames=1 ghosts=2", output)

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

    def test_direct_godot_rejects_manifest_errors_before_content_loading(self) -> None:
        # Bypass Python validation so this proves the runtime uses its adapter.
        mutations = [
            ({"name": " "}, "Project name is required"),
            ({"entrypoint": "missing.py"}, "Project path does not exist"),
            ({"editors": [{"id": "x", "label": "x", "script": "assets"}]}, "must be a file"),
            ({"content_manifest": "broken-content.json", "content": {"room": "room.json"}},
             "Path escapes the project root"),
        ]
        for mutation, expected_error in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                path = self.source_fixture(root)
                manifest = json.loads(path.read_text(encoding="utf-8"))
                manifest.update(mutation)
                path.write_text(json.dumps(manifest), encoding="utf-8")
                (root / "broken-content.json").write_text(json.dumps({"schema_version": 1,
                     "content": {"room": "../outside.json"}}), encoding="utf-8")
                before = path.read_bytes()
                result = subprocess.run(
                    [str(GODOT), "--headless", "--path", str(ROOT / "godot"), "--",
                     "--content-root", str(root), "--test-frames", "1"],
                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                )
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn(expected_error, output)
                self.assertNotIn("CONVERSATION_DECK", output)
                self.assertNotIn("GODOT_SMOKE_OK", output)
                self.assertNotIn("SCRIPT ERROR:", output)
                self.assertEqual(path.read_bytes(), before)


    def run_source_project(self, root: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [str(GODOT), "--headless", "--path", str(ROOT / "godot"), "--",
             "--content-root", str(root), "--test-frames", "1", "--seed", "12345"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
        )

    def test_direct_godot_validates_all_characters_before_images(self) -> None:
        mutations = [
            (0, {"display_name": " "}, "Character id and display_name are required"),
            (0, {"start_position": [961, 200]}, "start x"),
            (1, {"bubble_y_offset": 201}, "bubble_y_offset"),
            (1, {"behavior_weights": {"stop": 1, " stop ": 2}}, "action names must be unique"),
            (1, {"id": "unknown"}, "Expected distinct kadoka and maru IDs"),
        ]
        for index, mutation, error in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.source_fixture(root)
                path = root / "characters.json"
                data = json.loads(path.read_text(encoding="utf-8"))
                # A missing first PNG must not hide an invalid second character.
                data["characters"][0]["image"] = "missing-image.png"
                data["characters"][index].update(mutation)
                path.write_text(json.dumps(data), encoding="utf-8")
                before = {path.name: path.read_bytes() for path in root.glob("*.json")}
                result = self.run_source_project(root)
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn(error, output)
                self.assertNotIn("Missing content", output)
                self.assertNotIn("SCRIPT ERROR:", output)
                self.assertNotIn("GODOT_SMOKE_OK", output)
                self.assertEqual({path.name: path.read_bytes() for path in root.glob("*.json")}, before)

    def test_direct_godot_validates_room_geometry_before_images(self) -> None:
        mutations = [
            ({"zones": {"water_rest": [950, 500, 20, 20]}}, "zones.water_rest must stay inside"),
            ({"zones": {"water_rest": [335, 348, 0, 168]}}, "zones.water_rest width"),
            ({"movement_bounds": [74.5, 80, 812, 446]}, "movement_bounds x"),
            ({"fps": 0}, "fps"),
            ({"conversation_distance": 961}, "conversation_distance"),
            # Basic geometry accepts these; the current runtime still restricts them.
            ({"conversation_distance": 400}, "Conversation distance must be between 80 and 300"),
            ({"size": {"width": 1280, "height": 720}}, "First-stage room size must be 960x540"),
        ]
        for mutation, error in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.source_fixture(root)
                path = root / "room.json"
                data = json.loads(path.read_text(encoding="utf-8"))
                data.update(mutation)
                path.write_text(json.dumps(data), encoding="utf-8")
                characters = root / "characters.json"
                data = json.loads(characters.read_text(encoding="utf-8"))
                data["characters"][0]["image"] = "missing-image.png"
                characters.write_text(json.dumps(data), encoding="utf-8")
                before = {path.name: path.read_bytes() for path in root.glob("*.json")}
                result = self.run_source_project(root)
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn(error, output)
                self.assertNotIn("Missing content", output)
                self.assertNotIn("SCRIPT ERROR:", output)
                self.assertNotIn("GODOT_SMOKE_OK", output)
                self.assertEqual({path.name: path.read_bytes() for path in root.glob("*.json")}, before)

    def test_direct_godot_validates_palette_before_images(self) -> None:
        mutations = [
            ("top", [-1, 10, 20], "background.gradient.top"),
            ("bottom", [15, 256, 30], "background.gradient.bottom"),
            ("step", 541, "background.gradient.step"),
            ("step", 8.5, "background.gradient.step"),
            ("polygon", [5, 7, 256], "background.polygons[0].color"),
        ]
        for field, value, error in mutations:
            with self.subTest(field=field, value=value), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.source_fixture(root)
                path = root / "room.json"
                data = json.loads(path.read_text(encoding="utf-8"))
                if field == "polygon":
                    data["background"]["polygons"][0]["color"] = value
                else:
                    data["background"]["gradient"][field] = value
                path.write_text(json.dumps(data), encoding="utf-8")
                characters = root / "characters.json"
                data = json.loads(characters.read_text(encoding="utf-8"))
                data["characters"][0]["image"] = "missing-image.png"
                characters.write_text(json.dumps(data), encoding="utf-8")
                before = {path.name: path.read_bytes() for path in root.glob("*.json")}
                result = self.run_source_project(root)
                output = result.stdout + result.stderr
                self.assertNotEqual(result.returncode, 0, output)
                self.assertIn(error, output)
                self.assertNotIn("Missing content", output)
                self.assertNotIn("SCRIPT ERROR:", output)
                self.assertNotIn("GODOT_SMOKE_OK", output)
                self.assertEqual({path.name: path.read_bytes() for path in root.glob("*.json")}, before)

    def test_direct_godot_accepts_edited_palette_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.source_fixture(root)
            path = root / "room.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["background"]["gradient"] = {"top": [0, 0, 0], "bottom": [25, 30, 40], "step": 540}
            data["background"]["polygons"][0]["color"] = [0, 0, 255]
            path.write_text(json.dumps(data), encoding="utf-8")
            before = {path.name: path.read_bytes() for path in root.glob("*.json")}
            result = self.run_source_project(root)
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("GODOT_SMOKE_OK frames=1 ghosts=2", output)
            self.assertNotIn("SCRIPT ERROR:", output)
            self.assertNotIn("\nERROR:", output)
            self.assertEqual({path.name: path.read_bytes() for path in root.glob("*.json")}, before)

    def test_direct_godot_reads_edited_room_geometry_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.source_fixture(root)
            path = root / "room.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data.update({"movement_bounds": [80, 100, 780, 390],
                         "zones": {"water_rest": [400, 250, 140, 140]},
                         "conversation_distance": 200, "fps": 144})
            path.write_text(json.dumps(data), encoding="utf-8")
            before = {path.name: path.read_bytes() for path in root.glob("*.json")}
            result = self.run_source_project(root)
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("GODOT_SMOKE_OK frames=1 ghosts=2", output)
            self.assertNotIn("SCRIPT ERROR:", output)
            self.assertNotIn("\nERROR:", output)
            self.assertEqual({path.name: path.read_bytes() for path in root.glob("*.json")}, before)

    def test_direct_godot_uses_normalized_character_data_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.source_fixture(root)
            path = root / "characters.json"
            data = json.loads(path.read_text(encoding="utf-8"))
            data["characters"][0].update({"id": " kadoka ", "display_name": " かどか ",
                                          "native_facing": 0, "start_position": [320.9, 340.9]})
            data["characters"][0].pop("bubble_y_offset")
            path.write_text(json.dumps(data), encoding="utf-8")
            before = path.read_bytes()
            result = self.run_source_project(root)
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertIn("GODOT_SMOKE_OK frames=1 ghosts=2", output)
            self.assertNotIn("SCRIPT ERROR:", output)
            self.assertNotIn("\nERROR:", output)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
