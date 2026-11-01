"""Shared dark look for every Tk window, taken from the ghosts' room (Issue #132).

The colours come from ``room.json``: the night gradient (#080a14 to #0f121e),
the drifting motes (#92a0af), the ghosts' white, the spring's teal (#1d5664)
and the gold of the cursor marker. Windows call :func:`apply` before they
create widgets, and use the named styles below instead of hard-coded colours.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

BACKGROUND = "#0b0e19"
SURFACE = "#141a28"
RAISED = "#1d2536"
HOVER = "#27324a"
BORDER = "#2e384d"
TEXT = "#ebece5"
MUTED = "#92a0af"
# Disabled text is meant to recede: WCAG exempts it from 4.5:1, and it keeps 3:1.
DISABLED = "#5c6675"
SELECTION = "#1d5664"
ACCENT = "#6fc3bd"
GOLD = "#cac27e"

TITLE_FONT = ("Yu Gothic UI", 13, "bold")

# Named label styles: use these instead of foreground="#..." in windows.
MUTED_LABEL = "Muted.TLabel"
STATUS_LABEL = "Status.TLabel"
EXPECTED_LABEL = "Expected.TLabel"
TITLE_LABEL = "Title.TLabel"

# The transparent-cell checker of the pixel editor, dark to match the room.
CHECKER_LIGHT = "#323947"
CHECKER_DARK = "#262c38"
GRID_LINE = "#50545a"


def apply(root: tk.Misc) -> ttk.Style:
    """Give ``root`` and every widget created after this call the dark look."""
    root.configure(background=BACKGROUND)
    _set_tk_defaults(root)
    style = ttk.Style(root)
    # "clam" draws every part itself, so it honours colours on Windows too.
    style.theme_use("clam")
    style.configure(
        ".",
        background=BACKGROUND,
        foreground=TEXT,
        fieldbackground=SURFACE,
        bordercolor=BORDER,
        darkcolor=BACKGROUND,
        lightcolor=RAISED,
        troughcolor=SURFACE,
        selectbackground=SELECTION,
        selectforeground=TEXT,
        insertcolor=TEXT,
        focuscolor=ACCENT,
        arrowcolor=MUTED,
    )
    style.map(".", foreground=[("disabled", DISABLED)])
    # Paddings stay close to the platform theme so the editors' layouts still fit.
    style.configure("TButton", background=RAISED, padding=(8, 1))
    style.map(
        "TButton",
        background=[("disabled", BACKGROUND), ("pressed", SELECTION), ("active", HOVER)],
        bordercolor=[("focus", ACCENT)],
    )
    for field in ("TEntry", "TSpinbox", "TCombobox"):
        style.configure(field, foreground=TEXT, padding=1)
        # "disabled" comes first: a disabled read-only box must still look disabled.
        style.map(
            field,
            fieldbackground=[("disabled", BACKGROUND), ("readonly", RAISED)],
            foreground=[("disabled", DISABLED)],
            bordercolor=[("disabled", BORDER), ("focus", ACCENT)],
        )
    style.map("TCombobox", background=[("active", HOVER)])
    style.map("TSpinbox", background=[("active", HOVER)])
    for toggle in ("TCheckbutton", "TRadiobutton"):
        style.configure(toggle, indicatorbackground=SURFACE, indicatorforeground=ACCENT)
        style.map(
            toggle,
            background=[("active", BACKGROUND)],
            indicatorbackground=[("pressed", SELECTION), ("selected", SELECTION)],
        )
    style.configure("TScrollbar", background=RAISED, troughcolor=BACKGROUND)
    style.map("TScrollbar", background=[("active", HOVER)])
    style.configure("Horizontal.TScale", background=RAISED, troughcolor=SURFACE)
    style.map("Horizontal.TScale", background=[("active", HOVER)])
    style.configure("TSeparator", background=BORDER)
    style.configure("TLabelframe", background=BACKGROUND, bordercolor=BORDER)
    style.configure("TLabelframe.Label", background=BACKGROUND, foreground=MUTED)
    style.configure(MUTED_LABEL, foreground=MUTED)
    style.configure(STATUS_LABEL, foreground=GOLD)
    style.configure(EXPECTED_LABEL, foreground=ACCENT)
    style.configure(TITLE_LABEL, font=TITLE_FONT, foreground=TEXT)
    return style


def _set_tk_defaults(root: tk.Misc) -> None:
    """Defaults for classic tk widgets (lists, text, canvases, menus)."""
    options = {
        "*Listbox.background": SURFACE,
        "*Listbox.foreground": TEXT,
        "*Listbox.selectBackground": SELECTION,
        "*Listbox.selectForeground": TEXT,
        "*Listbox.highlightBackground": BORDER,
        "*Listbox.highlightColor": ACCENT,
        "*Listbox.highlightThickness": 1,
        "*Listbox.borderWidth": 0,
        "*Listbox.activeStyle": "none",
        "*Text.background": SURFACE,
        "*Text.foreground": TEXT,
        "*Text.insertBackground": TEXT,
        "*Text.selectBackground": SELECTION,
        "*Text.selectForeground": TEXT,
        "*Text.highlightBackground": BORDER,
        "*Text.highlightColor": ACCENT,
        "*Text.highlightThickness": 1,
        "*Text.borderWidth": 0,
        "*Canvas.background": BACKGROUND,
        "*Canvas.highlightBackground": BORDER,
        "*Button.background": RAISED,
        "*Button.foreground": TEXT,
        "*Button.activeBackground": HOVER,
        "*Button.activeForeground": TEXT,
        "*Menu.background": SURFACE,
        "*Menu.foreground": TEXT,
        "*Menu.activeBackground": SELECTION,
        "*Menu.activeForeground": TEXT,
        "*Menu.disabledForeground": DISABLED,
        "*TCombobox*Listbox.background": SURFACE,
        "*TCombobox*Listbox.foreground": TEXT,
        "*TCombobox*Listbox.selectBackground": SELECTION,
        "*TCombobox*Listbox.selectForeground": TEXT,
        "*Toplevel.background": BACKGROUND,
        # simpledialog (e.g. the new-project name prompt) builds classic widgets.
        "*Frame.background": BACKGROUND,
        "*Label.background": BACKGROUND,
        "*Label.foreground": TEXT,
        "*Entry.background": SURFACE,
        "*Entry.foreground": TEXT,
        "*Entry.insertBackground": TEXT,
        "*Entry.selectBackground": SELECTION,
        "*Entry.selectForeground": TEXT,
        "*Entry.disabledBackground": BACKGROUND,
        "*Entry.disabledForeground": DISABLED,
        "*Entry.highlightBackground": BORDER,
        "*Entry.highlightColor": ACCENT,
    }
    for pattern, value in options.items():
        root.option_add(pattern, value)


def readable_text(background: str) -> str:
    """Text colour that reads at 4.5:1 or better on ``background``.

    Prefers the theme's own white and black; for mid greys where neither
    reaches 4.5:1, pure white or black does (one of them always does).
    """
    candidates = sorted(
        (TEXT, BACKGROUND), key=lambda colour: contrast_ratio(colour, background), reverse=True
    )
    candidates += sorted(
        ("#ffffff", "#000000"),
        key=lambda colour: contrast_ratio(colour, background),
        reverse=True,
    )
    return next(c for c in candidates if contrast_ratio(c, background) >= 4.5)


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio between two ``#rrggbb`` colours."""
    lighter, darker = sorted(
        (relative_luminance(foreground), relative_luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def relative_luminance(color: str) -> float:
    """WCAG relative luminance of a ``#rrggbb`` colour (the only form used here)."""
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]
