"""Step-based editor for conversations.json."""

from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


PROJECT_DIR = Path(__file__).resolve().parent
DECK_PATH = PROJECT_DIR / "conversations.json"
PLACEMENTS_PATH = PROJECT_DIR / "placed_objects.json"

STEP_LABELS = {
    "say": "セリフ",
    "move": "タグへ移動",
    "take": "タグの物を取り出す",
    "put": "タグの物をしまう",
    "event": "既存イベント（ここで会話終了）",
}
STEP_VALUES = {label: value for value, label in STEP_LABELS.items()}
ACTOR_LABELS = {"kadoka": "かどか", "maru": "まる", "both": "ふたり"}
ACTOR_VALUES = {label: value for value, label in ACTOR_LABELS.items()}
EVENT_LABELS = {
    "water_bath": "水浴び",
    "game_device": "ゲーム機イベント（game_deviceを取り出す）",
}
EVENT_VALUES = {label: value for value, label in EVENT_LABELS.items()}


def load_tags() -> list[str]:
    try:
        raw = json.loads(PLACEMENTS_PATH.read_text(encoding="utf-8"))
        tags = {
            str(item.get("tag", "")).strip()
            for item in raw.get("objects", [])
            if isinstance(item, dict) and str(item.get("tag", "")).strip()
        }
        return sorted(tags)
    except (OSError, ValueError, AttributeError):
        return []


def normalize_step(raw: object) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    step_type = str(raw.get("type", "say"))
    if step_type == "say":
        speaker = str(raw.get("speaker", "kadoka"))
        text = str(raw.get("text", "")).strip()
        if speaker in ("kadoka", "maru") and text:
            return {"type": "say", "speaker": speaker, "text": text}
    elif step_type in ("move", "take", "put"):
        actor = str(raw.get("actor", "kadoka"))
        tag = str(raw.get("tag", "")).strip()
        if actor in ACTOR_LABELS and tag:
            return {"type": step_type, "actor": actor, "tag": tag}
    elif step_type == "event" and raw.get("event") in EVENT_LABELS:
        return {"type": "event", "event": str(raw["event"])}
    return None


def legacy_steps(item: dict) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    kadoka = str(item.get("kadoka", "")).strip()
    maru = str(item.get("maru", "")).strip()
    if kadoka:
        steps.append({"type": "say", "speaker": "kadoka", "text": kadoka})
    if maru:
        steps.append({"type": "say", "speaker": "maru", "text": maru})
    if item.get("event") in EVENT_LABELS:
        steps.append({"type": "event", "event": str(item["event"])})
    return steps


