import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from engine.manifest_loader import load_project_manifest


SPECIAL_ROOT = PROJECT_DIR / "projects" / "obakeno_sumika_special"


class SpecialProjectIsolationTests(unittest.TestCase):
    def test_standard_project_type_is_explicit(self):
        manifest = load_project_manifest(PROJECT_DIR / "engine_project.json")

        self.assertEqual(manifest.project_type, "standard")

    def test_special_project_has_own_manifest_and_data_root(self):
        manifest = load_project_manifest(SPECIAL_ROOT / "engine_project.json")

        self.assertEqual(manifest.project_type, "obakeno_sumika_special")
        self.assertEqual(manifest.root, SPECIAL_ROOT)
        self.assertEqual(manifest.content_manifest, SPECIAL_ROOT / "game_content.json")
        for content_path in manifest.content.values():
            self.assertEqual(content_path, SPECIAL_ROOT / content_path.relative_to(SPECIAL_ROOT))
            self.assertNotEqual(content_path.parent, PROJECT_DIR)

    def test_special_project_validates_without_standard_game_data(self):
        result = subprocess.run(
            [sys.executable, str(SPECIAL_ROOT / "game.py"), "--validate"],
            cwd=SPECIAL_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("OK: special knowledge entries=", result.stdout)


if __name__ == "__main__":
    unittest.main()
