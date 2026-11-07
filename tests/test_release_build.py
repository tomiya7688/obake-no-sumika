import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "tools" / "release"))

import build_release  # noqa: E402


class ReleaseBuildTests(unittest.TestCase):
    def build(self, directory: str) -> list[Path]:
        return build_release.build_all(PROJECT_DIR, build_release.DEFAULT_MANIFEST, Path(directory))

    def test_build_is_byte_for_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            built_first = self.build(first)
            built_second = self.build(second)
            self.assertEqual(
                [path.name for path in built_first], [path.name for path in built_second]
            )
            for left, right in zip(built_first, built_second):
                self.assertEqual(left.read_bytes(), right.read_bytes())
            self.assertEqual(
                (Path(first) / "SHA256SUMS").read_text(encoding="utf-8"),
                (Path(second) / "SHA256SUMS").read_text(encoding="utf-8"),
            )

    def test_archives_have_fixed_metadata_and_expected_content(self):
        version = build_release.read_version(PROJECT_DIR)
        with tempfile.TemporaryDirectory() as directory:
            built = {path.name: path for path in self.build(directory)}
            self.assertEqual(
                sorted(built),
                [
                    f"obake-no-sumika-editors-v{version}.zip",
                    f"obake-no-sumika-game-v{version}.zip",
                ],
            )
            with zipfile.ZipFile(built[f"obake-no-sumika-game-v{version}.zip"]) as game:
                names = game.namelist()
                self.assertEqual(names, sorted(names))
                prefix = f"obake-no-sumika-game-v{version}/"
                self.assertTrue(all(name.startswith(prefix) for name in names))
                self.assertIn(prefix + "game.py", names)
                self.assertIn(prefix + "run_game.bat", names)
                self.assertNotIn(prefix + "conversation_editor.py", names)
                self.assertFalse(any("__pycache__" in name for name in names))
                self.assertTrue(
                    all(info.date_time == build_release.FIXED_DATE_TIME for info in game.infolist())
                )
            with zipfile.ZipFile(built[f"obake-no-sumika-editors-v{version}.zip"]) as editors:
                names = editors.namelist()
                prefix = f"obake-no-sumika-editors-v{version}/"
                for expected in ("engine_app.py", "conversation_editor.py", "run_editor.bat"):
                    self.assertIn(prefix + expected, names)
                self.assertNotIn(prefix + "game.py", names)

    def test_sha256sums_match_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            built = self.build(directory)
            lines = (Path(directory) / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
            self.assertEqual(lines, [f"{build_release.sha256_of(p)}  {p.name}" for p in built])

    def test_secrets_and_build_outputs_are_not_in_manifest(self):
        manifest = json.loads(build_release.DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        for spec in manifest["archives"].values():
            for entry in spec["include"]:
                self.assertNotRegex(entry, r"(?i)\.(pfx|p12|key|pem|jks|keystore)$")
                self.assertNotIn(entry, {"tmp", "dist", ".venv", ".git", ".github"})

    def test_manifest_paths_must_stay_inside_project(self):
        with tempfile.TemporaryDirectory() as directory:
            bad = Path(directory) / "manifest.json"
            bad.write_text(
                json.dumps({"archives": {"x": {"include": ["../outside"]}}}), encoding="utf-8"
            )
            with self.assertRaises(build_release.ReleaseBuildError):
                build_release.load_manifest(bad)

    def test_missing_manifest_entry_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            root.mkdir()
            (root / "VERSION").write_text("1.0.0\n", encoding="utf-8")
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(
                json.dumps({"archives": {"x": {"include": ["missing.py"]}}}), encoding="utf-8"
            )
            with self.assertRaises(build_release.ReleaseBuildError):
                build_release.build_all(root, manifest, Path(directory) / "out")


if __name__ == "__main__":
    unittest.main()
