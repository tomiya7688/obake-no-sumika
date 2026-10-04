"""Synchronous source-playtest bridge; Python gameplay and Tk are not imported."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess

from .manifest_loader import load_project_manifest


RUNTIME_ROOT = Path(__file__).resolve().parents[1] / "godot"


def resolve_godot(executable: Path | None = None) -> Path:
    """An explicit path overrides GODOT_BIN; an invalid override never falls back."""
    configured = str(executable) if executable is not None else os.environ.get("GODOT_BIN")
    if configured is not None:
        if not configured.strip():
            raise ValueError("GODOT_BIN must be a non-empty executable path")
        candidate = Path(configured).resolve()
        if not candidate.is_file():
            raise FileNotFoundError(f"Godot executable does not exist: {candidate}")
        return candidate
    for name in ("godot", "godot4"):
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    raise FileNotFoundError("Godot 4 not found; set GODOT_BIN or pass --godot-bin")


def verify_godot(executable: Path) -> None:
    """Reject unsupported versions or failed probes before starting the game."""
    try:
        probe = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Godot version check timed out after 10 seconds") from exc
    version = probe.stdout.strip()
    if probe.returncode != 0 or not re.match(r"^4\.\d+\.", version):
        detail = (probe.stdout + probe.stderr).strip()[:4000]
        raise RuntimeError(f"Godot 4 version check failed (exit={probe.returncode}): {detail}")


def run_godot(
    project_path: Path,
    *,
    executable: Path | None = None,
    headless: bool = False,
    test_frames: int | None = None,
    seed: int | None = None,
) -> int:
    """Run until the game exits, inheriting output and returning its exit code."""
    project_path = project_path.resolve()
    if project_path.name != "engine_project.json":
        raise ValueError("Godot playtests require an engine_project.json manifest")
    manifest = load_project_manifest(project_path)
    if manifest.project_type != "standard":
        raise ValueError("Godot playtests currently support standard projects only")
    if test_frames is not None and (type(test_frames) is not int or test_frames <= 0):
        raise ValueError("--test-frames must be a positive integer")
    if headless and test_frames is None:
        raise ValueError("--headless requires --test-frames to finish without a window")
    if seed is not None and (type(seed) is not int or not -(2**63) <= seed < 2**63):
        raise ValueError("--seed must be a signed 64-bit integer")
    if not (RUNTIME_ROOT / "project.godot").is_file():
        raise FileNotFoundError(f"Source Godot runtime is missing: {RUNTIME_ROOT}")
    godot = resolve_godot(executable)
    verify_godot(godot)
    command = [str(godot), "--path", str(RUNTIME_ROOT)]
    if headless:
        command.append("--headless")
    if test_frames is not None:
        command.extend(["--fixed-fps", "60"])
    # Engine flags stay before '--'; selected project data belongs to the game.
    command.extend(["--", "--content-root", str(manifest.root)])
    if test_frames is not None:
        command.extend(["--test-frames", str(test_frames)])
    if seed is not None:
        command.extend(["--seed", str(seed)])
    return subprocess.run(command, cwd=manifest.root, check=False).returncode
