"""One-click real-screen checks for Kadoka (Issue #123).

run_manual_check.bat opens a window listing checks. Choosing one shows plain
steps and the expected result; "エディターを開く" copies the committed game data
(from git HEAD, never the working tree) into a separate folder, changes that
copy for the check, and opens the editor on it. The real project data is never
modified. Answers are saved to results.json in the check folder so agents can
read them.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
# Copied for every check: the editors and the data and assets they read
# (git pathspecs, matched against HEAD).
COPY_PATTERNS = (":(glob)*.py", ":(glob)*.json", "engine", "assets", "objects")
PREFERRED_WORK_ROOT = Path("E:/program_files/soft/claude/tmp")


def work_root() -> Path:
    """Where check folders go: OBAKE_MANUAL_CHECK_DIR, else E: scratch, else temp."""
    configured = os.environ.get("OBAKE_MANUAL_CHECK_DIR")
    if configured:
        return Path(configured)
    if PREFERRED_WORK_ROOT.is_dir():
        return PREFERRED_WORK_ROOT / "obake_manual_check"
    return Path(tempfile.gettempdir()) / "obake_manual_check"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def break_conversations(folder: Path) -> None:
    path = folder / "conversations.json"
    deck = read_json(path)
    deck.append({"weight": 1, "steps": [{"type": "say", "speaker": "nobody", "text": "x"}]})
    deck.append("これは会話ではない")
    write_json(path, deck)


def use_generic_ids(folder: Path) -> None:
    characters = read_json(folder / "characters.json")
    player = dict(characters["characters"][0], id="player", display_name="プレイヤー")
    characters["characters"] = [player]
    write_json(folder / "characters.json", characters)
    write_json(
        folder / "events.json",
        {"schema_version": 1, "events": [{"id": "idle", "label": "待機", "terminal": True}]},
    )
    say = {"type": "say", "speaker": "player", "text": "ひとりだ"}
    write_json(
        folder / "conversations.json",
        [{"weight": 1, "steps": [say, {"type": "event", "event": "idle"}]}],
    )


def break_placements(folder: Path) -> None:
    path = folder / "placed_objects.json"
    data = read_json(path)
    first, second = data["objects"][0], data["objects"][1]
    data["objects"].append(dict(first, name="重複IDの配置", x=100))
    data["objects"].append(dict(second, id="far_away", tag="far_away", x=5000))
    write_json(path, data)


@dataclass(frozen=True)
class Step:
    action: str
    expected: str


@dataclass(frozen=True)
class Scenario:
    id: str
    issue: int
    title: str
    editor: str
    prepare: Callable[[Path], None]
    steps: tuple[Step, ...] = field(default_factory=tuple)


SCENARIOS = (
    Scenario(
        "conversation-load-errors",
        30,
        "会話エディター: 読めない会話があるとき",
        "conversation_editor.py",
        break_conversations,
        (
            Step(
                "「エディターを開く」を押す",
                "「読込エラー」の警告が出て、読めない会話が2件並んでいる",
            ),
            Step("警告を閉じる", "下の欄に「読込エラーがあります」と出ている"),
            Step(
                "どれかのセリフを少し変えて「JSONへ保存」を押す",
                "「破棄して保存しますか？」と聞かれる",
            ),
            Step("「いいえ」を押す", "保存されない（何も起きない）"),
            Step("もう一度「JSONへ保存」→「はい」を押す", "「保存しました」と出る"),
        ),
    ),
    Scenario(
        "conversation-generic-ids",
        26,
        "会話エディター: かどか・水浴びがないプロジェクト",
        "conversation_editor.py",
        use_generic_ids,
        (
            Step(
                "「エディターを開く」を押す",
                "エラーなしで開き、話者は「プレイヤー」だけ（「ふたり」は無い）",
            ),
            Step(
                "「この会話の順番」の2番目（待機）を選び、次に1番目を選ぶ",
                "セリフ欄に「ひとりだ」と出ている（空にならない）",
            ),
            Step("「手順追加」「会話追加」を押してから「JSONへ保存」", "「保存しました」と出る"),
        ),
    ),
    Scenario(
        "object-load-errors",
        24,
        "オブジェクトエディター: 読めない配置があるとき",
        "object_editor.py",
        break_placements,
        (
            Step(
                "「エディターを開く」を押す",
                "「読込エラー」の警告が出て、読めない配置が2件並んでいる",
            ),
            Step(
                "「2. おばけの住処に置く」の住処の絵で、置いてある物を少しドラッグして離す",
                "「破棄して保存しますか？」と聞かれる",
            ),
            Step("「いいえ」を押す", "下の欄に「読込エラーがあるため保存していません」と出る"),
            Step(
                "もう一度ドラッグして離し、「はい」を押す",
                "「ドラッグした位置を保存しました」と出る",
            ),
        ),
    ),
)


def prepare_check(scenario: Scenario, repo: Path, root: Path) -> Path:
    """Copy committed files into a fresh folder for the scenario and apply its change."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = root / f"{stamp}-{scenario.id}"
    folder.mkdir(parents=True)
    # One git call: starting git is slow on some machines, so avoid one per file.
    archive = subprocess.run(
        [
            "git",
            "-c",
            "core.autocrlf=false",
            "archive",
            "--format=tar",
            "HEAD",
            "--",
            *COPY_PATTERNS,
        ],
        cwd=repo,
        capture_output=True,
        check=True,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar.getmembers():
            if member.isfile():
                target = folder / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tar.extractfile(member).read())
    scenario.prepare(folder)
    return folder


