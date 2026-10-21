from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path

from .godot_runner import GodotInvocation, prepare_godot_invocation, prepare_godot_invocation_async
from .project_manifest import ProjectManifest


@dataclass(frozen=True)
class LaunchedProcess:
    """A non-blocking child and its persistent, UTF-8 diagnostic log."""

    process: subprocess.Popen
    log_path: Path

    def poll(self) -> int | None:
        return self.process.poll()

    def log_tail(self, max_bytes: int = 8192) -> str:
        # Read only the tail, not an unbounded stream or a blocking PIPE.
        with self.log_path.open("rb") as stream:
            stream.seek(0, os.SEEK_END)
            size = stream.tell()
            stream.seek(max(0, size - max_bytes))
            return stream.read(max_bytes).decode("utf-8", errors="replace")


class ProcessLauncher:
    """Launch project scripts or the source Godot runtime with persistent diagnostics."""

    def __init__(self, manifest: ProjectManifest, *, log_dir: Path | None = None) -> None:
        self.manifest = manifest
        self.log_dir = log_dir if log_dir is not None else manifest.root / "tmp" / "launch_logs"

    def launch_game(self) -> LaunchedProcess:
        return self._launch(self.manifest.entrypoint)

    def launch_editor(self, editor_id: str) -> LaunchedProcess:
        return self._launch(self.manifest.editor(editor_id).script)

    def launch_godot(
        self, *, executable: Path | None = None, headless: bool = False,
        test_frames: int | None = None, seed: int | None = None,
    ) -> LaunchedProcess:
        """Prepare synchronously; then return without waiting for Godot to exit."""
        if self.manifest.project_type != "standard":
            raise ValueError("Godot playtests currently support standard projects only")
        invocation = prepare_godot_invocation(
            self.manifest.root / "engine_project.json", executable=executable,
            headless=headless, test_frames=test_frames, seed=seed,
            expected_manifest=self.manifest,
        )
        return self.launch_prepared_godot(invocation)

    def prepare_godot_async(
        self, *, executable: Path | None = None, headless: bool = False,
        test_frames: int | None = None, seed: int | None = None,
    ) -> Future[GodotInvocation]:
        """Return preparation status; the caller must explicitly start the game."""
        return prepare_godot_invocation_async(
            self.manifest.root / "engine_project.json", executable=executable,
            headless=headless, test_frames=test_frames, seed=seed,
            expected_manifest=self.manifest,
        )

    def launch_prepared_godot(self, invocation: GodotInvocation) -> LaunchedProcess:
        """Start a trusted invocation from the shared preparer for this selection."""
        if not isinstance(invocation, GodotInvocation):
            raise TypeError("Expected a prepared GodotInvocation")
        if self.manifest.project_type != "standard" or invocation.manifest != self.manifest:
            raise ValueError("Prepared Godot selection changed; prepare the project again")
        return self._launch_command(list(invocation.command), "godot")

    def _launch(self, script: Path) -> LaunchedProcess:
        python = Path(sys.executable)
        # The engine may run under pythonw; use the same environment's console
        # interpreter with hidden-window flags so stderr is always available.
        if python.name.lower() == "pythonw.exe":
            console_python = python.with_name("python.exe")
            if console_python.is_file():
                python = console_python
        return self._launch_command([str(python), str(script)], script.stem)

    def _launch_command(self, command: list[str], log_prefix: str) -> LaunchedProcess:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=self.log_dir, prefix=f"{log_prefix}-", suffix=".log", delete=False
        ) as log:
            process = subprocess.Popen(
                command,
                cwd=self.manifest.root,
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            log_path = Path(log.name)
        # Popen duplicated/inherited the file handle. The parent need not keep
        # it open, and output remains available after the engine window closes.
        return LaunchedProcess(process, log_path)
