"""The object editor stays usable when its window is shorter than its panels (Issue #131)."""

import sys
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from types import SimpleNamespace
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

import object_editor
from engine.scroll_frame import ScrollFrame

LIBRARY_BUTTON = "選択した画像を住処に挿入"


def find_button(widget: tk.Misc, text: str):
    if isinstance(widget, ttk.Button) and str(widget.cget("text")) == text:
        return widget
    for child in widget.winfo_children():
        found = find_button(child, text)
        if found is not None:
            return found
    return None


class ObjectEditorScrollTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.addCleanup(self.root.destroy)
        # A real modal dialog would block a headless run forever.
        with mock.patch.object(object_editor, "messagebox"):
            self.editor = object_editor.ObjectEditor(self.root)
        self.area = self.editor.scroll_area

    def resize(self, width: int, height: int) -> None:
        self.root.geometry(f"{width}x{height}")
        self.root.update()

    def visible_in_canvas(self, widget: tk.Misc) -> bool:
        canvas = self.area.canvas
        top = widget.winfo_rooty()
        bottom = top + widget.winfo_height()
        return (
            canvas.winfo_rooty() <= top and bottom <= canvas.winfo_rooty() + canvas.winfo_height()
        )

    def test_bottom_controls_are_reachable_at_the_minimum_size(self) -> None:
        min_width, min_height = self.root.minsize()
        button = find_button(self.root, LIBRARY_BUTTON)
        self.assertIsNotNone(button)
        for width, height in ((1380, 860), (min_width, min_height), (min_width, 400)):
            with self.subTest(size=f"{width}x{height}"):
                self.resize(width, height)
                self.area.canvas.yview_moveto(1.0)
                self.root.update()
                self.assertTrue(self.visible_in_canvas(button))
                self.area.canvas.yview_moveto(0.0)
                self.root.update()

    def test_scroll_bar_appears_only_when_the_window_is_too_short(self) -> None:
        self.resize(1380, 1400)
        self.assertFalse(self.area.scrollbar_visible)
        self.resize(1160, 400)
        self.assertTrue(self.area.scrollbar_visible)
        self.resize(1380, 1400)
        self.assertFalse(self.area.scrollbar_visible)

    def test_wheel_scrolls_the_panels_but_not_lists_or_ctrl_zoom(self) -> None:
        self.resize(1160, 400)
        canvas = self.area.canvas

        def wheel(widget, delta=-120, state=0):
            self.area._on_wheel(SimpleNamespace(widget=widget, delta=delta, state=state))
            self.root.update()

        wheel(self.editor.scroll_area.body)
        scrolled = canvas.yview()[0]
        self.assertGreater(scrolled, 0)
        wheel(self.editor.placement_list)  # lists scroll themselves
        wheel(self.editor.scroll_area.body, state=0x4)  # Ctrl+wheel is the zoom
        self.assertEqual(canvas.yview()[0], scrolled)
        wheel(self.editor.scroll_area.body, delta=120)
        self.assertLess(canvas.yview()[0], scrolled)

    def test_body_fills_the_window_when_it_is_tall_enough(self) -> None:
        frame = ScrollFrame(self.root)
        child = ttk.Frame(frame.body, height=50)
        child.pack(fill="both", expand=True)
        frame.pack(fill="both", expand=True)
        self.resize(900, 700)
        self.assertGreaterEqual(frame.body.winfo_width(), frame.canvas.winfo_width())
        self.assertGreaterEqual(frame.body.winfo_height(), frame.canvas.winfo_height())


if __name__ == "__main__":
    unittest.main()
