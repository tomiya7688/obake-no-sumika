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
REAL_DATA = ("characters.json", "conversations.json", "events.json", "placed_objects.json")


def committed(name: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"HEAD:{name}"], cwd=ROOT, capture_output=True, check=True
    ).stdout


class ManualCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.before = {name: (ROOT / name).read_bytes() for name in REAL_DATA}

    def tearDown(self) -> None:
        for name, data in self.before.items():
            self.assertEqual((ROOT / name).read_bytes(), data, f"{name} must not change")

    def test_scenarios_name_existing_editors_and_unique_ids(self) -> None:
        ids = [scenario.id for scenario in kit.SCENARIOS]
        self.assertEqual(len(ids), len(set(ids)))
        for scenario in kit.SCENARIOS:
            with self.subTest(scenario=scenario.id):
                self.assertTrue((ROOT / scenario.editor).is_file())
                self.assertTrue(scenario.steps)

    def test_copy_comes_from_head_and_only_the_copy_is_changed(self) -> None:
        scenario = next(s for s in kit.SCENARIOS if s.id == "conversation-load-errors")
        folder = kit.prepare_check(scenario, ROOT, self.base)
        self.assertTrue(folder.is_relative_to(self.base))
        self.assertEqual((folder / "room.json").read_bytes(), committed("room.json"))
        deck = json.loads((folder / "conversations.json").read_text(encoding="utf-8"))
        original = json.loads(committed("conversations.json").decode("utf-8"))
        self.assertEqual(deck[: len(original)], original)
        self.assertEqual(len(deck), len(original) + 2)

    def test_each_scenario_produces_the_problems_its_steps_describe(self) -> None:
        for scenario in kit.SCENARIOS:
            with self.subTest(scenario=scenario.id):
                folder = kit.prepare_check(scenario, ROOT, self.base / scenario.id)
                probe = (
                    "import sys, json\n"
                    "sys.path.insert(0, '.')\n"
                    "from unittest import mock\n"
                    "import tkinter\n"
                    f"import {scenario.editor[:-3]} as editor\n"
                    "problems = []\n"
                    "for name in ('CONVERSATION_REPOSITORY', 'PLACEMENT_REPOSITORY'):\n"
                    "    repo = getattr(editor, name, None)\n"
                    "    if repo is not None and hasattr(repo, 'load_problems'):\n"
                    "        problems += repo.load_problems()\n"
                    "print(json.dumps({'problems': problems,"
                    " 'labels': getattr(editor, 'ACTOR_LABELS', {})}))\n"
                )
                env = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
                result = subprocess.run(
                    [sys.executable, "-c", probe],
                    cwd=folder,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                self.assertEqual(result.returncode, 0, result.stderr[-2000:])
                report = json.loads(result.stdout.strip().splitlines()[-1])
                if scenario.id == "conversation-generic-ids":
                    self.assertEqual(report["labels"], {"player": "プレイヤー"})
                    self.assertEqual(report["problems"], [])
                elif scenario.id == "object-load-errors":
                    problems = [p for p in report["problems"] if p.startswith("配置")]
                    self.assertEqual(len(problems), 2)
                else:
                    problems = [p for p in report["problems"] if p.startswith("会話")]
                    self.assertEqual(len(problems), 2)

    def test_results_are_appended_for_agents_to_read(self) -> None:
        scenario = kit.SCENARIOS[0]
        path = self.base / "results.json"
        answers = [("ok", "")] * (len(scenario.steps) - 1) + [("ng", "保存できなかった")]
        kit.save_results(path, scenario, None, answers)
        kit.save_results(path, scenario, self.base, answers)
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(saved["checks"]), 2)
        last = saved["checks"][-1]
        self.assertEqual((last["scenario"], last["issue"]), (scenario.id, scenario.issue))
        self.assertEqual(last["steps"][-1]["result"], "ng")
        self.assertEqual(last["steps"][-1]["note"], "保存できなかった")

    def test_work_root_prefers_setting_then_e_drive(self) -> None:
        with mock.patch.dict(os.environ, {"OBAKE_MANUAL_CHECK_DIR": str(self.base)}):
            self.assertEqual(kit.work_root(), self.base)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("OBAKE_MANUAL_CHECK_DIR", None)
            with mock.patch.object(kit, "PREFERRED_WORK_ROOT", self.base):
                self.assertEqual(kit.work_root(), self.base / "obake_manual_check")

    def test_window_lists_every_scenario(self) -> None:
        try:
            import tkinter as tk

            root = tk.Tk()
        except Exception as exc:  # noqa: BLE001 - no display in some environments
            self.skipTest(f"Tk display unavailable: {exc}")
        root.withdraw()
        self.addCleanup(root.destroy)
        window = kit.CheckWindow(root, ROOT, self.base)
        self.assertEqual(window.listbox.size(), len(kit.SCENARIOS))
        self.assertEqual(len(window.answers), len(kit.SCENARIOS[0].steps))
        window.answers[0][0].set("ok")
        window.save()
        saved = json.loads((self.base / "results.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["checks"][0]["steps"][0]["result"], "ok")


if __name__ == "__main__":
    unittest.main()
