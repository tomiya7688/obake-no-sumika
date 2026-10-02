import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from tools.context.script.character_info import read_settings


ROOT = Path(__file__).resolve().parents[1]


class CharacterContextTests(unittest.TestCase):
    def test_cli_selects_only_maru_and_requested_fields(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools/context/script/character_info.py"),
             "--id", "maru", "--field", "native_facing", "--field", "behavior_weights"],
            cwd=ROOT, capture_output=True, text=True, check=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(set(payload), {"id", "native_facing", "behavior_weights"})
        self.assertEqual(payload["id"], "maru")
        self.assertEqual(payload["native_facing"], -1)
        self.assertEqual(payload["behavior_weights"]["dash"], 4.0)

    def test_list_and_invalid_requests(self):
        manifest = ROOT / "engine_project.json"
        entries = read_settings(manifest)
        self.assertEqual(entries, [
            {"id": "kadoka", "display_name": "かどか"},
            {"id": "maru", "display_name": "まる"},
        ])
        with self.assertRaisesRegex(ValueError, "Unknown character"):
            read_settings(manifest, "missing")
        with self.assertRaisesRegex(ValueError, "Unknown fields"):
            read_settings(manifest, "maru", ("missing",))

    def test_project_content_paths_are_respected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").write_text("", encoding="utf-8")
            (root / "sprite.png").write_bytes(b"placeholder")
            shutil.copyfile(ROOT / "room.json", root / "scene.json")
            payload = json.loads((ROOT / "characters.json").read_text(encoding="utf-8"))
            ghost = payload["characters"][0]
            ghost.update(id="custom", image="sprite.png", personality=1.5)
            payload["characters"] = [ghost]
            (root / "settings.json").write_text(json.dumps(payload), encoding="utf-8")
            manifest = root / "engine_project.json"
            manifest.write_text(json.dumps({
                "schema_version": 1, "name": "custom", "entrypoint": "main.py",
                "editors": [], "content": {"characters": "settings.json", "room": "scene.json"},
            }), encoding="utf-8")
            self.assertEqual(read_settings(manifest, "custom", ("image", "personality")), {
                "id": "custom", "image": "sprite.png", "personality": 1.5,
            })

    def test_project_without_character_content_is_reported(self):
        with self.assertRaisesRegex(ValueError, "characters and room"):
            read_settings(ROOT / "projects/obakeno_sumika_special/engine_project.json")


if __name__ == "__main__":
    unittest.main()