def open_editor(scenario: Scenario, folder: Path) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, str(folder / scenario.editor)], cwd=folder)


def save_results(path: Path, scenario: Scenario, folder: Path | None, answers: list) -> None:
    """Record answers ("ok"/"ng"/None and a note per step) in results.json."""
    results = read_json(path) if path.exists() else {"schema_version": 1, "checks": []}
    results["checks"].append(
        {
            "scenario": scenario.id,
            "issue": scenario.issue,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "folder": str(folder) if folder else None,
            "steps": [
                {"action": step.action, "expected": step.expected, "result": result, "note": note}
                for step, (result, note) in zip(scenario.steps, answers)
            ],
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, results)


class CheckWindow:
    def __init__(self, root, repo: Path = PROJECT_ROOT, base: Path | None = None) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk, self.ttk = tk, ttk
        self.root, self.repo = root, repo
        self.base = base or work_root()
        self.results_path = self.base / "results.json"
        self.folder: Path | None = None
        self.scenario = SCENARIOS[0]
        root.title("おばけの住処・実画面確認")
        root.geometry("900x560")
        left = ttk.Frame(root, padding=8)
        left.pack(side="left", fill="y")
        ttk.Label(left, text="確認すること").pack(anchor="w")
        self.listbox = tk.Listbox(left, width=34, height=12, exportselection=False)
        for scenario in SCENARIOS:
            self.listbox.insert("end", f"#{scenario.issue} {scenario.title}")
        self.listbox.pack(fill="y", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)
        self.right = ttk.Frame(root, padding=8)
        self.right.pack(side="left", fill="both", expand=True)
        self.status = tk.StringVar(value=f"結果の保存先: {self.results_path}")
        ttk.Label(root, textvariable=self.status, foreground="#475e68").pack(side="bottom")
        self.listbox.selection_set(0)
        self.show(SCENARIOS[0])

    def on_select(self, _event=None) -> None:
        picked = self.listbox.curselection()
        if picked:
            self.show(SCENARIOS[picked[0]])

    def show(self, scenario: Scenario) -> None:
        ttk, tk = self.ttk, self.tk
        self.scenario, self.folder = scenario, None
        for child in self.right.winfo_children():
            child.destroy()
        ttk.Label(self.right, text=scenario.title, font=("Yu Gothic UI", 13, "bold")).pack(
            anchor="w"
        )
        ttk.Label(
            self.right,
            text="本物のデータは変わりません。確認用のコピーを開きます。上から順に操作し、"
            "期待どおりなら「できた」、違ったら「違った」を選んでください。",
            wraplength=560,
        ).pack(anchor="w", pady=(4, 8))
        ttk.Button(self.right, text="エディターを開く", command=self.open).pack(anchor="w")
        self.answers = []
        for number, step in enumerate(scenario.steps, 1):
            box = ttk.Frame(self.right, padding=(0, 6))
            box.pack(fill="x")
            ttk.Label(box, text=f"{number}. {step.action}", wraplength=560).pack(anchor="w")
            ttk.Label(box, text=f"→ {step.expected}", foreground="#2f6b3a", wraplength=560).pack(
                anchor="w"
            )
            choice, note = tk.StringVar(value=""), tk.StringVar()
            row = ttk.Frame(box)
            row.pack(anchor="w")
            ttk.Radiobutton(row, text="できた", variable=choice, value="ok").pack(side="left")
            ttk.Radiobutton(row, text="違った", variable=choice, value="ng").pack(side="left")
            ttk.Label(row, text="  メモ:").pack(side="left")
            ttk.Entry(row, textvariable=note, width=40).pack(side="left")
            self.answers.append((choice, note))
        ttk.Button(self.right, text="結果を保存", command=self.save).pack(anchor="w", pady=8)

    def open(self) -> None:
        self.folder = prepare_check(self.scenario, self.repo, self.base)
        open_editor(self.scenario, self.folder)
        self.status.set(f"確認用のコピーを開きました: {self.folder}")

    def save(self) -> None:
        answers = [(choice.get() or None, note.get().strip()) for choice, note in self.answers]
        save_results(self.results_path, self.scenario, self.folder, answers)
        self.status.set(f"保存しました: {self.results_path}")


def main() -> int:
    import tkinter as tk

    root = tk.Tk()
    CheckWindow(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
