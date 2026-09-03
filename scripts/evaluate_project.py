from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_LOG = Path("tmp/evaluation/runtime.jsonl")


def project_python(project_root: Path) -> Path:
    candidate = project_root / ".venv" / "Scripts" / "python.exe"
    if candidate.is_file():
        return candidate
    return Path(sys.executable)


def iter_python_files(project_root: Path) -> list[Path]:
    ignored_parts = {".git", ".venv", "__pycache__"}
    files = []
    for path in project_root.rglob("*.py"):
        if ignored_parts.intersection(path.relative_to(project_root).parts):
            continue
        files.append(path)
    return sorted(files)


def build_checks(project_root: Path, frame_count: int) -> list[tuple[str, list[str], dict[str, str]]]:
    python = str(project_python(project_root))
    dummy_env = {"SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
    py_files = [str(path.relative_to(project_root)) for path in iter_python_files(project_root)]
    return [
        ("py_compile", [python, "-m", "py_compile", *py_files], {}),
        ("unit tests", [python, "-m", "unittest", "discover", "-s", "tests", "-v"], {}),
        ("engine manifest", [python, "engine_app.py", "--validate"], {}),
        (
            "standard game smoke",
            [python, "game.py", "--test-frames", str(frame_count), "--seed", "12345"],
            dummy_env,
        ),
        (
            "runtime evaluation log",
            [
                python,
                "game.py",
                "--test-frames",
                "60",
                "--seed",
                "12345",
                "--evaluation-log",
                str(RUNTIME_LOG),
                "--evaluation-interval",
                "10",
            ],
            dummy_env,
        ),
        (
            "special project validate",
            [python, "projects/obakeno_sumika_special/game.py", "--validate"],
            {},
        ),
    ]


def run_check(label: str, command: list[str], extra_env: dict[str, str]) -> bool:
    env = os.environ.copy()
    env.update(extra_env)
    print(f"[RUN] {label}")
    result = subprocess.run(command, cwd=PROJECT_ROOT, env=env)
    if result.returncode == 0:
        print(f"[OK] {label}")
        return True
    print(f"[FAIL] {label}: exit={result.returncode}")
    return False


def validate_runtime_log(project_root: Path, log_path: Path) -> bool:
    path = project_root / log_path
    if not path.is_file():
        print(f"[FAIL] runtime evaluation log format: missing {log_path}")
        return False
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        print("[FAIL] runtime evaluation log format: empty log")
        return False
    try:
        payload = json.loads(lines[0])
    except ValueError:
        print("[FAIL] runtime evaluation log format: invalid json")
        return False
    ghosts = payload.get("ghosts")
    objects = payload.get("objects")
    if not isinstance(ghosts, list) or len(ghosts) < 2:
        print("[FAIL] runtime evaluation log format: missing ghosts")
        return False
    if not isinstance(objects, list):
        print("[FAIL] runtime evaluation log format: missing objects")
        return False
    required_ghost_keys = {"name", "x", "y", "vx", "vy", "facing", "action"}
    if not required_ghost_keys.issubset(ghosts[0]):
        print("[FAIL] runtime evaluation log format: incomplete ghost payload")
        return False
    print("[OK] runtime evaluation log format")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run project evaluation checks.")
    parser.add_argument("--frames", type=int, default=900)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    failures = []
    for label, command, extra_env in build_checks(PROJECT_ROOT, args.frames):
        if not run_check(label, command, extra_env):
            failures.append(label)
        elif label == "runtime evaluation log" and not validate_runtime_log(
            PROJECT_ROOT, RUNTIME_LOG
        ):
            failures.append("runtime evaluation log format")
    if failures:
        print("FAILED: " + ", ".join(failures))
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
