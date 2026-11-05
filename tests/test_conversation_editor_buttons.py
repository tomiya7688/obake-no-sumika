"""The conversation editor's button rows must fit their columns (Issue #133)."""

import sys
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

import conversation_editor


def buttons(widget: tk.Misc):
    if isinstance(widget, ttk.Button):
        yield widget
    for child in widget.winfo_children():
        yield from buttons(child)


class ConversationEditorButtonTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.addCleanup(self.root.destroy)
        # A real modal dialog would block a headless run forever.
        with mock.patch.object(conversation_editor, "messagebox"):
            self.editor = conversation_editor.ConversationEditor(self.root)

    def test_save_button_survives_a_long_status_message(self) -> None:
        min_width, min_height = self.root.minsize()
        self.root.geometry(f"{min_width}x{min_height}")
        self.editor.status_var.set("保存しました。次回ゲーム起動時から反映されます。" * 3)
        self.root.update()
        save = next(b for b in buttons(self.root) if str(b.cget("text")) == "JSONへ保存")
        self.assertTrue(save.winfo_ismapped())
        self.assertGreaterEqual(save.winfo_width(), save.winfo_reqwidth())

    def test_every_button_is_fully_visible_at_initial_and_minimum_size(self) -> None:
        min_width, min_height = self.root.minsize()
        self.assertGreater(min_width, 1, "the editor must set a minimum window size")
        # Explicit sizes first: a size below the minimum is raised to it by Tk,
        # so the minimum itself is checked as well.
        for width, height in ((1180, 680), (960, 560), (min_width, min_height)):
            self.root.geometry(f"{width}x{height}")
            self.root.update()
            self.assertGreaterEqual(self.root.winfo_width(), min(width, min_width))
            all_buttons = list(buttons(self.root))
            self.assertGreaterEqual(len(all_buttons), 9)  # 4 + 4 + save
            for button in all_buttons:
                with self.subTest(size=f"{width}x{height}", button=str(button.cget("text"))):
                    self.assertTrue(button.winfo_ismapped())
                    self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth())
                    self.assertGreaterEqual(button.winfo_height(), button.winfo_reqheight())
                    right = button.winfo_rootx() - self.root.winfo_rootx() + button.winfo_width()
                    self.assertLessEqual(right, self.root.winfo_width())


if __name__ == "__main__":
    unittest.main()
