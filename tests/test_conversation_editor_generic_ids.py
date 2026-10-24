"""The conversation editor must work for projects without kadoka / water_bath."""

import json
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

import conversation_editor
from engine.conversation_repository import ConversationRepository


def character(character_id: str, name: str) -> SimpleNamespace:
    return SimpleNamespace(id=character_id, display_name=name)


class ConversationEditorGenericIdTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.deck_path = Path(self.temp_dir.name) / "conversations.json"
        self.deck_path.write_text(
            json.dumps([{"weight": 1, "steps": [
                {"type": "say", "speaker": "player", "text": "やあ"},
                {"type": "event", "event": "idle"},
            ]}]),
            encoding="utf-8",
        )
        labels = conversation_editor.actor_labels([character("player", "プレイヤー")])
        repository = ConversationRepository(self.deck_path, ("player",), tuple(labels), ("idle",))
        patches = {
            "SPEAKER_IDS": ("player",),
            "DEFAULT_SPEAKER": "player",
            "ACTOR_LABELS": labels,
            "ACTOR_VALUES": {label: value for value, label in labels.items()},
            "EVENT_LABELS": {"idle": "待機"},
            "EVENT_VALUES": {"待機": "idle"},
            "DEFAULT_EVENT": "idle",
            "CONVERSATION_REPOSITORY": repository,
        }
        for name, value in patches.items():
            patcher = mock.patch.object(conversation_editor, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        tags = mock.patch.object(conversation_editor.PLACEMENT_REPOSITORY, "tags", return_value=[])
        tags.start()
        self.addCleanup(tags.stop)
        # A real modal dialog would block a headless run forever; record it instead.
        dialogs = mock.patch.object(conversation_editor, "messagebox")
        self.messagebox = dialogs.start()
        self.addCleanup(dialogs.stop)

    def test_shared_actor_is_offered_only_for_two_or_more_characters(self) -> None:
        self.assertEqual(conversation_editor.actor_labels([character("player", "P")]), {"player": "P"})
        self.assertEqual(
            conversation_editor.actor_labels([character("a", "A"), character("b", "B")])["both"], "ふたり"
        )
        three = [character("a", "A"), character("b", "B"), character("c", "C")]
        self.assertEqual(conversation_editor.actor_labels(three)["both"], "全員")

    def test_editor_starts_edits_and_saves_with_generic_ids(self) -> None:
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        root.withdraw()
        self.addCleanup(root.destroy)
        editor = conversation_editor.ConversationEditor(root)
        self.assertEqual(editor.actor_var.get(), "プレイヤー")
        self.assertEqual(editor.event_var.get(), "待機")

        editor.show_step(1)
        self.assertEqual(editor.build_current_step(), {"type": "event", "event": "idle"})
        editor.show_step(0)
        self.assertEqual(
            editor.build_current_step(), {"type": "say", "speaker": "player", "text": "やあ"}
        )

        editor.add_step()
        editor.add_conversation()
        self.assertEqual(editor.data[-1]["steps"], [{"type": "say", "speaker": "player", "text": "新しいセリフ"}])
        self.assertTrue(editor.save(), self.messagebox.mock_calls)
        self.assertEqual(self.messagebox.mock_calls, [])

        saved = json.loads(self.deck_path.read_text(encoding="utf-8"))
        self.assertEqual(len(saved), 2)
        self.assertEqual(saved[0]["steps"][1], {"type": "say", "speaker": "player", "text": "つづき"})
        self.assertEqual(saved[0]["steps"][-1], {"type": "event", "event": "idle"})


if __name__ == "__main__":
    unittest.main()
