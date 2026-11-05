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


def all_buttons(widget: tk.Misc):
    if isinstance(widget, ttk.Button):
        yield widget
    for child in widget.winfo_children():
        yield from all_buttons(child)


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
        left = widget.winfo_rootx()
        right = left + widget.winfo_width()
        return (
            canvas.winfo_rooty() <= top
            and bottom <= canvas.winfo_rooty() + canvas.winfo_height()
            and canvas.winfo_rootx() <= left
            and right <= canvas.winfo_rootx() + canvas.winfo_width()
        )

    def reachable(self, widget: tk.Misc) -> bool:
        """Can the widget be shown completely by scrolling to some corner?"""
        for x in (0.0, 1.0):
            for y in (0.0, 1.0):
                self.area.canvas.xview_moveto(x)
                self.area.canvas.yview_moveto(y)
                self.root.update()
                if self.visible_in_canvas(widget):
                    return True
        return False

    def test_every_button_is_reachable_at_the_minimum_size(self) -> None:
        min_width, min_height = self.root.minsize()
        for width, height in ((1380, 860), (min_width, min_height), (min_width, 400)):
            self.resize(width, height)
            for button in all_buttons(self.root):
                with self.subTest(size=f"{width}x{height}", button=str(button.cget("text"))):
                    self.assertTrue(self.reachable(button))

    def test_horizontal_scroll_bar_appears_only_when_the_window_is_too_narrow(self) -> None:
        self.resize(1500, 900)
        self.assertFalse(self.area.hscrollbar_visible)
        self.resize(1100, 900)
        self.assertTrue(self.area.hscrollbar_visible)
        self.resize(1500, 900)
        self.assertFalse(self.area.hscrollbar_visible)

    def test_shift_wheel_scrolls_sideways(self) -> None:
        self.resize(1100, 900)
        canvas = self.area.canvas
        event = SimpleNamespace(widget=self.area.body, delta=-120, state=0x1, num=0)
        self.area._on_wheel(event)
        self.root.update()
        self.assertGreater(canvas.xview()[0], 0)
        self.assertEqual(canvas.yview()[0], 0.0)

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

        def wheel(widget, delta=0, state=0, num=0):
            self.area._on_wheel(SimpleNamespace(widget=widget, delta=delta, state=state, num=num))
            self.root.update()

        body = self.editor.scroll_area.body
        wheel(body, delta=-120)  # Windows / macOS: wheel down
        scrolled = canvas.yview()[0]
        self.assertGreater(scrolled, 0)
        wheel(self.editor.placement_list, delta=-120)  # lists scroll themselves
        wheel(body, delta=-120, state=0x4)  # Ctrl+wheel is the zoom
        self.assertEqual(canvas.yview()[0], scrolled)
        wheel(body, delta=120)  # wheel up
        self.assertLess(canvas.yview()[0], scrolled)
        canvas.yview_moveto(0.0)
        wheel(body, num=5)  # X11: button 5 is wheel down
        self.assertGreater(canvas.yview()[0], 0)
        wheel(body, num=4)  # X11: button 4 is wheel up
        self.assertEqual(canvas.yview()[0], 0.0)

    def test_the_wheel_is_bound_to_its_own_window_only(self) -> None:
        # Not bind_all: a second window must not have our handler, and a frame
        # that has been destroyed must ignore wheel events that still arrive.
        other = tk.Toplevel(self.root)
        self.addCleanup(other.destroy)
        self.assertEqual(other.bind("<MouseWheel>"), "")
        self.assertNotEqual(self.root.bind("<MouseWheel>"), "")
        self.resize(1160, 400)
        gone = self.editor.scroll_area
        event = SimpleNamespace(widget=gone.body, delta=-120, state=0, num=0)
        gone.destroy()
        gone._on_wheel(event)  # must not raise

    def test_body_fills_the_window_when_it_is_tall_enough(self) -> None:
        window = tk.Toplevel(self.root)
        self.addCleanup(window.destroy)
        window.geometry("900x700")
        frame = ScrollFrame(window)
        child = ttk.Frame(frame.body, height=50)
        child.pack(fill="both", expand=True)
        frame.pack(fill="both", expand=True)
        window.update()
        self.assertGreaterEqual(frame.body.winfo_width(), frame.canvas.winfo_width())
        self.assertGreaterEqual(frame.body.winfo_height(), frame.canvas.winfo_height())
        self.assertFalse(frame.scrollbar_visible)


if __name__ == "__main__":
    unittest.main()
