from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .process_launcher import ProcessLauncher
from .project_manifest import ProjectManifest


class MainWindow:
    """Render the project actions exposed by an engine manifest."""

    def __init__(
        self,
        root: tk.Tk,
        manifest: ProjectManifest,
        launcher: ProcessLauncher,
    ) -> None:
        self.root = root
        self.manifest = manifest
        self.launcher = launcher
        self.status = tk.StringVar(value="準備できました")
        self._build()

    def _build(self) -> None:
        self.root.title(f"{self.manifest.name} - エンジン")
        self.root.minsize(460, 300)
        frame = ttk.Frame(self.root, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=self.manifest.name, font=("Yu Gothic UI", 18, "bold")).pack(
            anchor="w", pady=(0, 4)
        )
        ttk.Label(frame, text=str(self.manifest.root), foreground="#666666").pack(
            anchor="w", pady=(0, 20)
        )
        ttk.Button(frame, text="ゲームを実行", command=self._launch_game).pack(
            fill="x", pady=4
        )
        for editor in self.manifest.editors:
            ttk.Button(
                frame,
                text=editor.label,
                command=lambda editor_id=editor.id: self._launch_editor(editor_id),
            ).pack(fill="x", pady=4)
        ttk.Separator(frame).pack(fill="x", pady=16)
        ttk.Label(frame, textvariable=self.status).pack(anchor="w")

    def _launch_game(self) -> None:
        self._run("ゲーム", self.launcher.launch_game)

    def _launch_editor(self, editor_id: str) -> None:
        editor = self.manifest.editor(editor_id)
        self._run(editor.label, lambda: self.launcher.launch_editor(editor_id))

    def _run(self, label: str, action) -> None:
        try:
            action()
        except OSError as exc:
            messagebox.showerror("起動できません", f"{label}を起動できませんでした。\n{exc}")
            self.status.set(f"{label}の起動に失敗しました")
            return
        self.status.set(f"{label}を起動しました")
