import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from scripts.evaluate_project import (
    build_checks,
    iter_python_files,
    run_check,
    validate_runtime_log,
)


class EvaluateProjectTests(unittest.TestCase):
    def test_python_file_scan_ignores_virtualenv(self):
        files = iter_python_files(PROJECT_DIR)
        relative = [path.relative_to(PROJECT_DIR).as_posix() for path in files]

        self.assertIn("game.py", relative)
        self.assertIn("scripts/evaluate_project.py", relative)
        self.assertFalse(any(".venv" in item for item in relative))

    def test_build_checks_include_standard_and_special_validation(self):
        labels = [label for label, _command, _env in build_checks(PROJECT_DIR, 12)]

        self.assertEqual(
            labels,
            [
                "py_compile",
                "unit tests",
                "engine manifest",
                "standard game smoke",
                "runtime evaluation log",
                "special project validate",
            ],
        )

    def test_run_check_passes_environment_to_subprocess(self):
        completed = Mock(returncode=0)
        with patch("scripts.evaluate_project.subprocess.run", return_value=completed) as run:
            self.assertTrue(run_check("demo", ["python", "--version"], {"X_TEST": "1"}))

        _command, kwargs = run.call_args
        self.assertEqual(kwargs["cwd"], PROJECT_DIR)
        self.assertEqual(kwargs["env"]["X_TEST"], "1")

    def test_validate_runtime_log_requires_ghost_payload(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            log = root / "runtime.jsonl"
            log.write_text(
                '{"ghosts":[{"name":"kadoka","x":1,"y":2,"vx":0,"vy":0,'
                '"facing":1,"action":"stop"},{"name":"maru","x":3,"y":4,'
                '"vx":0,"vy":0,"facing":-1,"action":"stop"}],"objects":[]}\n',
                encoding="utf-8",
            )

            self.assertTrue(validate_runtime_log(root, Path("runtime.jsonl")))


if __name__ == "__main__":
    unittest.main()
