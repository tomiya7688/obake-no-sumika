from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .manifest_loader import load_project_manifest
from .process_launcher import ProcessLauncher
from .project_creator import ProjectCreator
from .project_manifest import ProjectManifest


class MainWindow:
    """Render the project actions exposed by an engine manifest."""

    def __init__(
        self,
        root: tk.Tk,
        manifest: ProjectManifest,
        launcher: ProcessLauncher,
        project_creator: ProjectCreator | None = None,
    ) -> None:
        self.root = root
        self.manifest = manifest
        self.launcher = launcher
        self.project_creator = project_creator or ProjectCreator()
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
        ttk.Label(frame, text=f"type: {self.manifest.project_type}", foreground="#666666").pack(
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
        ttk.Button(frame, text="プロジェクトを開く", command=self._open_project).pack(
            fill="x", pady=4
        )
        ttk.Button(frame, text="新規プロジェクトを作成", command=self._create_project).pack(
            fill="x", pady=4
        )
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

    def open_project(self, manifest_path: Path) -> None:
        manifest = load_project_manifest(manifest_path)
        self._set_project(manifest)
        self.status.set(f"プロジェクトを開きました: {manifest.root}")

    def _open_project(self) -> None:
        selected = filedialog.askopenfilename(
            title="engine_project.json を選択",
            parent=self.root,
            initialdir=str(self.manifest.root.parent),
            filetypes=(("Engine project", "engine_project.json"), ("JSON", "*.json")),
        )
        if not selected:
            return
        try:
            self.open_project(Path(selected))
        except (OSError, ValueError) as exc:
            messagebox.showerror("開けません", str(exc))
            self.status.set("プロジェクトを開けませんでした")

    def _set_project(self, manifest: ProjectManifest) -> None:
        self.manifest = manifest
        self.launcher = ProcessLauncher(manifest)
        for child in self.root.winfo_children():
            child.destroy()
        self._build()

    def _create_project(self) -> None:
        name = simpledialog.askstring(
            "新規プロジェクト",
            "プロジェクト名",
            parent=self.root,
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            messagebox.showerror("作成できません", "プロジェクト名を入力してください。")
            return
        parent = filedialog.askdirectory(
            title="作成先フォルダーを選択",
            parent=self.root,
            initialdir=str(self.manifest.root.parent),
        )
        if not parent:
            return
        try:
            manifest_path = self.project_creator.create_project(Path(parent), name)
            manifest = load_project_manifest(manifest_path)
            self._set_project(manifest)
        except (OSError, ValueError) as exc:
            messagebox.showerror("作成できません", str(exc))
            self.status.set("新規プロジェクトの作成に失敗しました")
            return
        self.status.set(f"新規プロジェクトを作成して開きました: {manifest_path.parent}")
        messagebox.showinfo(
            "作成しました",
            f"{manifest_path.parent}\n\nengine_project.json を作成しました。",
        )
