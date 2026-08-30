from __future__ import annotations

import subprocess
import sys

from .project_manifest import ProjectManifest


class ProcessLauncher:
    """Launch scripts belonging to one validated engine project."""

    def __init__(self, manifest: ProjectManifest) -> None:
        self.manifest = manifest

    def launch_game(self) -> subprocess.Popen:
        return self._launch(self.manifest.entrypoint)

    def launch_editor(self, editor_id: str) -> subprocess.Popen:
        return self._launch(self.manifest.editor(editor_id).script)

    def _launch(self, script) -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, str(script)],
            cwd=self.manifest.root,
        )
