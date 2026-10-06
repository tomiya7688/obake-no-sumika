from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
import tempfile

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
    """Launch scripts belonging to one validated engine project."""

    def __init__(self, manifest: ProjectManifest, *, log_dir: Path | None = None) -> None:
        self.manifest = manifest
        self.log_dir = log_dir if log_dir is not None else manifest.root / "tmp" / "launch_logs"

    def launch_game(self) -> LaunchedProcess:
        return self._launch(self.manifest.entrypoint)

    def launch_editor(self, editor_id: str) -> LaunchedProcess:
        return self._launch(self.manifest.editor(editor_id).script)

    def _launch(self, script: Path) -> LaunchedProcess:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        python = Path(sys.executable)
        # The engine may run under pythonw; use the same environment's console
        # interpreter with hidden-window flags so stderr is always available.
        if python.name.lower() == "pythonw.exe":
            console_python = python.with_name("python.exe")
            if console_python.is_file():
                python = console_python
        env = os.environ.copy()
        env.update(PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=self.log_dir, prefix=f"{script.stem}-", suffix=".log", delete=False
        ) as log:
            process = subprocess.Popen(
                [str(python), str(script)],
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