class ConversationEditor:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("おばけの住処・会話エディタ")
        self.root.geometry("1180x680")
        self.root.minsize(960, 560)
        self.data = self.load()
        self.tags = load_tags()
        self.current_conversation: int | None = None
        self.current_step: int | None = None
        self.loading_fields = False

        self.step_type_var = tk.StringVar(value=STEP_LABELS["say"])
        self.actor_var = tk.StringVar(value=ACTOR_LABELS["kadoka"])
        self.tag_var = tk.StringVar(value=self.tags[0] if self.tags else "")
        self.event_var = tk.StringVar(value=EVENT_LABELS["water_bath"])
        self.weight_var = tk.IntVar(value=1)
        self.status_var = tk.StringVar(value="発言や動作を上から順に実行します")

        self.build_ui()
        self.refresh_conversations(0 if self.data else None)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    @staticmethod
    def load() -> list[dict[str, object]]:
        try:
            raw = json.loads(DECK_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        result = []
        for item in raw if isinstance(raw, list) else []:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("steps"), list):
                steps = [step for value in item["steps"] if (step := normalize_step(value))]
            else:
                steps = legacy_steps(item)
            if steps:
                try:
                    weight = max(1, min(999, int(item.get("weight", 1))))
                except (TypeError, ValueError):
                    weight = 1
                result.append({"weight": weight, "steps": steps})
        return result

    def build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=2)
        outer.columnconfigure(1, weight=3)
        outer.columnconfigure(2, weight=4)
        outer.rowconfigure(0, weight=1)

        conversations = ttk.LabelFrame(outer, text="会話デッキ", padding=8)
        conversations.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        conversations.columnconfigure(0, weight=1)
        conversations.rowconfigure(0, weight=1)
        self.conversation_list = tk.Listbox(conversations, exportselection=False)
        self.conversation_list.grid(row=0, column=0, sticky="nsew")
        self.conversation_list.bind("<<ListboxSelect>>", self.select_conversation)
        conversation_buttons = ttk.Frame(conversations)
        conversation_buttons.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        for label, command in (
            ("会話追加", self.add_conversation),
            ("削除", self.delete_conversation),
            ("↑", lambda: self.move_conversation(-1)),
            ("↓", lambda: self.move_conversation(1)),
        ):
            ttk.Button(conversation_buttons, text=label, command=command).pack(
                side="left", padx=(0, 4)
            )
        weight_frame = ttk.Frame(conversations)
        weight_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(weight_frame, text="発生の重み").pack(side="left")
        self.weight_spinbox = ttk.Spinbox(
            weight_frame,
            from_=1,
            to=999,
            textvariable=self.weight_var,
            width=7,
            command=self.on_weight_edit,
        )
        self.weight_spinbox.pack(side="left", padx=(6, 0))
        self.weight_spinbox.bind("<KeyRelease>", self.on_weight_edit)
        self.weight_spinbox.bind("<FocusOut>", self.on_weight_edit)
        ttk.Label(
            weight_frame,
            text="大きいほど選ばれやすい",
            foreground="#666666",
        ).pack(side="left", padx=(7, 0))

        steps = ttk.LabelFrame(outer, text="この会話の順番", padding=8)
        steps.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        steps.columnconfigure(0, weight=1)
        steps.rowconfigure(0, weight=1)
        self.step_list = tk.Listbox(steps, exportselection=False)
        self.step_list.grid(row=0, column=0, sticky="nsew")
        self.step_list.bind("<<ListboxSelect>>", self.select_step)
        step_buttons = ttk.Frame(steps)
        step_buttons.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        for label, command in (
            ("手順追加", self.add_step),
            ("削除", self.delete_step),
            ("↑", lambda: self.move_step(-1)),
            ("↓", lambda: self.move_step(1)),
        ):
            ttk.Button(step_buttons, text=label, command=command).pack(
                side="left", padx=(0, 4)
            )
        fields = ttk.LabelFrame(outer, text="選択した手順を編集", padding=12)
        fields.grid(row=0, column=2, sticky="nsew")
        fields.columnconfigure(0, weight=1)
        fields.rowconfigure(5, weight=1)

        ttk.Label(fields, text="手順の種類").grid(row=0, column=0, sticky="w")
        self.type_combo = ttk.Combobox(
            fields, state="readonly", textvariable=self.step_type_var, values=list(STEP_VALUES)
        )
        self.type_combo.grid(row=1, column=0, sticky="ew", pady=(3, 10))
        self.type_combo.bind("<<ComboboxSelected>>", self.on_type_changed)

        ttk.Label(fields, text="話す／動くおばけ").grid(row=2, column=0, sticky="w")
        self.actor_combo = ttk.Combobox(
            fields, state="readonly", textvariable=self.actor_var, values=list(ACTOR_VALUES)
        )
        self.actor_combo.grid(row=3, column=0, sticky="ew", pady=(3, 10))
        self.actor_combo.bind("<<ComboboxSelected>>", self.on_edit)

        ttk.Label(fields, text="セリフ").grid(row=4, column=0, sticky="w")
        self.text = tk.Text(fields, height=7, wrap="word", font=("Yu Gothic UI", 12))
        self.text.grid(row=5, column=0, sticky="nsew", pady=(3, 10))
        self.text.bind("<KeyRelease>", self.on_edit)

        ttk.Label(fields, text="オブジェクトのタグ").grid(row=6, column=0, sticky="w")
        self.tag_combo = ttk.Combobox(fields, textvariable=self.tag_var, values=self.tags)
        self.tag_combo.grid(row=7, column=0, sticky="ew", pady=(3, 4))
        self.tag_combo.bind("<<ComboboxSelected>>", self.on_edit)
        self.tag_combo.bind("<KeyRelease>", self.on_edit)
        ttk.Label(
            fields,
            text="タグはオブジェクトエディタで設定します。取り出す＝表示、しまう＝非表示です。",
            foreground="#666666",
            wraplength=420,
        ).grid(row=8, column=0, sticky="w", pady=(0, 10))

        ttk.Label(fields, text="既存イベント").grid(row=9, column=0, sticky="w")
        self.event_combo = ttk.Combobox(
            fields, state="readonly", textvariable=self.event_var, values=list(EVENT_VALUES)
        )
        self.event_combo.grid(row=10, column=0, sticky="ew", pady=(3, 10))
        self.event_combo.bind("<<ComboboxSelected>>", self.on_edit)

        footer = ttk.Frame(fields)
        footer.grid(row=11, column=0, sticky="ew")
        ttk.Label(footer, textvariable=self.status_var).pack(side="left")
        ttk.Button(footer, text="JSONへ保存", command=self.save).pack(side="right")
        self.update_field_states()

    def conversation_label(self, item: dict) -> str:
        parts = [self.step_label(step) for step in item["steps"][:2]]
        suffix = " …" if len(item["steps"]) > 2 else ""
        return f"重み{item.get('weight', 1)}｜" + " → ".join(parts) + suffix

    @staticmethod
    def step_label(step: dict[str, str]) -> str:
        kind = step["type"]
        if kind == "say":
            return f"{ACTOR_LABELS[step['speaker']]}「{step['text']}」"
        if kind in ("move", "take", "put"):
            return f"{ACTOR_LABELS[step['actor']]}：{STEP_LABELS[kind]} #{step['tag']}"
        return f"イベント：{EVENT_LABELS[step['event']]}"

    def refresh_conversations(self, selected: int | None = None) -> None:
        self.conversation_list.delete(0, "end")
        for item in self.data:
            self.conversation_list.insert("end", self.conversation_label(item))
        if selected is not None and self.data:
            selected = max(0, min(selected, len(self.data) - 1))
            self.conversation_list.selection_set(selected)
            self.show_conversation(selected)
        else:
            self.current_conversation = None
            self.current_step = None
            self.step_list.delete(0, "end")

    def show_conversation(self, index: int, selected_step: int = 0) -> None:
        self.current_conversation = index
        self.loading_fields = True
        self.weight_var.set(int(self.data[index].get("weight", 1)))
        self.loading_fields = False
        self.step_list.delete(0, "end")
        for step in self.data[index]["steps"]:
            self.step_list.insert("end", self.step_label(step))
        if self.data[index]["steps"]:
            selected_step = max(0, min(selected_step, len(self.data[index]["steps"]) - 1))
            self.step_list.selection_set(selected_step)
            self.show_step(selected_step)

    def show_step(self, index: int) -> None:
        if self.current_conversation is None:
            return
        step = self.data[self.current_conversation]["steps"][index]
        self.current_step = index
        self.loading_fields = True
        self.step_type_var.set(STEP_LABELS[step["type"]])
        actor = step.get("speaker", step.get("actor", "kadoka"))
        self.actor_var.set(ACTOR_LABELS.get(actor, ACTOR_LABELS["kadoka"]))
        self.text.delete("1.0", "end")
        self.text.insert("1.0", step.get("text", ""))
        self.tag_var.set(step.get("tag", self.tags[0] if self.tags else ""))
        self.event_var.set(EVENT_LABELS.get(step.get("event", "water_bath"), EVENT_LABELS["water_bath"]))
        self.loading_fields = False
        self.update_field_states()

    def update_field_states(self) -> None:
        kind = STEP_VALUES.get(self.step_type_var.get(), "say")
        self.actor_combo.configure(state="readonly" if kind != "event" else "disabled")
        self.text.configure(state="normal" if kind == "say" else "disabled")
        self.tag_combo.configure(state="normal" if kind in ("move", "take", "put") else "disabled")
        self.event_combo.configure(state="readonly" if kind == "event" else "disabled")

    def build_current_step(self) -> dict[str, str]:
        kind = STEP_VALUES.get(self.step_type_var.get(), "say")
        actor = ACTOR_VALUES.get(self.actor_var.get(), "kadoka")
        if kind == "say":
            if actor == "both":
                actor = "kadoka"
            return {"type": "say", "speaker": actor, "text": self.text.get("1.0", "end-1c").strip()}
        if kind in ("move", "take", "put"):
            return {"type": kind, "actor": actor, "tag": self.tag_var.get().strip()}
        return {"type": "event", "event": EVENT_VALUES.get(self.event_var.get(), "water_bath")}

    def commit_step(self) -> None:
        if self.loading_fields or self.current_conversation is None or self.current_step is None:
            return
        self.data[self.current_conversation]["steps"][self.current_step] = self.build_current_step()

    def select_conversation(self, _event: object = None) -> None:
        selection = self.conversation_list.curselection()
        if not selection:
            return
        index = int(selection[0])
        if index != self.current_conversation:
            self.commit_step()
            self.show_conversation(index)

    def select_step(self, _event: object = None) -> None:
        selection = self.step_list.curselection()
        if not selection:
            return
        index = int(selection[0])
        if index != self.current_step:
            self.commit_step()
            self.show_step(index)

    def on_type_changed(self, _event: object = None) -> None:
        self.update_field_states()
        self.on_edit()

    def on_edit(self, _event: object = None) -> None:
        if self.loading_fields or self.current_conversation is None or self.current_step is None:
            return
        self.commit_step()
        step = self.data[self.current_conversation]["steps"][self.current_step]
        self.step_list.delete(self.current_step)
        self.step_list.insert(self.current_step, self.step_label(step))
        self.step_list.selection_set(self.current_step)
        self.conversation_list.delete(self.current_conversation)
        self.conversation_list.insert(
            self.current_conversation, self.conversation_label(self.data[self.current_conversation])
        )
        self.conversation_list.selection_set(self.current_conversation)
        self.status_var.set("未保存の変更があります")

    def on_weight_edit(self, _event: object = None) -> None:
        if self.loading_fields or self.current_conversation is None:
            return
        try:
            weight = max(1, min(999, int(self.weight_var.get())))
        except (tk.TclError, TypeError, ValueError):
            return
        self.weight_var.set(weight)
        self.data[self.current_conversation]["weight"] = weight
        self.conversation_list.delete(self.current_conversation)
        self.conversation_list.insert(
            self.current_conversation,
            self.conversation_label(self.data[self.current_conversation]),
        )
        self.conversation_list.selection_set(self.current_conversation)
        self.status_var.set("未保存の変更があります")

    def add_conversation(self) -> None:
        self.commit_step()
        self.data.append({"weight": 1, "steps": [
            {"type": "say", "speaker": "kadoka", "text": "新しいセリフ"},
            {"type": "say", "speaker": "maru", "text": "新しいセリフなのだ！"},
        ]})
        self.refresh_conversations(len(self.data) - 1)
        self.status_var.set("未保存の変更があります")

    def delete_conversation(self) -> None:
        if self.current_conversation is None:
            return
        if not messagebox.askyesno("削除", "この会話を削除しますか？"):
            return
        index = self.current_conversation
        del self.data[index]
        self.refresh_conversations(min(index, len(self.data) - 1) if self.data else None)
        self.status_var.set("未保存の変更があります")

    def move_conversation(self, amount: int) -> None:
        if self.current_conversation is None:
            return
        self.commit_step()
        destination = self.current_conversation + amount
        if not 0 <= destination < len(self.data):
            return
        self.data[self.current_conversation], self.data[destination] = self.data[destination], self.data[self.current_conversation]
        self.refresh_conversations(destination)
        self.status_var.set("未保存の変更があります")

    def add_step(self) -> None:
        if self.current_conversation is None:
            return
        self.commit_step()
        steps = self.data[self.current_conversation]["steps"]
        insert_at = len(steps) if self.current_step is None else self.current_step + 1
        steps.insert(insert_at, {"type": "say", "speaker": "kadoka", "text": "つづき"})
        self.show_conversation(self.current_conversation, insert_at)
        self.status_var.set("未保存の変更があります")

    def delete_step(self) -> None:
        if self.current_conversation is None or self.current_step is None:
            return
        steps = self.data[self.current_conversation]["steps"]
        if len(steps) <= 1:
            messagebox.showinfo("削除できません", "会話には手順を1つ以上残してください。")
            return
        index = self.current_step
        del steps[index]
        self.show_conversation(self.current_conversation, min(index, len(steps) - 1))
        self.status_var.set("未保存の変更があります")

    def move_step(self, amount: int) -> None:
        if self.current_conversation is None or self.current_step is None:
            return
        self.commit_step()
        steps = self.data[self.current_conversation]["steps"]
        destination = self.current_step + amount
        if not 0 <= destination < len(steps):
            return
        steps[self.current_step], steps[destination] = steps[destination], steps[self.current_step]
        self.show_conversation(self.current_conversation, destination)
        self.status_var.set("未保存の変更があります")

    def save(self) -> bool:
        self.commit_step()
        if not self.data:
            messagebox.showerror("保存できません", "会話を1件以上登録してください。")
            return False
        for number, item in enumerate(self.data, 1):
            try:
                item["weight"] = max(1, min(999, int(item.get("weight", 1))))
            except (TypeError, ValueError):
                messagebox.showerror("保存できません", f"会話{number}の重みが正しくありません。")
                return False
            if not item["steps"]:
                messagebox.showerror("保存できません", f"会話{number}に手順がありません。")
                return False
            for step in item["steps"]:
                if step["type"] == "say" and not step.get("text", "").strip():
                    messagebox.showerror("保存できません", f"会話{number}に空のセリフがあります。")
                    return False
                if step["type"] in ("move", "take", "put") and not step.get("tag", "").strip():
                    messagebox.showerror("保存できません", f"会話{number}のタグが空です。")
                    return False
        temporary = DECK_PATH.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(self.data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(DECK_PATH)
        self.refresh_conversations(self.current_conversation)
        self.status_var.set("保存しました。次回ゲーム起動時から反映されます")
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
