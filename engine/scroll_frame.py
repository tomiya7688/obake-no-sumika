"""A frame that scrolls when its window is too small for it (Issue #131).

Put the window's content in ``ScrollFrame.body``. While the window is big
enough the body fills it exactly as a plain frame would and no scroll bar is
shown; when it is shorter or narrower, the scroll bar appears (vertical, and
horizontal with Shift+wheel) so every control stays reachable at any size.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# Widgets that scroll or change a value with the wheel themselves.
WHEEL_OWNERS = frozenset({"Listbox", "Text", "TCombobox", "TSpinbox", "TScale", "Scale"})
SHIFT_MASK = 0x1
CONTROL_MASK = 0x4


class ScrollFrame(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.hscrollbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=self._set_yscroll, xscrollcommand=self._set_xscroll)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self._shown = {"v": False, "h": False}
        self.body = ttk.Frame(self.canvas)
        self._window = self.canvas.create_window((0, 0), window=self.body, anchor="nw")
        self.body.bind("<Configure>", self._body_changed)
        self.canvas.bind("<Configure>", self._canvas_changed)
        # Bind on this window only (not bind_all): every widget in it passes through
        # its toplevel, other windows are untouched, and nothing outlives the window.
        # X11 reports the wheel as buttons 4 and 5 instead of <MouseWheel>.
        window = self.winfo_toplevel()
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            window.bind(sequence, self._on_wheel, add="+")

    @property
    def scrollbar_visible(self) -> bool:
        return self._shown["v"]

    @property
    def hscrollbar_visible(self) -> bool:
        return self._shown["h"]

    def _body_changed(self, _event: tk.Event) -> None:
        self._fit_body(self.canvas.winfo_width(), self.canvas.winfo_height())

    def _canvas_changed(self, event: tk.Event) -> None:
        self._fit_body(event.width, event.height)

    def _fit_body(self, canvas_width: int, canvas_height: int) -> None:
        # The body is at least as big as the window, so its rows keep expanding.
        width = max(self.body.winfo_reqwidth(), canvas_width)
        height = max(self.body.winfo_reqheight(), canvas_height)
        self.canvas.itemconfigure(self._window, width=width, height=height)
        self.canvas.configure(scrollregion=(0, 0, width, height))

    def _toggle(self, key: str, bar: ttk.Scrollbar, first: str, last: str, **grid) -> None:
        bar.set(first, last)
        needed = not (float(first) <= 0 and float(last) >= 1)
        if needed == self._shown[key]:
            return
        self._shown[key] = needed
        if needed:
            bar.grid(**grid)
        else:
            bar.grid_remove()

    def _set_yscroll(self, first: str, last: str) -> None:
        self._toggle("v", self.scrollbar, first, last, row=0, column=1, sticky="ns")

    def _set_xscroll(self, first: str, last: str) -> None:
        self._toggle("h", self.hscrollbar, first, last, row=1, column=0, sticky="ew")

    def _on_wheel(self, event: tk.Event) -> None:
        widget = event.widget
        if not isinstance(widget, tk.Misc):
            return
        try:
            if not self.winfo_exists():
                return  # the frame is gone but the window's binding is still there
            if widget.winfo_class() in WHEEL_OWNERS or event.state & CONTROL_MASK:
                return  # a list, text box or Ctrl+wheel zoom keeps its own wheel
        except tk.TclError:
            return
        number = getattr(event, "num", 0)
        up = number == 4 if number in (4, 5) else event.delta > 0
        step = -1 if up else 1
        if event.state & SHIFT_MASK and self.hscrollbar_visible:
            self.canvas.xview_scroll(step, "units")
        elif self.scrollbar_visible:
            self.canvas.yview_scroll(step, "units")
