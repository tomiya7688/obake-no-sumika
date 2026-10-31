from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.manual_check.script import manual_check as kit

ROOT = Path(__file__).resolve().parents[1]
REAL_DATA = (
    "characters.json",
    "conversations.json",
    "events.json",
    "placed_objects.json",
    "room.json",
)
# What each scenario's copy must make the editor see: number of load problems
# per repository, and the speaker labels where relevant.
EXPECTED = {
    "conversation-load-errors": {"conversation_problems": 2},
    "conversation-generic-ids": {"conversation_problems": 0, "labels": {"player": "プレイヤー"}},
    "object-load-errors": {"placement_problems": 2},
}
PROBE = """
import json, sys
sys.path.insert(0, ".")
import {module} as editor
report = {{}}
if hasattr(editor, "CONVERSATION_REPOSITORY"):
    report["conversation_problems"] = len(editor.CONVERSATION_REPOSITORY.load_problems())
    report["labels"] = editor.ACTOR_LABELS
if {module!r} == "object_editor":
    report["placement_problems"] = len(editor.PLACEMENT_REPOSITORY.load_problems())
if {save}:
    data = editor.CONVERSATION_REPOSITORY.load_editable()
    data.append({{"weight": 1, "steps": [{{"type": "say", "speaker": "player", "text": "追加"}}]}})
    editor.CONVERSATION_REPOSITORY.save_editable(data)
print(json.dumps(report, ensure_ascii=False))
"""


def committed(name: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"HEAD:{name}"], cwd=ROOT, capture_output=True, check=True
    ).stdout


def run_probe(folder: Path, module: str, save: bool = False) -> dict:
    env = {
        **os.environ,
        "SDL_VIDEODRIVER": "dummy",
        "SDL_AUDIODRIVER": "dummy",
        "PYTHONIOENCODING": "utf-8",
    }
    result = subprocess.run(
        [sys.executable, "-c", PROBE.format(module=module, save=save)],
        cwd=folder,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr[-2000:])
    return json.loads(result.stdout.strip().splitlines()[-1])


class ManualCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.before = {name: (ROOT / name).read_bytes() for name in REAL_DATA}

    def tearDown(self) -> None:
        for name, data in self.before.items():
            self.assertEqual((ROOT / name).read_bytes(), data, f"{name} must not change")

    def scenario(self, scenario_id: str) -> kit.Scenario:
        return next(s for s in kit.SCENARIOS if s.id == scenario_id)

    def test_every_scenario_has_an_expectation_and_an_existing_editor(self) -> None:
        ids = [scenario.id for scenario in kit.SCENARIOS]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(EXPECTED))
        for scenario in kit.SCENARIOS:
            with self.subTest(scenario=scenario.id):
                self.assertTrue((ROOT / scenario.editor).is_file())
                self.assertTrue(scenario.steps)

    def test_copy_comes_from_head_and_only_the_copy_is_changed(self) -> None:
        folder = kit.prepare_check(self.scenario("conversation-load-errors"), ROOT, self.base)
        self.assertTrue(folder.is_relative_to(self.base))
        self.assertEqual((folder / "room.json").read_bytes(), committed("room.json"))
        deck = json.loads((folder / "conversations.json").read_text(encoding="utf-8"))
        original = json.loads(committed("conversations.json").decode("utf-8"))
        self.assertEqual(deck[: len(original)], original)
        self.assertEqual(len(deck), len(original) + 2)

    def test_each_scenario_shows_what_its_steps_describe(self) -> None:
        for scenario in kit.SCENARIOS:
            with self.subTest(scenario=scenario.id):
                folder = kit.prepare_check(scenario, ROOT, self.base)
                report = run_probe(folder, scenario.editor[:-3])
                for key, value in EXPECTED[scenario.id].items():
                    self.assertEqual(report[key], value, key)

    def test_saving_in_the_copy_writes_the_copy_not_the_project(self) -> None:
        folder = kit.prepare_check(self.scenario("conversation-generic-ids"), ROOT, self.base)
        before = (folder / "conversations.json").read_bytes()
        run_probe(folder, "conversation_editor", save=True)
        after = json.loads((folder / "conversations.json").read_text(encoding="utf-8"))
        self.assertNotEqual((folder / "conversations.json").read_bytes(), before)
        self.assertEqual(after[-1]["steps"][0]["text"], "追加")
        # tearDown asserts the project's own data files are unchanged.

    def test_same_scenario_can_be_opened_twice_quickly(self) -> None:
        scenario = self.scenario("object-load-errors")
        first = kit.prepare_check(scenario, ROOT, self.base)
        second = kit.prepare_check(scenario, ROOT, self.base)
        self.assertNotEqual(first, second)

    def test_failed_preparation_leaves_no_folder_and_explains_why(self) -> None:
        def fail(_folder: Path) -> None:
            raise kit.CheckError("この確認には配置が2件以上必要です")

        broken = kit.Scenario("broken", 0, "broken", "object_editor.py", fail, ())
        with self.assertRaisesRegex(kit.CheckError, "2件以上"):
            kit.prepare_check(broken, ROOT, self.base)
        self.assertEqual(list(self.base.iterdir()), [])

    def test_results_record_head_and_answers(self) -> None:
        scenario = kit.SCENARIOS[0]
        path = self.base / "results.json"
        answers = [("ok", "")] * (len(scenario.steps) - 1) + [("ng", "保存できなかった")]
        kit.save_results(path, scenario, None, answers, "abc123")
        kit.save_results(path, scenario, self.base, answers, "def456")
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(saved["checks"]), 2)
        first, last = saved["checks"]
        self.assertEqual((first["editor_opened"], last["editor_opened"]), (False, True))
        self.assertEqual(last["head"], "def456")
        self.assertEqual(last["steps"][-1], {**last["steps"][-1], "result": "ng"})
        self.assertEqual(last["steps"][-1]["note"], "保存できなかった")

    def test_work_root_never_falls_back_to_the_system_temp(self) -> None:
        with mock.patch.dict(os.environ, {"OBAKE_MANUAL_CHECK_DIR": str(self.base)}):
            self.assertEqual(kit.work_root(), self.base)
        env = {k: v for k, v in os.environ.items() if k != "OBAKE_MANUAL_CHECK_DIR"}
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch.object(kit, "PREFERRED_WORK_ROOT", self.base):
                self.assertEqual(kit.work_root(), self.base / "obake_manual_check")
            with mock.patch.object(kit, "PREFERRED_WORK_ROOT", self.base / "missing"):
                with self.assertRaisesRegex(kit.CheckError, "OBAKE_MANUAL_CHECK_DIR"):
                    kit.work_root()

    def test_window_saves_answers_and_guards_unsaved_switches(self) -> None:
        try:
            import tkinter as tk

            root = tk.Tk()
        except Exception as exc:  # noqa: BLE001 - no display in some environments
            self.skipTest(f"Tk display unavailable: {exc}")
        root.withdraw()
        self.addCleanup(root.destroy)
        window = kit.CheckWindow(root, ROOT, self.base)
        window.messagebox = mock.Mock()
        self.assertEqual(window.listbox.size(), len(kit.SCENARIOS))

        window.answers[0][0].set("ok")
        window.mark_changed()
        window.messagebox.askyesno.return_value = False
        window.listbox.selection_clear(0, "end")
        window.listbox.selection_set(1)
        window.on_select()
        self.assertIs(window.scenario, kit.SCENARIOS[0])

        window.messagebox.askyesno.return_value = True
        window.save()
        saved = json.loads((self.base / "results.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["checks"][0]["steps"][0]["result"], "ok")
        self.assertTrue(window.saved)


if __name__ == "__main__":
    unittest.main()
