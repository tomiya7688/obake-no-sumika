"""spec/command/engine_cli_cases.json を engine_app.py の実出力で検証する。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "spec/command/engine_cli_cases.json"


def run_cli(project: Path, flag: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "engine_app.py"), "--project", str(project), flag],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def snapshot(root: Path) -> dict[str, str]:
    # プロジェクト配下の全ファイルの内容ハッシュ（書き換え・新規作成の検出用）
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class PortableCliContractTests(unittest.TestCase):
    def test_shared_cases_against_python_cli(self) -> None:
        suite = json.loads(CASES_PATH.read_text(encoding="utf-8"))
        self.assertEqual(suite["schema_version"], 1)
        self.assertEqual(len({case["id"] for case in suite["cases"]}), len(suite["cases"]))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, content in suite["files"].items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(content) if content != "" else "", encoding="utf-8")
            for name in suite["directories"]:
                (root / name).mkdir(exist_ok=True)
            manifest = root / "engine_project.json"
            for case in suite["cases"]:
                with self.subTest(case=case["id"]):
                    manifest.write_text(
                        json.dumps(case["manifest"], ensure_ascii=False), encoding="utf-8"
                    )
                    before = snapshot(root)
                    described = run_cli(manifest, "--describe")
                    validated = run_cli(manifest, "--validate")
                    expected = case["expected"]
                    if expected["status"] == "rejected":
                        self.assertNotEqual(described.returncode, 0)
                        self.assertNotEqual(validated.returncode, 0)
                        self.assertEqual(described.stdout, "")
                        self.assertEqual(validated.stdout, "")
                    else:
                        self.assertEqual(described.returncode, 0, described.stderr)
                        self.assertEqual(json.loads(described.stdout), expected["describe"])
                        self.assertEqual(validated.returncode, 0, validated.stderr)
                        self.assertEqual(validated.stdout.splitlines(), [expected["validate"]])
                        want = expected["validate"]
                        self.assertIn(validated.stdout, (want + chr(10), want + chr(13) + chr(10)))
                    self.assertEqual(snapshot(root), before)


if __name__ == "__main__":
    unittest.main()
