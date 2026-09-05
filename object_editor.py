"""Pixel object editor and habitat placement tool for Obake no Sumika."""

from __future__ import annotations

import tkinter as tk
import uuid
from pathlib import Path
from tkinter import colorchooser, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk

from engine.pixel_object_repository import PixelObjectRepository
from engine.placement_repository import PlacementRepository, normalize_tag
from engine.room_repository import RoomRepository


PROJECT_DIR = Path(__file__).resolve().parent
OBJECT_DIR = PROJECT_DIR / "objects"
PLACEMENTS_PATH = PROJECT_DIR / "placed_objects.json"
PREVIEW_PATH = PROJECT_DIR / "assets" / "editor_cave_preview.png"
ROOM_PATH = PROJECT_DIR / "room.json"
ROOM = RoomRepository(ROOM_PATH).load()
GAME_SIZE = (ROOM.width, ROOM.height)
PREVIEW_SIZE = (480, round(480 * ROOM.height / ROOM.width))
EDITOR_PIXELS = 512
CANVAS_SIZES = (16, 32, 64, 128)
EXPORT_SIZE = 1024
PLACEMENT_REPOSITORY = PlacementRepository(
    PROJECT_DIR,
    PLACEMENTS_PATH,
    (ROOM.width, ROOM.height),
)
PIXEL_OBJECT_REPOSITORY = PixelObjectRepository(
    PROJECT_DIR,
    OBJECT_DIR,
    CANVAS_SIZES,
    EXPORT_SIZE,
)
BUILTIN_LIBRARY = {
    "spring": ("湧き水", 204),
    "small_rock": ("小さな岩", 42),
    "large_rock": ("大きな岩", 72),
    "gray_found_item": ("灰色の拾い物", 24),
    "game_device": ("ゲーム機", 32),
}


