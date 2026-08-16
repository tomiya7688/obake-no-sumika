"""Small standard-library editor for conversations.json."""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


DECK_PATH = Path(__file__).resolve().parent / "conversations.json"
EVENT_LABELS = {
    "": "なし（通常会話）",
    "water_bath": "水浴びへ移動",
    "game_device": "ゲーム機イベント",
}
EVENT_VALUES = {label: value for value, label in EVENT_LABELS.items()}


class ConversationEditor:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("おばけの住処・会話エディタ")
        self.root.geometry("820x500")
        self.root.minsize(680, 420)
        self.data = self.load()
        self.current_index: int | None = None
        self.loading_fields = False

        main = ttk.Frame(root, padding=12)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=2)
        main.columnconfigure(1, weight=3)
        main.rowconfigure(0, weight=1)

        list_frame = ttk.Frame(main)
        list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(1, weight=1)
        ttk.Label(list_frame, text="会話一覧").grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.listbox = tk.Listbox(list_frame, exportselection=False)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        left_buttons = ttk.Frame(list_frame)
        left_buttons.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        for label, command in (
            ("追加", self.add),
            ("削除", self.delete),
            ("↑", lambda: self.move(-1)),
            ("↓", lambda: self.move(1)),
        ):
            ttk.Button(left_buttons, text=label, command=command).pack(side="left", padx=(0, 5))

        fields = ttk.Frame(main)
        fields.grid(row=0, column=1, sticky="nsew")
        fields.columnconfigure(0, weight=1)
        fields.rowconfigure(1, weight=1)
        fields.rowconfigure(3, weight=1)

        ttk.Label(fields, text="かどかのセリフ").grid(row=0, column=0, sticky="w")
        self.kadoka_text = tk.Text(fields, height=5, wrap="word", font=("Yu Gothic UI", 12))
        self.kadoka_text.grid(row=1, column=0, sticky="nsew", pady=(4, 12))
        ttk.Label(fields, text="まるのセリフ").grid(row=2, column=0, sticky="w")
        self.maru_text = tk.Text(fields, height=5, wrap="word", font=("Yu Gothic UI", 12))
        self.maru_text.grid(row=3, column=0, sticky="nsew", pady=(4, 12))
        self.kadoka_text.bind("<KeyRelease>", self.on_edit)
        self.maru_text.bind("<KeyRelease>", self.on_edit)

        ttk.Label(fields, text="会話後のイベント").grid(row=4, column=0, sticky="w")
        self.event_var = tk.StringVar(value=EVENT_LABELS[""])
        self.event_combo = ttk.Combobox(
            fields,
            state="readonly",
            textvariable=self.event_var,
            values=list(EVENT_VALUES),
        )
        self.event_combo.grid(row=5, column=0, sticky="ew", pady=(4, 12))
        self.event_combo.bind("<<ComboboxSelected>>", self.on_edit)

        footer = ttk.Frame(fields)
        footer.grid(row=6, column=0, sticky="ew")
        self.status = ttk.Label(footer, text="編集後に保存してください")
        self.status.pack(side="left")
        ttk.Button(footer, text="JSONへ保存", command=self.save).pack(side="right")

        self.refresh(0 if self.data else None)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    @staticmethod
    def load() -> list[dict[str, str]]:
        try:
            raw = json.loads(DECK_PATH.read_text(encoding="utf-8"))
            result = []
            for item in raw:
                if not isinstance(item, dict):
                    continue
                entry = {
                    "kadoka": str(item.get("kadoka", "")),
                    "maru": str(item.get("maru", "")),
                }
                if item.get("event") in EVENT_LABELS:
                    entry["event"] = item["event"]
                result.append(entry)
            return result
        except (OSError, ValueError):
            return []

    def label_for(self, item: dict[str, str]) -> str:
        event = item.get("event", "")
        tag = f"［{EVENT_LABELS[event]}］ " if event else ""
        return f"{tag}{item['kadoka']}　／　{item['maru']}"

    def refresh(self, selected: int | None = None) -> None:
        self.listbox.delete(0, "end")
        for item in self.data:
            self.listbox.insert("end", self.label_for(item))
        if selected is not None and self.data:
            selected = max(0, min(selected, len(self.data) - 1))
            self.listbox.selection_set(selected)
            self.listbox.see(selected)
            self.show(selected)
        else:
            self.current_index = None

    def show(self, index: int) -> None:
        self.current_index = index
        self.loading_fields = True
        self.kadoka_text.delete("1.0", "end")
        self.maru_text.delete("1.0", "end")
        self.kadoka_text.insert("1.0", self.data[index]["kadoka"])
        self.maru_text.insert("1.0", self.data[index]["maru"])
        self.event_var.set(EVENT_LABELS.get(self.data[index].get("event", ""), EVENT_LABELS[""]))
        self.loading_fields = False

    def commit(self) -> None:
        if self.current_index is None or self.loading_fields:
            return
        entry = {
            "kadoka": self.kadoka_text.get("1.0", "end-1c"),
            "maru": self.maru_text.get("1.0", "end-1c"),
        }
        event = EVENT_VALUES.get(self.event_var.get(), "")
        if event:
            entry["event"] = event
        self.data[self.current_index] = entry

    def on_select(self, _event: object = None) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if index != self.current_index:
            self.commit()
            self.show(index)

    def on_edit(self, _event: object = None) -> None:
        if self.loading_fields or self.current_index is None:
            return
        self.commit()
        self.listbox.delete(self.current_index)
        self.listbox.insert(self.current_index, self.label_for(self.data[self.current_index]))
        self.listbox.selection_set(self.current_index)
        self.status.configure(text="未保存の変更があります")

    def add(self) -> None:
        self.commit()
        self.data.append({"kadoka": "新しいセリフ", "maru": "新しいセリフなのだ！"})
        self.refresh(len(self.data) - 1)
        self.status.configure(text="未保存の変更があります")

    def delete(self) -> None:
        if self.current_index is None:
            return
        if not messagebox.askyesno("削除", "この会話を削除しますか？"):
            return
        index = self.current_index
        del self.data[index]
        self.refresh(min(index, len(self.data) - 1) if self.data else None)
        self.status.configure(text="未保存の変更があります")

    def move(self, amount: int) -> None:
        if self.current_index is None:
            return
        self.commit()
        destination = self.current_index + amount
        if not 0 <= destination < len(self.data):
            return
        self.data[self.current_index], self.data[destination] = (
            self.data[destination], self.data[self.current_index]
        )
        self.refresh(destination)
        self.status.configure(text="未保存の変更があります")

    def save(self) -> bool:
        self.commit()
        if not self.data:
            messagebox.showerror("保存できません", "会話を1件以上登録してください。")
            return False
        if any(not item["kadoka"].strip() or not item["maru"].strip() for item in self.data):
            messagebox.showerror("保存できません", "空のセリフがあります。")
            return False
        temporary = DECK_PATH.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(DECK_PATH)
        self.status.configure(text="保存しました。次回ゲーム起動時から反映されます")
        return True

    def on_close(self) -> None:
        answer = messagebox.askyesnocancel("終了", "変更を保存して終了しますか？")
        if answer is None:
            return
        if answer and not self.save():
            return
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    ConversationEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
