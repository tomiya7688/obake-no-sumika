"""Editor for the character definitions used directly by the game."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from engine.character_definition import CharacterDefinition
from engine.character_repository import CharacterRepository


PROJECT_DIR = Path(__file__).resolve().parent
CHARACTER_PATH = PROJECT_DIR / "characters.json"
FACING_LABELS = {"右向き（1）": 1, "左向き（-1）": -1}


class CharacterEditor:
    """Edit the characters exposed by one engine project."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("おばけの住処・キャラクターエディター")
        self.root.geometry("920x620")
        self.root.minsize(820, 560)
        self.repository = CharacterRepository(PROJECT_DIR, CHARACTER_PATH)
        self.definitions = list(self.repository.load())
        self.selected_index: int | None = None
        self.preview_photo: ImageTk.PhotoImage | None = None

        self.id_var = tk.StringVar()
        self.display_name_var = tk.StringVar()
        self.image_var = tk.StringVar()
        self.start_x_var = tk.StringVar()
        self.start_y_var = tk.StringVar()
        self.height_var = tk.StringVar()
        self.personality_var = tk.StringVar()
        self.facing_var = tk.StringVar()
        self.bubble_y_var = tk.StringVar()
        self.status_var = tk.StringVar(value="キャラクターを選択してください")

        self._build_ui()
        self._refresh_list()
        if self.definitions:
            self.character_list.selection_set(0)
            self._select_character()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=16)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=3)
        outer.rowconfigure(0, weight=1)

        list_frame = ttk.LabelFrame(outer, text="キャラクター", padding=8)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.character_list = tk.Listbox(list_frame, exportselection=False)
        self.character_list.grid(row=0, column=0, sticky="nsew")
        self.character_list.bind("<<ListboxSelect>>", self._select_character)

        form = ttk.LabelFrame(outer, text="設定", padding=14)
        form.grid(row=0, column=1, sticky="nsew")
        form.columnconfigure(1, weight=1)
        fields = (
            ("ID（会話・イベント連携用）", self.id_var),
            ("表示名", self.display_name_var),
            ("開始位置 X（0～960）", self.start_x_var),
            ("開始位置 Y（0～540）", self.start_y_var),
            ("表示身長（16～256 px）", self.height_var),
            ("行動速度倍率（0.25～3.0）", self.personality_var),
            ("吹き出し高さ補正（-200～200）", self.bubble_y_var),
        )
        for row, (label, variable) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=5)
            entry = ttk.Entry(form, textvariable=variable)
            entry.grid(row=row, column=1, sticky="ew", pady=5)
            if row == 0:
                entry.configure(state="readonly")

        facing_row = len(fields)
        ttk.Label(form, text="元画像が向いている方向").grid(
            row=facing_row, column=0, sticky="w", pady=5
        )
        ttk.Combobox(
            form,
            state="readonly",
            textvariable=self.facing_var,
            values=list(FACING_LABELS),
        ).grid(row=facing_row, column=1, sticky="ew", pady=5)

        image_row = facing_row + 1
        ttk.Label(form, text="画像").grid(row=image_row, column=0, sticky="w", pady=5)
        image_frame = ttk.Frame(form)
        image_frame.grid(row=image_row, column=1, sticky="ew", pady=5)
        image_frame.columnconfigure(0, weight=1)
        ttk.Entry(image_frame, textvariable=self.image_var, state="readonly").grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Button(image_frame, text="選択", command=self._choose_image).grid(
            row=0, column=1, padx=(6, 0)
        )

        preview_row = image_row + 1
        self.preview_label = ttk.Label(form, anchor="center")
        self.preview_label.grid(row=preview_row, column=0, columnspan=2, pady=12)

        buttons = ttk.Frame(form)
        buttons.grid(row=preview_row + 1, column=0, columnspan=2, sticky="ew")
        ttk.Button(buttons, text="変更を反映", command=self._apply_fields).pack(
            side="left"
        )
        ttk.Button(buttons, text="characters.jsonへ保存", command=self._save).pack(
            side="left", padx=(8, 0)
        )
        ttk.Label(outer, textvariable=self.status_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(12, 0)
        )

    def _refresh_list(self) -> None:
        self.character_list.delete(0, "end")
        for definition in self.definitions:
            self.character_list.insert("end", f"{definition.display_name}  ({definition.id})")

    def _select_character(self, _event: object | None = None) -> None:
        selection = self.character_list.curselection()
        if not selection:
            return
        self.selected_index = selection[0]
        definition = self.definitions[self.selected_index]
        self.id_var.set(definition.id)
        self.display_name_var.set(definition.display_name)
        self.image_var.set(definition.image.relative_to(PROJECT_DIR).as_posix())
        self.start_x_var.set(str(definition.start_x))
        self.start_y_var.set(str(definition.start_y))
        self.height_var.set(str(definition.display_height))
        self.personality_var.set(str(definition.personality))
        self.facing_var.set(next(label for label, value in FACING_LABELS.items() if value == definition.native_facing))
        self.bubble_y_var.set(str(definition.bubble_y_offset))
        self._show_preview(definition.image)
        self.status_var.set(f"{definition.display_name}を編集中")

    def _choose_image(self) -> None:
        selected = filedialog.askopenfilename(
            title="キャラクター画像を選択",
            initialdir=PROJECT_DIR / "assets",
            filetypes=[("PNG / WebP", "*.png *.webp"), ("すべてのファイル", "*.*")],
        )
        if not selected:
            return
        path = Path(selected).resolve()
        if PROJECT_DIR.resolve() not in path.parents:
            messagebox.showerror("選択できません", "プロジェクト内の画像を選んでください。")
            return
        self.image_var.set(path.relative_to(PROJECT_DIR).as_posix())
        self._show_preview(path)

    def _definition_from_fields(self) -> CharacterDefinition:
        if self.selected_index is None:
            raise ValueError("キャラクターが選択されていません")
        definition = CharacterDefinition(
            id=self.id_var.get().strip(),
            display_name=self.display_name_var.get().strip(),
            image=(PROJECT_DIR / self.image_var.get()).resolve(),
            start_x=int(self.start_x_var.get()),
            start_y=int(self.start_y_var.get()),
            display_height=int(self.height_var.get()),
            personality=float(self.personality_var.get()),
            native_facing=FACING_LABELS.get(self.facing_var.get(), 1),
            bubble_y_offset=int(self.bubble_y_var.get()),
        )
        self.repository.validate(definition)
        return definition

    def _apply_fields(self) -> bool:
        try:
            definition = self._definition_from_fields()
        except (ValueError, OSError) as exc:
            messagebox.showerror("設定を反映できません", str(exc))
            return False
        assert self.selected_index is not None
        selected = self.selected_index
        self.definitions[selected] = definition
        self._refresh_list()
        self.character_list.selection_set(selected)
        self.status_var.set(f"{definition.display_name}の変更を反映しました（未保存）")
        return True

    def _save(self) -> None:
        if not self._apply_fields():
            return
        try:
            self.repository.save(self.definitions)
        except (ValueError, OSError) as exc:
            messagebox.showerror("保存できません", str(exc))
            return
        self.status_var.set("characters.jsonへ保存しました。次回のゲーム起動から反映されます")

    def _show_preview(self, image_path: Path) -> None:
        try:
            image = Image.open(image_path).convert("RGBA")
            bounds = image.getbbox()
            if bounds:
                image = image.crop(bounds)
            image.thumbnail((180, 180), Image.Resampling.LANCZOS)
            self.preview_photo = ImageTk.PhotoImage(image)
            self.preview_label.configure(image=self.preview_photo, text="")
        except (OSError, ValueError):
            self.preview_photo = None
            self.preview_label.configure(image="", text="プレビューできません")


def main() -> None:
    root = tk.Tk()
    try:
        CharacterEditor(root)
    except (OSError, ValueError) as exc:
        messagebox.showerror("キャラクター定義を開けません", str(exc), parent=root)
        root.destroy()
        return
    root.mainloop()


if __name__ == "__main__":
    main()
