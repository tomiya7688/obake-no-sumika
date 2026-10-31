from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from tools.release.script.package import (
    PackageError,
    build,
    load_manifest,
    select_files,
    sha256,
    tracked_files,
)

ROOT = Path(__file__).resolve().parents[1]
GIT_ENV = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
GIT_ENV.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull})
MANIFEST = {
    "schema_version": 1,
    "name": "demo",
    "packages": {"game": {"include": ["game.py", "data/*", "VERSION"]}},
}


def git(repo: Path, *args: str) -> None:
    result = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=", *args],
        cwd=repo,
        env=GIT_ENV,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AssertionError(f"git {args} failed: {result.stderr}")


class TemporaryRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name).resolve() / "repo"
        self.out = Path(temp.name).resolve() / "out"
        self.repo.mkdir()
        isolated = mock.patch.dict(os.environ, GIT_ENV, clear=True)
        isolated.start()
        self.addCleanup(isolated.stop)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "test")
        (self.repo / "data").mkdir()
        for name, text in {
            "game.py": b"print('hi')\n",
            "data/a.json": b"{}\n",
            "run.bat": b"@echo off\n:start\ngoto :eof\n",
            "secret_notes.txt": b"not shipped\n",
            "VERSION": b"1.2.3\n",
        }.items():
            (self.repo / name).write_bytes(text)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")

    def names(self, path: Path) -> list[str]:
        with zipfile.ZipFile(path) as archive:
            return archive.namelist()

    def read(self, path: Path, name: str) -> bytes:
        with zipfile.ZipFile(path) as archive:
            return archive.read(name)

    def test_builds_listed_files_under_a_versioned_folder_with_checksums(self) -> None:
        paths = build(self.repo, "HEAD", self.out, MANIFEST)
        self.assertEqual([path.name for path in paths], ["demo-v1.2.3-game.zip", "SHA256SUMS"])
        self.assertEqual(
            self.names(paths[0]),
            [
                "demo-v1.2.3-game/VERSION",
                "demo-v1.2.3-game/data/a.json",
                "demo-v1.2.3-game/game.py",
            ],
        )
        self.assertEqual(
            paths[1].read_text(encoding="utf-8"), f"{sha256(paths[0])}  demo-v1.2.3-game.zip\n"
        )

    def test_output_is_reproducible(self) -> None:
        first = build(self.repo, "HEAD", self.out / "a", MANIFEST)[0]
        second = build(self.repo, "HEAD", self.out / "b", MANIFEST)[0]
        self.assertEqual(sha256(first), sha256(second))

    def test_uncommitted_working_tree_edits_are_not_packaged(self) -> None:
        (self.repo / "game.py").write_bytes(b"print('someone else')\n")
        package = build(self.repo, "HEAD", self.out, MANIFEST)[0]
        self.assertEqual(self.read(package, "demo-v1.2.3-game/game.py"), b"print('hi')\n")

    def test_batch_files_get_crlf_and_other_files_keep_their_bytes(self) -> None:
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["packages"]["game"]["include"].append("run.bat")
        package = build(self.repo, "HEAD", self.out, manifest)[0]
        self.assertEqual(
            self.read(package, "demo-v1.2.3-game/run.bat"), b"@echo off\r\n:start\r\ngoto :eof\r\n"
        )
        self.assertEqual(self.read(package, "demo-v1.2.3-game/data/a.json"), b"{}\n")

    def test_missing_pattern_and_bad_version_fail(self) -> None:
        broken = json.loads(json.dumps(MANIFEST))
        broken["packages"]["game"]["include"].append("missing/*")
        with self.assertRaisesRegex(PackageError, "missing/"):
            build(self.repo, "HEAD", self.out, broken)
        with self.assertRaisesRegex(PackageError, "invalid version"):
            build(self.repo, "HEAD", self.out, MANIFEST, version="../x")
        with self.assertRaisesRegex(PackageError, "no-such-ref"):
            tracked_files(self.repo, "no-such-ref")


class ProjectManifestTests(unittest.TestCase):
    def test_every_pattern_matches_tracked_files_and_packages_differ(self) -> None:
        manifest = load_manifest()
        tracked = (
            subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
            .stdout.decode("utf-8")
            .split("\0")
        )
        selected = {
            name: select_files(tracked, spec["include"])
            for name, spec in manifest["packages"].items()
        }
        self.assertEqual(set(selected), {"game", "editors"})
        self.assertIn("run_game.bat", selected["game"])
        self.assertNotIn("conversation_editor.py", selected["game"])
        self.assertIn("conversation_editor.py", selected["editors"])
        for files in selected.values():
            self.assertIn("tools/security/script/launch.py", files)
            self.assertFalse([name for name in files if name.startswith(("tests/", "docs/"))])

    def test_game_package_runs_on_its_own(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            game_zip = next(
                path for path in build(ROOT, "HEAD", out, load_manifest()) if "-game" in path.name
            )
            with zipfile.ZipFile(game_zip) as archive:
                archive.extractall(out)
            folder = out / game_zip.stem
            env = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
            result = subprocess.run(
                [sys.executable, "game.py", "--test-frames", "30", "--seed", "1"],
                cwd=folder,
                env=env,
                capture_output=True,
                text=True,
                timeout=120,
            )
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])


if __name__ == "__main__":
    unittest.main()
