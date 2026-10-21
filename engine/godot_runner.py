"""Shared source-playtest preparation; Python gameplay and Tk are not imported."""

from __future__ import annotations

import copy
import os
import re
import shutil
import subprocess
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path
from threading import Thread

from .manifest_loader import load_project_manifest
from .project_manifest import ProjectManifest

RUNTIME_ROOT = Path(__file__).resolve().parents[1] / "godot"


@dataclass(frozen=True)
class GodotInvocation:
    """Validated immutable arguments and the selected project's current definition."""

    command: tuple[str, ...]
    manifest: ProjectManifest


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
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Godot version check timed out after 10 seconds") from exc
    version = probe.stdout.strip()
    if probe.returncode != 0 or not re.match(r"^4\.\d+\.", version):
        detail = (probe.stdout + probe.stderr).strip()[:4000]
        raise RuntimeError(f"Godot 4 version check failed (exit={probe.returncode}): {detail}")


def prepare_godot_invocation(
    project_path: Path,
    *,
    executable: Path | None = None,
    headless: bool = False,
    test_frames: int | None = None,
    seed: int | None = None,
    expected_manifest: ProjectManifest | None = None,
) -> GodotInvocation:
    """Validate synchronously (probe <=10s), without starting the gameplay process."""
    project_path = project_path.resolve()
    if project_path.name != "engine_project.json":
        raise ValueError("Godot playtests require an engine_project.json manifest")
    manifest = load_project_manifest(project_path)
    if manifest.project_type != "standard":
        raise ValueError("Godot playtests currently support standard projects only")
    if expected_manifest is not None and expected_manifest != manifest:
        raise ValueError("Selected project differs from engine_project.json; reload the project")
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
    return GodotInvocation(tuple(command), manifest)


def prepare_godot_invocation_async(
    project_path: Path,
    *,
    executable: Path | None = None,
    headless: bool = False,
    test_frames: int | None = None,
    seed: int | None = None,
    expected_manifest: ProjectManifest | None = None,
) -> Future[GodotInvocation]:
    """Prepare on a daemon worker; never start gameplay or access GUI widgets."""
    # Capture relative paths and mutable selection data before another project
    # or working directory can be selected. Files are read by the worker.
    project_path = project_path.absolute()
    executable = executable.absolute() if executable is not None else None
    selection = copy.deepcopy(expected_manifest)
    future: Future[GodotInvocation] = Future()

    def prepare() -> None:
        if not future.set_running_or_notify_cancel():
            return
        try:
            invocation = prepare_godot_invocation(
                project_path, executable=executable, headless=headless,
                test_frames=test_frames, seed=seed, expected_manifest=selection,
            )
        except BaseException as exc:
            # Match Future executors: failures belong to the requesting caller,
            # including unexpected worker exits, instead of leaving it pending.
            future.set_exception(exc)
        else:
            future.set_result(invocation)

    try:
        Thread(target=prepare, name="godot-preparation", daemon=True).start()
    except Exception as exc:
        future.set_exception(exc)
    return future


def run_godot(
    project_path: Path,
    *,
    executable: Path | None = None,
    headless: bool = False,
    test_frames: int | None = None,
    seed: int | None = None,
) -> int:
    """Run until the game exits, inheriting output and returning its exit code."""
    invocation = prepare_godot_invocation(
        project_path, executable=executable, headless=headless, test_frames=test_frames, seed=seed,
    )
    return subprocess.run(list(invocation.command), cwd=invocation.manifest.root, check=False).returncode
