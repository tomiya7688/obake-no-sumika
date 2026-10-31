"""Windows launchers must stay readable by cmd.exe (Issue #127)."""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tracked_batch_files() -> list[Path]:
    names = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.bat", "*.cmd"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    return [ROOT / name for name in names.split("\0") if name]


class BatchLauncherTests(unittest.TestCase):
    def test_batch_files_are_checked_out_with_crlf(self) -> None:
        attributes = subprocess.run(
            ["git", "check-attr", "eol", "--", "run_game.bat", "x.cmd"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        self.assertIn("run_game.bat: eol: crlf", attributes)
        self.assertIn("x.cmd: eol: crlf", attributes)

    def test_every_launcher_is_ascii_with_crlf_line_endings(self) -> None:
        files = tracked_batch_files()
        self.assertIn(ROOT / "run_manual_check.bat", files)
        for path in files:
            with self.subTest(path=path.name):
                data = path.read_bytes()
                # UTF-8 text is split mid-character by cmd.exe; keep messages ASCII.
                self.assertTrue(data.isascii(), "non-ASCII bytes")
                self.assertTrue(data.endswith(b"\r\n"), "last line must end with CRLF")
                lines = data.split(b"\r\n")
                self.assertFalse(any(b"\n" in line or b"\r" in line for line in lines), "not CRLF")


if __name__ == "__main__":
    unittest.main()
