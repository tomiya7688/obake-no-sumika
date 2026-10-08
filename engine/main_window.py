from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .manifest_loader import load_project_manifest
from .process_launcher import LaunchedProcess, ProcessLauncher
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
        self._launch_poll_ids: set[str] = set()
        self.root.bind("<Destroy>", self._cancel_launch_polls, add="+")
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
            launched = action()
        except OSError as exc:
            messagebox.showerror("起動できません", f"{label}を起動できませんでした。\n{exc}")
            self.status.set(f"{label}の起動に失敗しました")
            return
        # Popen success is not proof that imports/validation/startup succeeded.
        # Keep the GUI responsive and monitor the child's actual exit status.
        target = f"{label}（{self.manifest.name}）"
        self.status.set(f"{target}の起動を確認しています")
        self._schedule_launch_poll(target, launched, announced=False)

    def _schedule_launch_poll(
        self, label: str, launched: LaunchedProcess, *, announced: bool
    ) -> None:
        def check() -> None:
            self._launch_poll_ids.discard(callback_id)
            self._poll_launch(label, launched, announced=announced)

        callback_id = self.root.after(150, check)
        self._launch_poll_ids.add(callback_id)

    def _poll_launch(self, label: str, launched: LaunchedProcess, *, announced: bool) -> None:
        exit_code = launched.poll()
        if exit_code is None:
            if not announced:
                self.status.set(f"{label}を実行中です")
            self._schedule_launch_poll(label, launched, announced=True)
            return
        if exit_code == 0:
            self.status.set(f"{label}が終了しました")
            return
        self.status.set(f"{label}が異常終了しました（終了コード: {exit_code}）")
        try:
            detail = launched.log_tail().strip() or "ログ出力はありません。"
        except OSError as exc:
            detail = f"ログを読み取れませんでした: {exc}"
        messagebox.showerror(
            "実行に失敗しました",
            f"{label}が異常終了しました。\n終了コード: {exit_code}\n"
            f"ログ: {launched.log_path}\n\n{detail}",
            parent=self.root,
        )

    def _cancel_launch_polls(self, event) -> None:
        if event.widget is not self.root:
            return
        for callback_id in self._launch_poll_ids:
            self.root.after_cancel(callback_id)
        self._launch_poll_ids.clear()
        # Preserve the previous behavior: closing the engine does not kill
        # independently running games/editors; their logs remain on disk.

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
