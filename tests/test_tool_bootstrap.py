"""Keep direct-file tools usable without the caller's cwd or PYTHONPATH."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = (
    "tools/context/script/audit.py",
    "tools/context/script/character_info.py",
    "tools/context/script/snapshot.py",
    "tools/diff_summary/script/summarize.py",
    "tools/repo_sync/script/inventory.py",
    "tools/repo_sync/script/report.py",
)


class ToolBootstrapTests(unittest.TestCase):
    def run_isolated(self, cwd: str, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-I", "-X", "utf8", *arguments],
            cwd=cwd,
            capture_output=True,
            encoding="utf-8",
            timeout=20,
        )

    def test_direct_help_from_unrelated_cwd_without_pythonpath(self) -> None:
        with tempfile.TemporaryDirectory(prefix="tool bootstrap 日本語 ") as directory:
            for tool in TOOLS:
                with self.subTest(tool=tool):
                    result = self.run_isolated(directory, str(ROOT / tool), "--help")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("usage:", result.stdout)
                    self.assertEqual(result.stderr, "")
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_imported_root_and_inventory_default_stay_file_relative(self) -> None:
        probe = (
            "import json, runpy, sys; "
            "module = runpy.run_path(sys.argv[1], run_name='bootstrap_probe'); "
            "print(json.dumps({'root': str(module['PROJECT_ROOT']), "
            "'plan': str(module.get('DEFAULT_PLAN', ''))}))"
        )
        with tempfile.TemporaryDirectory(prefix="tool import 日本語 ") as directory:
            for tool in TOOLS:
                with self.subTest(tool=tool):
                    result = self.run_isolated(directory, "-c", probe, str(ROOT / tool))
                    self.assertEqual(result.returncode, 0, result.stderr)
                    payload = json.loads(result.stdout)
                    self.assertEqual(Path(payload["root"]), ROOT)
                    if tool.endswith("inventory.py"):
                        self.assertEqual(
                            Path(payload["plan"]), ROOT / "tools/repo_sync/main_work_inventory.json"
                        )
                    self.assertEqual(result.stderr, "")
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