class ObjectEditor:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("おばけの住処　オブジェクトエディター")
        self.root.geometry("1380x860")
        self.root.minsize(1160, 720)

        self.canvas_size = 32
        self.pixels: list[list[str | None]] = self.blank_pixels(self.canvas_size)
        self.undo_stack: list[list[list[str | None]]] = []
        self.color = "#e8e4d4"
        self.tool = "pencil"
        self.painting = False
        self.last_cell: tuple[int, int] | None = None
        self.placements = PLACEMENT_REPOSITORY.load_editable()
        self.selected_placement: int | None = None
        self.drag_offset = (0, 0)
        self.dragging_placement = False
        self.preview_photo: ImageTk.PhotoImage | None = None
        self.preview_base = self.load_preview_base()

        self.size_var = tk.IntVar(value=self.canvas_size)
        self.zoom_var = tk.IntVar(value=100)
        self.name_var = tk.StringVar(value="あたらしいもの")
        self.tool_var = tk.StringVar(value="pencil")
        self.x_var = tk.IntVar(value=480)
        self.y_var = tk.IntVar(value=330)
        self.width_var = tk.IntVar(value=64)
        self.tag_var = tk.StringVar(value="")
        self.visible_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="左クリックで描く／右クリックで透明にします")
        self.show_grid_var = tk.BooleanVar(value=True)

        self.build_ui()
        self.redraw_editor()
        self.refresh_placement_list()
        self.refresh_library_list()
        self.redraw_preview()

    @staticmethod
    def blank_pixels(size: int) -> list[list[str | None]]:
        return [[None for _ in range(size)] for _ in range(size)]

    def editor_extent(self) -> float:
        return EDITOR_PIXELS * self.zoom_var.get() / 100

    def editor_cell_size(self) -> float:
        return self.editor_extent() / self.canvas_size

    def load_preview_base(self) -> Image.Image:
        if PREVIEW_PATH.exists():
            return Image.open(PREVIEW_PATH).convert("RGBA").resize(
                PREVIEW_SIZE, Image.Resampling.LANCZOS
            )
        image = Image.new("RGBA", PREVIEW_SIZE, "#080b15")
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 226, PREVIEW_SIZE[0], PREVIEW_SIZE[1]), fill="#090d17")
        draw.ellipse((205, 203, 307, 229), fill="#08202a")
        draw.rectangle((226, 211, 282, 218), fill="#1d5664")
        return image

    def build_ui(self) -> None:
        style = ttk.Style()
        style.configure("Title.TLabel", font=("Yu Gothic UI", 13, "bold"))
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=0)
        outer.columnconfigure(1, weight=0)
        outer.columnconfigure(2, weight=1)
        outer.rowconfigure(0, weight=1)

        editor = ttk.Frame(outer)
        editor.grid(row=0, column=0, sticky="n")
        ttk.Label(editor, text="1. オブジェクトを描く", style="Title.TLabel").pack(anchor="w")
        draw_holder = ttk.Frame(editor, width=EDITOR_PIXELS + 18, height=EDITOR_PIXELS + 18)
        draw_holder.pack_propagate(False)
        draw_holder.pack(pady=(8, 6))
        self.draw_canvas = tk.Canvas(
            draw_holder,
            width=EDITOR_PIXELS,
            height=EDITOR_PIXELS,
            highlightthickness=1,
            highlightbackground="#6f747c",
            cursor="crosshair",
        )
        draw_scroll_y = ttk.Scrollbar(draw_holder, orient="vertical", command=self.draw_canvas.yview)
        draw_scroll_x = ttk.Scrollbar(draw_holder, orient="horizontal", command=self.draw_canvas.xview)
        self.draw_canvas.configure(
            xscrollcommand=draw_scroll_x.set,
            yscrollcommand=draw_scroll_y.set,
        )
        self.draw_canvas.grid(row=0, column=0, sticky="nsew")
        draw_scroll_y.grid(row=0, column=1, sticky="ns")
        draw_scroll_x.grid(row=1, column=0, sticky="ew")
        draw_holder.columnconfigure(0, weight=1)
        draw_holder.rowconfigure(0, weight=1)
        self.draw_canvas.bind("<ButtonPress-1>", self.begin_paint)
        self.draw_canvas.bind("<B1-Motion>", self.continue_paint)
        self.draw_canvas.bind("<ButtonRelease-1>", self.end_paint)
        self.draw_canvas.bind("<ButtonPress-3>", self.begin_erase)
        self.draw_canvas.bind("<B3-Motion>", self.continue_erase)
        self.draw_canvas.bind("<ButtonRelease-3>", self.end_paint)
        self.draw_canvas.bind("<Control-MouseWheel>", self.zoom_with_wheel)

        tools = ttk.LabelFrame(outer, text="キャンバスと色", padding=10)
        tools.grid(row=0, column=1, padx=12, sticky="ns")
        ttk.Label(tools, text="キャンバス").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            tools,
            textvariable=self.size_var,
            values=CANVAS_SIZES,
            width=8,
            state="readonly",
        ).grid(row=1, column=0, sticky="ew", pady=(2, 4))
        ttk.Button(tools, text="この大きさで新規", command=self.new_canvas).grid(
            row=2, column=0, sticky="ew", pady=(0, 12)
        )

        ttk.Label(tools, text="編集表示倍率").grid(row=3, column=0, sticky="w")
        zoom_box = ttk.Combobox(
            tools,
            textvariable=self.zoom_var,
            values=(50, 100, 150, 200, 300, 400),
            width=8,
            state="readonly",
        )
        zoom_box.grid(row=4, column=0, sticky="ew", pady=(2, 4))
        zoom_box.bind("<<ComboboxSelected>>", self.zoom_changed)
        ttk.Label(tools, text="%　Ctrl+ホイールでも変更", foreground="#666666").grid(
            row=5, column=0, sticky="w", pady=(0, 10)
        )
        ttk.Checkbutton(
            tools,
            text="グリッドを表示",
            variable=self.show_grid_var,
            command=self.redraw_editor,
        ).grid(row=6, column=0, sticky="w", pady=(0, 10))

        self.color_button = tk.Button(
            tools,
            text="色を選ぶ",
            bg=self.color,
            activebackground=self.color,
            command=self.choose_color,
        )
        self.color_button.grid(row=7, column=0, sticky="ew", pady=(0, 8))
        ttk.Radiobutton(
            tools, text="えんぴつ", variable=self.tool_var, value="pencil"
        ).grid(row=8, column=0, sticky="w")
        ttk.Radiobutton(
            tools, text="透明消しゴム", variable=self.tool_var, value="eraser"
        ).grid(row=9, column=0, sticky="w")
        ttk.Radiobutton(
            tools, text="スポイト", variable=self.tool_var, value="eyedropper"
        ).grid(row=10, column=0, sticky="w")
        ttk.Button(tools, text="1つ戻す", command=self.undo).grid(
            row=11, column=0, sticky="ew", pady=(12, 4)
        )
        ttk.Button(tools, text="背景を全部透明", command=self.clear_canvas).grid(
            row=12, column=0, sticky="ew"
        )

        ttk.Separator(tools).grid(row=13, column=0, sticky="ew", pady=14)
        ttk.Label(tools, text="オブジェクト名").grid(row=14, column=0, sticky="w")
        ttk.Entry(tools, textvariable=self.name_var, width=20).grid(
            row=15, column=0, sticky="ew", pady=(2, 6)
        )
        ttk.Button(tools, text="1024×1024 PNGで保存", command=self.save_png).grid(
            row=16, column=0, sticky="ew"
        )
        ttk.Label(
            tools,
            text="透明部分も含め、常に\n1024×1024で保存します。",
            foreground="#666666",
            justify="left",
        ).grid(row=17, column=0, sticky="w", pady=(7, 0))

        placement = ttk.Frame(outer)
        placement.grid(row=0, column=2, sticky="nsew")
        placement.columnconfigure(0, weight=1)
        ttk.Label(placement, text="2. おばけの住処に置く", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            placement,
            text="住処をクリックすると中心位置が決まります。",
            foreground="#666666",
        ).grid(row=1, column=0, sticky="w", pady=(2, 6))
        self.preview_canvas = tk.Canvas(
            placement,
            width=PREVIEW_SIZE[0],
            height=PREVIEW_SIZE[1],
            highlightthickness=1,
            highlightbackground="#6f747c",
            cursor="crosshair",
        )
        self.preview_canvas.grid(row=2, column=0, sticky="w")
        self.preview_canvas.bind("<ButtonPress-1>", self.preview_press)
        self.preview_canvas.bind("<B1-Motion>", self.preview_drag)
        self.preview_canvas.bind("<ButtonRelease-1>", self.preview_release)

        settings = ttk.LabelFrame(placement, text="配置", padding=10)
        settings.grid(row=3, column=0, sticky="ew", pady=(10, 8))
        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text="横位置").grid(row=0, column=0, sticky="w")
        ttk.Spinbox(settings, from_=0, to=GAME_SIZE[0], textvariable=self.x_var, width=7,
                    command=self.redraw_preview).grid(row=0, column=1, sticky="w")
        ttk.Label(settings, text="縦位置").grid(row=0, column=2, padx=(14, 0), sticky="w")
        ttk.Spinbox(settings, from_=0, to=GAME_SIZE[1], textvariable=self.y_var, width=7,
                    command=self.redraw_preview).grid(row=0, column=3, sticky="w")
        ttk.Label(settings, text="ゲーム内の幅").grid(row=1, column=0, sticky="w", pady=(8, 0))
        scale = ttk.Scale(
            settings,
            from_=8,
            to=512,
            variable=self.width_var,
            command=self.scale_changed,
        )
        scale.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(8, 0))
        self.width_label = ttk.Label(settings, text="64 px", width=8)
        self.width_label.grid(row=1, column=3, sticky="e", pady=(8, 0))
        ttk.Label(settings, text="会話用タグ").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(settings, textvariable=self.tag_var).grid(
            row=2, column=1, columnspan=3, sticky="ew", pady=(8, 0)
        )
        ttk.Checkbutton(
            settings,
            text="ゲーム開始時から表示する",
            variable=self.visible_var,
            command=self.redraw_preview,
        ).grid(row=3, column=0, columnspan=4, sticky="w", pady=(7, 0))
        ttk.Label(
            settings,
            text="タグは配置ごとに一意。会話エディタから移動・取り出す・しまう対象にできます。\n"
                 "縦横比は固定。保存画像の1024pxとは別の表示サイズです。",
            foreground="#666666",
        ).grid(row=4, column=0, columnspan=4, sticky="w", pady=(5, 0))

        buttons = ttk.Frame(placement)
        buttons.grid(row=4, column=0, sticky="ew")
        ttk.Button(buttons, text="新しく住処に置く", command=self.add_to_habitat).pack(
            side="left"
        )
        ttk.Button(buttons, text="選択中の位置・大きさを更新", command=self.update_placement).pack(
            side="left", padx=6
        )
        ttk.Button(buttons, text="選択中を住処から外す", command=self.delete_placement).pack(
            side="left"
        )

        ttk.Label(placement, text="住処に置かれているもの").grid(
            row=5, column=0, sticky="w", pady=(12, 3)
        )
        self.placement_list = tk.Listbox(placement, height=7, exportselection=False)
        self.placement_list.grid(row=6, column=0, sticky="ew")
        self.placement_list.bind("<<ListboxSelect>>", self.select_placement)

        ttk.Label(placement, text="保存済みオブジェクト（何度でも挿入できます）").grid(
            row=7, column=0, sticky="w", pady=(10, 3)
        )
        self.library_list = tk.Listbox(placement, height=5, exportselection=False)
        self.library_list.grid(row=8, column=0, sticky="ew")
        library_buttons = ttk.Frame(placement)
        library_buttons.grid(row=9, column=0, sticky="w", pady=(4, 0))
        ttk.Button(
            library_buttons,
            text="選択した画像を住処に挿入",
            command=self.insert_library_object,
        ).pack(side="left")
        ttk.Button(
            library_buttons,
            text="編集キャンバスへ読み込む",
            command=self.load_library_object,
        ).pack(side="left", padx=6)
        ttk.Label(placement, textvariable=self.status_var, foreground="#475e68").grid(
            row=10, column=0, sticky="w", pady=(8, 0)
        )

    def snapshot(self) -> None:
        self.undo_stack.append([row[:] for row in self.pixels])
        self.undo_stack = self.undo_stack[-40:]

    def new_canvas(self) -> None:
        new_size = int(self.size_var.get())
        if any(value is not None for row in self.pixels for value in row):
            if not messagebox.askyesno("新規キャンバス", "いまの絵を消して作り直しますか？"):
                self.size_var.set(self.canvas_size)
                return
        self.canvas_size = new_size
        self.pixels = self.blank_pixels(new_size)
        self.undo_stack.clear()
        if new_size == 128 and self.zoom_var.get() < 200:
            self.zoom_var.set(200)
        self.redraw_editor()
        self.redraw_preview()

    def zoom_changed(self, _event: tk.Event | None = None) -> None:
        self.redraw_editor()

    def zoom_with_wheel(self, event: tk.Event) -> str:
        values = (50, 100, 150, 200, 300, 400)
        current = self.zoom_var.get()
        index = min(range(len(values)), key=lambda item: abs(values[item] - current))
        index += 1 if event.delta > 0 else -1
        self.zoom_var.set(values[max(0, min(len(values) - 1, index))])
        self.redraw_editor()
        return "break"

    def choose_color(self) -> None:
        chosen = colorchooser.askcolor(self.color, title="描く色を選ぶ")[1]
        if chosen:
            self.color = chosen.lower()
            self.tool_var.set("pencil")
            self.color_button.configure(bg=self.color, activebackground=self.color)

    def clear_canvas(self) -> None:
        if any(value is not None for row in self.pixels for value in row):
            self.snapshot()
        self.pixels = self.blank_pixels(self.canvas_size)
        self.redraw_editor()
        self.redraw_preview()

    def undo(self) -> None:
        if not self.undo_stack:
            return
        self.pixels = self.undo_stack.pop()
        self.redraw_editor()
        self.redraw_preview()

    def begin_paint(self, event: tk.Event) -> None:
        if self.tool_var.get() == "eyedropper":
            self.pick_color(event)
            return
        self.snapshot()
        self.painting = True
        self.last_cell = None
        self.paint_event(event, self.tool_var.get() == "eraser")

    def begin_erase(self, event: tk.Event) -> None:
        self.snapshot()
        self.painting = True
        self.last_cell = None
        self.paint_event(event, True)

    def continue_paint(self, event: tk.Event) -> None:
        if self.painting:
            self.paint_event(event, self.tool_var.get() == "eraser")

    def continue_erase(self, event: tk.Event) -> None:
        if self.painting:
            self.paint_event(event, True)

    def end_paint(self, _event: tk.Event) -> None:
        self.painting = False
        self.last_cell = None
        self.redraw_preview()

    def event_cell(self, event: tk.Event) -> tuple[int, int]:
        cell = self.editor_cell_size()
        canvas_x = self.draw_canvas.canvasx(event.x)
        canvas_y = self.draw_canvas.canvasy(event.y)
        x = max(0, min(self.canvas_size - 1, int(canvas_x / cell)))
        y = max(0, min(self.canvas_size - 1, int(canvas_y / cell)))
        return x, y

    def pick_color(self, event: tk.Event) -> None:
        x, y = self.event_cell(event)
        picked = self.pixels[y][x]
        if picked is None:
            self.status_var.set("透明セルです。色は変更していません。")
            return
        self.color = picked
        self.color_button.configure(bg=self.color, activebackground=self.color)
        self.tool_var.set("pencil")
        self.status_var.set(f"色を拾いました: {self.color}")

    def paint_event(self, event: tk.Event, erase: bool) -> None:
        x, y = self.event_cell(event)
        if self.last_cell == (x, y):
            return
        self.last_cell = (x, y)
        self.pixels[y][x] = None if erase else self.color
        self.draw_editor_cell(x, y)

    def redraw_editor(self) -> None:
        self.draw_canvas.delete("all")
        extent = round(self.editor_extent())
        self.draw_canvas.configure(scrollregion=(0, 0, extent, extent))
        for y in range(self.canvas_size):
            for x in range(self.canvas_size):
                self.draw_editor_cell(x, y)

    def draw_editor_cell(self, x: int, y: int) -> None:
        tag = f"cell_{x}_{y}"
        self.draw_canvas.delete(tag)
        cell = self.editor_cell_size()
        x0, y0 = round(x * cell), round(y * cell)
        x1, y1 = round((x + 1) * cell), round((y + 1) * cell)
        value = self.pixels[y][x]
        fill = value if value else ("#c7c9cc" if (x + y) % 2 else "#eeeeee")
        outline = "#50545a" if self.show_grid_var.get() and cell >= 6 else ""
        self.draw_canvas.create_rectangle(
            x0, y0, x1 + 1, y1 + 1, fill=fill, outline=outline, tags=tag
        )

    def source_image(self) -> Image.Image:
        return PIXEL_OBJECT_REPOSITORY.image_from_pixels(
            self.canvas_size,
            self.pixels,
        )

    def save_object_files(self, ask_overwrite: bool = True) -> tuple[Path, Path] | None:
        if not any(value is not None for row in self.pixels for value in row):
            messagebox.showwarning("空のキャンバス", "色を塗ってから保存してください。")
            return None
        png_path, source_path = PIXEL_OBJECT_REPOSITORY.paths_for(self.name_var.get())
        if ask_overwrite and png_path.exists():
            if not messagebox.askyesno("上書き", f"「{png_path.stem}」を上書きしますか？"):
                return None
        return PIXEL_OBJECT_REPOSITORY.save(
            self.name_var.get(),
            self.canvas_size,
            self.pixels,
        )

    def save_png(self) -> None:
        paths = self.save_object_files()
        if paths:
            self.refresh_library_list()
            self.status_var.set(f"1024×1024で保存しました: {paths[0].name}")

    def current_preview_image(self) -> Image.Image | None:
        if not any(value is not None for row in self.pixels for value in row):
            return None
        return self.source_image().resize((EXPORT_SIZE, EXPORT_SIZE), Image.Resampling.NEAREST)

    def redraw_preview(self, *_args) -> None:
        composite = self.preview_base.copy()
        selected = self.selected_placement
        for index, item in enumerate(self.placements):
            try:
                image_path = PROJECT_DIR / item["image"]
                source = Image.open(image_path).convert("RGBA")
                width = max(2, round(int(item["width"]) / 2))
                height = max(1, round(source.height * width / source.width))
                sprite = source.resize((width, height), Image.Resampling.LANCZOS)
                if not bool(item.get("visible", True)):
                    alpha = sprite.getchannel("A").point(lambda value: round(value * 0.28))
                    sprite.putalpha(alpha)
                x = round(int(item["x"]) / 2 - width / 2)
                y = round(int(item["y"]) / 2 - height / 2)
                composite.alpha_composite(sprite, (x, y))
                if index == selected:
                    ImageDraw.Draw(composite).rectangle(
                        (x - 2, y - 2, x + width + 1, y + height + 1),
                        outline="#f3d66e",
                        width=2,
                    )
            except (KeyError, OSError, ValueError, TypeError):
                continue

        draft = self.current_preview_image()
        if draft is not None and selected is None:
            width = max(2, round(self.width_var.get() / 2))
            height = max(1, round(draft.height * width / draft.width))
            draft = draft.resize((width, height), Image.Resampling.LANCZOS)
            x = round(self.x_var.get() / 2 - width / 2)
            y = round(self.y_var.get() / 2 - height / 2)
            composite.alpha_composite(draft, (x, y))
            ImageDraw.Draw(composite).rectangle(
                (x - 2, y - 2, x + width + 1, y + height + 1),
                outline="#70d6d1",
                width=2,
            )

        self.preview_photo = ImageTk.PhotoImage(composite)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(0, 0, image=self.preview_photo, anchor="nw")

    def placement_contains(self, index: int, x: int, y: int) -> bool:
        item = self.placements[index]
        try:
            source = Image.open(PROJECT_DIR / item["image"])
            width = int(item["width"])
            height = round(source.height * width / source.width)
            return (
                abs(x - int(item["x"])) <= width / 2
                and abs(y - int(item["y"])) <= height / 2
            )
        except (KeyError, OSError, TypeError, ValueError, ZeroDivisionError):
            return False

    def preview_press(self, event: tk.Event) -> None:
        game_x = max(0, min(GAME_SIZE[0], event.x * 2))
        game_y = max(0, min(GAME_SIZE[1], event.y * 2))
        hit = next(
            (
                index
                for index in range(len(self.placements) - 1, -1, -1)
                if self.placement_contains(index, game_x, game_y)
            ),
            None,
        )
        if hit is not None:
            self.selected_placement = hit
            item = self.placements[hit]
            self.drag_offset = (int(item["x"]) - game_x, int(item["y"]) - game_y)
            self.dragging_placement = True
            self.placement_list.selection_clear(0, "end")
            self.placement_list.selection_set(hit)
            self.placement_list.see(hit)
            self.apply_selected_placement()
        elif self.selected_placement is not None:
            self.drag_offset = (0, 0)
            self.dragging_placement = True
            self.move_selected_to(game_x, game_y)
        else:
            self.x_var.set(game_x)
            self.y_var.set(game_y)
            self.redraw_preview()

    def preview_drag(self, event: tk.Event) -> None:
        if not self.dragging_placement or self.selected_placement is None:
            return
        self.move_selected_to(
            max(0, min(GAME_SIZE[0], event.x * 2)) + self.drag_offset[0],
            max(0, min(GAME_SIZE[1], event.y * 2)) + self.drag_offset[1],
        )

    def preview_release(self, _event: tk.Event) -> None:
        if self.dragging_placement and self.selected_placement is not None:
            PLACEMENT_REPOSITORY.save_editable(self.placements)
            self.refresh_placement_list()
            self.placement_list.selection_set(self.selected_placement)
            self.status_var.set("ドラッグした位置を保存しました。")
        self.dragging_placement = False

    def move_selected_to(self, x: int, y: int) -> None:
        if self.selected_placement is None:
            return
        self.x_var.set(max(0, min(GAME_SIZE[0], x)))
        self.y_var.set(max(0, min(GAME_SIZE[1], y)))
        self.placements[self.selected_placement]["x"] = self.x_var.get()
        self.placements[self.selected_placement]["y"] = self.y_var.get()
        self.redraw_preview()

    def scale_changed(self, _value: str) -> None:
        self.width_label.configure(text=f"{self.width_var.get()} px")
        if self.selected_placement is not None:
            self.placements[self.selected_placement]["width"] = self.width_var.get()
        self.redraw_preview()

    def placement_tag(self, ignore_index: int | None = None) -> str | None:
        tag = normalize_tag(self.tag_var.get())
        if not tag:
            return ""
        for index, item in enumerate(self.placements):
            if index != ignore_index and normalize_tag(str(item.get("tag", ""))) == tag:
                messagebox.showerror(
                    "タグが重複しています",
                    f"タグ「{tag}」は別の配置で使われています。別のタグにしてください。",
                )
                return None
        return tag

    def add_to_habitat(self) -> None:
        tag = self.placement_tag()
        if tag is None:
            return
        paths = self.save_object_files()
        if not paths:
            return
        png_path, source_path = paths
        item = {
            "id": uuid.uuid4().hex[:10],
            "name": self.name_var.get().strip() or png_path.stem,
            "image": png_path.relative_to(PROJECT_DIR).as_posix(),
            "source": source_path.relative_to(PROJECT_DIR).as_posix(),
            "x": self.x_var.get(),
            "y": self.y_var.get(),
            "width": self.width_var.get(),
            "visible": self.visible_var.get(),
        }
        if tag:
            item["tag"] = tag
        self.placements.append(item)
        PLACEMENT_REPOSITORY.save_editable(self.placements)
        self.refresh_library_list()
        self.selected_placement = len(self.placements) - 1
        self.refresh_placement_list()
        self.placement_list.selection_set(self.selected_placement)
        self.redraw_preview()
        self.status_var.set("住処に置きました。ゲームを起動し直すと表示されます。")

    def update_placement(self) -> None:
        if self.selected_placement is None:
            messagebox.showinfo("選択", "一覧から更新するものを選んでください。")
            return
        tag = self.placement_tag(self.selected_placement)
        if tag is None:
            return
        item = self.placements[self.selected_placement]
        item["x"] = self.x_var.get()
        item["y"] = self.y_var.get()
        item["width"] = self.width_var.get()
        item["visible"] = self.visible_var.get()
        if tag:
            item["tag"] = tag
        else:
            item.pop("tag", None)
        PLACEMENT_REPOSITORY.save_editable(self.placements)
        self.refresh_placement_list()
        self.placement_list.selection_set(self.selected_placement)
        self.redraw_preview()
        self.status_var.set("位置と大きさを更新しました。")

    def delete_placement(self) -> None:
        if self.selected_placement is None:
            return
        item = self.placements[self.selected_placement]
        if not messagebox.askyesno("住処から外す", f"「{item.get('name', 'オブジェクト')}」を外しますか？"):
            return
        del self.placements[self.selected_placement]
        self.selected_placement = None
        PLACEMENT_REPOSITORY.save_editable(self.placements)
        self.refresh_placement_list()
        self.redraw_preview()
        self.status_var.set("住処から外しました。PNGはobjectsフォルダーに残ります。")

    def refresh_placement_list(self) -> None:
        self.placement_list.delete(0, "end")
        for item in self.placements:
            self.placement_list.insert(
                "end",
                f"{item.get('name', 'object')}  "
                f"{('#' + str(item.get('tag'))) if item.get('tag') else 'タグなし'}  "
                f"({item.get('x', 0)}, {item.get('y', 0)})  {item.get('width', 0)}px",
            )

    def refresh_library_list(self) -> None:
        extra_images = []
        for item in self.placements:
            try:
                path = (PROJECT_DIR / str(item["image"])).resolve()
                path.relative_to(PROJECT_DIR.resolve())
                extra_images.append(path)
            except (KeyError, OSError, ValueError):
                continue
        self.library_paths = PIXEL_OBJECT_REPOSITORY.library_images(extra_images)
        self.library_list.delete(0, "end")
        for image_path in self.library_paths:
            relative = image_path.relative_to(PROJECT_DIR).as_posix()
            existing = next(
                (item for item in self.placements if item.get("image") == relative),
                None,
            )
            self.library_list.insert(
                "end",
                str(existing.get("name"))
                if existing
                else BUILTIN_LIBRARY.get(image_path.stem, (image_path.stem, 64))[0],
            )

    def selected_library_path(self) -> Path | None:
        selection = self.library_list.curselection()
        if not selection:
            messagebox.showinfo("選択", "保存済みオブジェクトを選んでください。")
            return None
        return self.library_paths[int(selection[0])]

    def insert_library_object(self) -> None:
        image_path = self.selected_library_path()
        if image_path is None:
            return
        relative = image_path.relative_to(PROJECT_DIR).as_posix()
        example = next(
            (item for item in self.placements if item.get("image") == relative),
            None,
        )
        source_path = PIXEL_OBJECT_REPOSITORY.source_for_image(image_path)
        builtin_name, builtin_width = BUILTIN_LIBRARY.get(
            image_path.stem, (image_path.stem, self.width_var.get())
        )
        item = {
            "id": uuid.uuid4().hex[:10],
            "name": str(example.get("name")) if example else builtin_name,
            "image": relative,
            "x": self.x_var.get(),
            "y": self.y_var.get(),
            "width": int(example.get("width", builtin_width)) if example else builtin_width,
            "visible": bool(example.get("visible", True)) if example else True,
        }
        if example and example.get("tag"):
            proposed_tag = normalize_tag(str(example["tag"]))
            used_tags = {normalize_tag(str(value.get("tag", ""))) for value in self.placements}
            if proposed_tag and proposed_tag not in used_tags:
                item["tag"] = proposed_tag
        if source_path.exists():
            item["source"] = source_path.relative_to(PROJECT_DIR).as_posix()
        self.placements.append(item)
        PLACEMENT_REPOSITORY.save_editable(self.placements)
        self.selected_placement = len(self.placements) - 1
        self.refresh_placement_list()
        self.placement_list.selection_set(self.selected_placement)
        self.apply_selected_placement()
        self.status_var.set("保存済み画像を新しく挿入しました。ドラッグで移動できます。")

    def load_library_object(self) -> None:
        image_path = self.selected_library_path()
        if image_path is None:
            return
        source_path = PIXEL_OBJECT_REPOSITORY.source_for_image(image_path)
        if not source_path.exists():
            messagebox.showinfo("編集データなし", "この画像にはマス目の編集データがありません。")
            return
        self.selected_placement = None
        self.placement_list.selection_clear(0, "end")
        self.name_var.set(BUILTIN_LIBRARY.get(image_path.stem, (image_path.stem, 64))[0])
        self.load_source({"source": source_path.relative_to(PROJECT_DIR).as_posix()})
        self.redraw_preview()
        self.status_var.set("保存済み画像を編集キャンバスへ読み込みました。")

    def select_placement(self, _event: tk.Event) -> None:
        selection = self.placement_list.curselection()
        if not selection:
            return
        self.selected_placement = int(selection[0])
        self.apply_selected_placement()

    def apply_selected_placement(self) -> None:
        if self.selected_placement is None:
            return
        item = self.placements[self.selected_placement]
        self.x_var.set(int(item.get("x", 480)))
        self.y_var.set(int(item.get("y", 330)))
        self.width_var.set(int(item.get("width", 64)))
        self.tag_var.set(str(item.get("tag", "")))
        self.visible_var.set(bool(item.get("visible", True)))
        self.width_label.configure(text=f"{self.width_var.get()} px")
        self.name_var.set(str(item.get("name", "object")))
        self.load_source(item)
        self.redraw_preview()

    def load_source(self, item: dict) -> None:
        try:
            source_path = PROJECT_DIR / item["source"]
            size, pixels = PIXEL_OBJECT_REPOSITORY.load(source_path)
            self.canvas_size = size
            self.size_var.set(size)
            if size == 128 and self.zoom_var.get() < 200:
                self.zoom_var.set(200)
            self.pixels = pixels
            self.undo_stack.clear()
            self.redraw_editor()
        except (KeyError, OSError, ValueError, TypeError):
            pass


def main() -> None:
    root = tk.Tk()
    ObjectEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()
