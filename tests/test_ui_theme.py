"""Every Tk window uses the dark ghost-room theme (Issue #132)."""

import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import ttk
from unittest import mock

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

import character_editor
import conversation_editor
import object_editor
from engine import ui_theme
from engine.main_window import MainWindow
from engine.manifest_loader import load_project_manifest
from engine.process_launcher import ProcessLauncher
from tools.manual_check.script import manual_check

# Anything brighter than this is not "black-based".
DARK_LUMINANCE = 0.05


def all_widgets(widget: tk.Misc):
    yield widget
    for child in widget.winfo_children():
        yield from all_widgets(child)


class PaletteTests(unittest.TestCase):
    def test_text_colours_are_readable_on_their_backgrounds(self) -> None:
        pairs = {
            "text on window": (ui_theme.TEXT, ui_theme.BACKGROUND),
            "text in fields": (ui_theme.TEXT, ui_theme.SURFACE),
            "text on buttons": (ui_theme.TEXT, ui_theme.RAISED),
            "text on hover": (ui_theme.TEXT, ui_theme.HOVER),
            "selected text": (ui_theme.TEXT, ui_theme.SELECTION),
            "muted text": (ui_theme.MUTED, ui_theme.BACKGROUND),
            "status text": (ui_theme.GOLD, ui_theme.BACKGROUND),
            "expected text": (ui_theme.ACCENT, ui_theme.BACKGROUND),
        }
        for name, (foreground, background) in pairs.items():
            with self.subTest(name):
                self.assertGreaterEqual(ui_theme.contrast_ratio(foreground, background), 4.5)

    def test_backgrounds_are_dark(self) -> None:
        for colour in (ui_theme.BACKGROUND, ui_theme.SURFACE, ui_theme.RAISED):
            self.assertLess(ui_theme.relative_luminance(colour), DARK_LUMINANCE, colour)

    def test_colour_button_text_follows_the_chosen_colour(self) -> None:
        self.assertEqual(ui_theme.readable_text("#ffffff"), ui_theme.BACKGROUND)
        self.assertEqual(ui_theme.readable_text("#e8e4d4"), ui_theme.BACKGROUND)
        self.assertEqual(ui_theme.readable_text("#000000"), ui_theme.TEXT)
        self.assertEqual(ui_theme.readable_text("#1d5664"), ui_theme.TEXT)


class WindowThemeTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    def assert_dark(self, window_root: tk.Misc, skip: tuple[tk.Misc, ...] = ()) -> None:
        window_root.update_idletasks()
        style = ttk.Style(window_root)
        self.assertEqual(style.theme_use(), "clam")
        checked = 0
        for widget in all_widgets(window_root):
            if widget in skip:
                continue
            with self.subTest(widget=str(widget)):
                if isinstance(widget, ttk.Widget):
                    name = str(widget.cget("style")) or widget.winfo_class()
                    background = style.lookup(name, "background") or style.lookup(".", "background")
                    if isinstance(widget, ttk.Label):
                        # Colours come from the named styles, not hard-coded values.
                        self.assertEqual(str(widget.cget("foreground")), "")
                else:
                    background = str(widget.cget("background"))
                rgb = widget.winfo_rgb(background)
                colour = "#" + "".join(f"{channel >> 8:02x}" for channel in rgb)
                self.assertLess(ui_theme.relative_luminance(colour), DARK_LUMINANCE, background)
                checked += 1
        self.assertGreater(checked, 10)

    def test_disabled_fields_look_disabled(self) -> None:
        style = ui_theme.apply(self.root)
        for field in ("TCombobox", "TEntry", "TSpinbox"):
            with self.subTest(field):
                disabled = ["disabled", "readonly"]
                self.assertEqual(style.lookup(field, "foreground", disabled), ui_theme.DISABLED)
                self.assertEqual(
                    style.lookup(field, "fieldbackground", disabled), ui_theme.BACKGROUND
                )
                self.assertEqual(
                    style.lookup(field, "fieldbackground", ["readonly"]), ui_theme.RAISED
                )

    def test_main_window(self) -> None:
        manifest = load_project_manifest(PROJECT_DIR / "engine_project.json")
        MainWindow(self.root, manifest, ProcessLauncher(manifest))
        self.assert_dark(self.root)

    def test_object_editor(self) -> None:
        with mock.patch.object(object_editor, "messagebox"):
            editor = object_editor.ObjectEditor(self.root)
        # The colour button shows the chosen paint colour on purpose.
        self.assert_dark(self.root, skip=(editor.color_button,))
        self.assertEqual(str(editor.color_button.cget("fg")), ui_theme.readable_text(editor.color))

    def test_conversation_editor(self) -> None:
        with mock.patch.object(conversation_editor, "messagebox"):
            conversation_editor.ConversationEditor(self.root)
        self.assert_dark(self.root)

    def test_character_editor(self) -> None:
        with mock.patch.object(character_editor, "messagebox"):
            character_editor.CharacterEditor(self.root)
        self.assert_dark(self.root)

    def test_manual_check_window(self) -> None:
        with tempfile.TemporaryDirectory() as base:
            manual_check.CheckWindow(self.root, PROJECT_DIR, Path(base))
            self.assert_dark(self.root)


if __name__ == "__main__":
    unittest.main()
