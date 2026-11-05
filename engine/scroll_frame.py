"""A frame that scrolls vertically when its window is too short (Issue #131).

Put the window's content in ``ScrollFrame.body``. While the window is tall
enough the body fills it exactly as a plain frame would and no scroll bar is
shown; when it is shorter, the scroll bar appears and the mouse wheel scrolls,
so every control stays reachable at any window size.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# Widgets that scroll or change a value with the wheel themselves.
WHEEL_OWNERS = frozenset({"Listbox", "Text", "TCombobox", "TSpinbox", "TScale", "Scale"})
CONTROL_MASK = 0x4


class ScrollFrame(ttk.Frame):
    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._set_scroll)
        self.canvas.pack(side="left", fill="both", expand=True)
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
        return bool(self.scrollbar.winfo_manager())

    def _body_changed(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=(0, 0, self.body.winfo_reqwidth(), self._body_height()))
        self._fit_body(self.canvas.winfo_height())

    def _canvas_changed(self, event: tk.Event) -> None:
        self._fit_body(event.height, event.width)

    def _body_height(self) -> int:
        return max(self.body.winfo_reqheight(), self.canvas.winfo_height())

    def _fit_body(self, canvas_height: int, canvas_width: int | None = None) -> None:
        # The body is at least as tall as the window, so its rows keep expanding.
        height = max(self.body.winfo_reqheight(), canvas_height)
        options = {"height": height}
        if canvas_width is not None:
            options["width"] = canvas_width
        self.canvas.itemconfigure(self._window, **options)
        self.canvas.configure(scrollregion=(0, 0, self.body.winfo_reqwidth(), height))

    def _set_scroll(self, first: str, last: str) -> None:
        self.scrollbar.set(first, last)
        if float(first) <= 0 and float(last) >= 1:
            if self.scrollbar_visible:
                self.scrollbar.pack_forget()
        elif not self.scrollbar_visible:
            self.scrollbar.pack(side="right", fill="y")

    def _on_wheel(self, event: tk.Event) -> None:
        widget = event.widget
        if not isinstance(widget, tk.Misc):
            return
        try:
            if not self.winfo_exists():
                return  # the frame is gone but the window's binding is still there
            if widget.winfo_class() in WHEEL_OWNERS or event.state & CONTROL_MASK:
                return  # a list, text box or Ctrl+wheel zoom keeps its own wheel
            if not self.scrollbar_visible:
                return
        except tk.TclError:
            return
        number = getattr(event, "num", 0)
        up = number == 4 if number in (4, 5) else event.delta > 0
        self.canvas.yview_scroll(-1 if up else 1, "units")
