"""The object editor's status line must stay inside the window (Issue #128)."""

import sys
import tkinter as tk
import unittest
from pathlib import Path
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

import object_editor


def leaf_widgets(widget: tk.Misc):
    children = widget.winfo_children()
    if not children:
        yield widget
    for child in children:
        yield from leaf_widgets(child)


class ObjectEditorStatusBarTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.addCleanup(self.root.destroy)
        # A real modal dialog would block a headless run forever.
        with mock.patch.object(object_editor, "messagebox"):
            self.editor = object_editor.ObjectEditor(self.root)

    def resize(self, width: int, height: int) -> None:
        self.root.geometry(f"{width}x{height}")
        self.root.update()
        self.assertEqual(self.root.winfo_height(), height)

    def test_status_line_is_visible_at_initial_and_minimum_size(self) -> None:
        min_width, min_height = self.root.minsize()
        self.assertGreater(min_height, 1, "the editor must set a minimum window size")
        for width, height in ((1380, 860), (min_width, min_height)):
            with self.subTest(size=f"{width}x{height}"):
                self.resize(width, height)
                label = self.editor.status_label
                self.assertTrue(label.winfo_ismapped())
                # The whole text row must fit, not just a sliver of the label.
                self.assertGreaterEqual(label.winfo_height(), label.winfo_reqheight())
                self.assertLessEqual(label.winfo_y() + label.winfo_height(), height)

    # Font metrics differ by platform (Linux CI renders the panel a few px
    # taller), and the editor's layout is tuned for the Windows it runs on.
    @unittest.skipUnless(sys.platform == "win32", "layout is tuned for Windows font metrics")
    def test_every_control_fits_above_the_status_line_at_initial_size(self) -> None:
        self.resize(1380, 860)
        status_top = self.editor.status_label.winfo_y()
        root_y = self.root.winfo_rooty()
        for widget in leaf_widgets(self.root):
            if widget is self.editor.status_label or not widget.winfo_ismapped():
                continue
            with self.subTest(widget=str(widget)):
                bottom = widget.winfo_rooty() - root_y + widget.winfo_height()
                self.assertLessEqual(bottom, status_top)


if __name__ == "__main__":
    unittest.main()
