"""Optional real Godot checks: set GODOT_BIN to the Godot 4 console executable."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
GODOT = os.environ.get("GODOT_BIN") or shutil.which("godot")


@unittest.skipUnless(GODOT, "Godot runtime unavailable; set GODOT_BIN")
class GodotRuntimeTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
