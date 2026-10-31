"""The object editor's status line must stay inside the window (Issue #128)."""

import sys
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

import object_editor


class ObjectEditorStatusBarTests(unittest.TestCase):
    def test_status_line_is_visible_at_initial_and_minimum_size(self) -> None:
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.addCleanup(root.destroy)
        # A real modal dialog would block a headless run forever.
        with mock.patch.object(object_editor, "messagebox"):
            editor = object_editor.ObjectEditor(root)
        width, height = root.minsize()
        for size in ("1380x860", f"{width}x{height}"):
            with self.subTest(size=size):
                root.geometry(size)
                root.update()
                label = editor.status_label
                self.assertTrue(label.winfo_ismapped())
                self.assertGreater(label.winfo_height(), 1)
                self.assertLessEqual(label.winfo_y() + label.winfo_height(), root.winfo_height())


if __name__ == "__main__":
    unittest.main()
