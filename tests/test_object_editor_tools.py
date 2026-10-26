import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from PIL import Image

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

import object_editor
from object_editor import ObjectEditor


class ObjectEditorToolTests(unittest.TestCase):
    def make_editor(self, pixels: list[list[str | None]]) -> ObjectEditor:
        editor = ObjectEditor.__new__(ObjectEditor)
        editor.canvas_size = len(pixels)
        editor.pixels = [row[:] for row in pixels]
        return editor

    def test_fill_region_replaces_connected_area_only(self):
        editor = self.make_editor(
            [
                [None, None, "#000000"],
                [None, "#000000", "#000000"],
                ["#ffffff", "#ffffff", None],
            ]
        )

        filled = editor.fill_region(0, 0, None, "#ff0000")

        self.assertEqual(filled, 3)
        self.assertEqual(
            editor.pixels,
            [
                ["#ff0000", "#ff0000", "#000000"],
                ["#ff0000", "#000000", "#000000"],
                ["#ffffff", "#ffffff", None],
            ],
        )

    def test_fill_region_keeps_diagonal_area_separate(self):
        editor = self.make_editor(
            [
                [None, "#000000", None],
                ["#000000", None, "#000000"],
                [None, "#000000", None],
            ]
        )

        filled = editor.fill_region(0, 0, None, "#ff0000")

        self.assertEqual(filled, 1)
        self.assertEqual(editor.pixels[0][0], "#ff0000")
        self.assertIsNone(editor.pixels[1][1])

    def test_flipped_horizontal_reverses_each_row(self):
        pixels = [
            ["#111111", None, "#222222"],
            ["#333333", "#444444", None],
        ]

        self.assertEqual(
            ObjectEditor.flipped_horizontal(pixels),
            [
                ["#222222", None, "#111111"],
                [None, "#444444", "#333333"],
            ],
        )

    def test_flipped_vertical_reverses_row_order(self):
        pixels = [
            ["#111111", None],
            ["#222222", "#333333"],
            [None, "#444444"],
        ]

        self.assertEqual(
            ObjectEditor.flipped_vertical(pixels),
            [
                [None, "#444444"],
                ["#222222", "#333333"],
                ["#111111", None],
            ],
        )

    def test_rotated_clockwise_turns_square_canvas_right(self):
        pixels = [
            ["a", "b", "c"],
            ["d", "e", "f"],
            ["g", "h", "i"],
        ]

        self.assertEqual(
            ObjectEditor.rotated_clockwise(pixels),
            [
                ["g", "d", "a"],
                ["h", "e", "b"],
                ["i", "f", "c"],
            ],
        )

    def test_rotated_counterclockwise_turns_square_canvas_left(self):
        pixels = [
            ["a", "b", "c"],
            ["d", "e", "f"],
            ["g", "h", "i"],
        ]

        self.assertEqual(
            ObjectEditor.rotated_counterclockwise(pixels),
            [
                ["c", "f", "i"],
                ["b", "e", "h"],
                ["a", "d", "g"],
            ],
        )

    def test_brush_cells_returns_centered_square(self):
        self.assertEqual(
            ObjectEditor.brush_cells(2, 2, 3, 6),
            [(1, 1), (2, 1), (3, 1), (1, 2), (2, 2), (3, 2), (1, 3), (2, 3), (3, 3)],
        )

    def test_brush_cells_clips_at_canvas_edges(self):
        self.assertEqual(
            ObjectEditor.brush_cells(0, 0, 5, 4),
            [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1), (0, 2), (1, 2), (2, 2)],
        )

    ROOMS = ((960, 540), (1280, 720), (1920, 1080))

    def test_preview_conversion_follows_room_size(self):
        preview = (480, 270)
        for room in self.ROOMS:
            with self.subTest(room=room):
                scale = room[0] / preview[0]
                self.assertEqual(object_editor.preview_scale(room, preview), (scale, scale))
                center = (room[0] // 2, room[1] // 2)
                self.assertEqual(object_editor.preview_to_game(240, 135, room, preview), center)
                back = object_editor.game_to_preview(*center, room, preview)
                self.assertAlmostEqual(back[0], 240)
                self.assertAlmostEqual(back[1], 135)
                length = object_editor.game_length_to_preview(64 * scale, room, preview)
                self.assertAlmostEqual(length, 64)
                self.assertEqual(
                    object_editor.preview_to_game(-5, 999, room, preview), (0, room[1])
                )
                self.assertEqual(
                    object_editor.preview_to_game(-5, 999, room, preview, clamp=False),
                    (round(-5 * scale), round(999 * scale)),
                )

    def test_preview_click_and_drawing_round_trip(self):
        room, preview = (1920, 1080), (480, 270)
        for point in ((0, 0), (37, 201), (479, 269)):
            with self.subTest(point=point):
                game = object_editor.preview_to_game(*point, room, preview)
                back = object_editor.game_to_preview(*game, room, preview)
                self.assertAlmostEqual(back[0], point[0], delta=0.5)
                self.assertAlmostEqual(back[1], point[1], delta=0.5)

    class Var:
        def __init__(self, value=0):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value

    def make_preview_editor(self, placements):
        editor = ObjectEditor.__new__(ObjectEditor)
        editor.placements = placements
        editor.selected_placement = None
        editor.dragging_placement = False
        editor.drag_offset = (0, 0)
        editor.x_var, editor.y_var = self.Var(), self.Var()
        editor.placement_list = mock.Mock()
        editor.redraw_preview = mock.Mock()
        editor.apply_selected_placement = mock.Mock()
        return editor

    def test_press_and_drag_use_the_room_scale(self):
        for room in self.ROOMS:
            scale = room[0] / 480
            with (
                self.subTest(room=room),
                mock.patch.object(object_editor, "GAME_SIZE", room),
                mock.patch.object(object_editor, "PREVIEW_SIZE", (480, 270)),
            ):
                editor = self.make_preview_editor([])
                editor.preview_press(SimpleNamespace(x=240, y=135))
                self.assertEqual(
                    (editor.x_var.get(), editor.y_var.get()), (room[0] // 2, room[1] // 2)
                )

                item = {"x": round(100 * scale), "y": round(50 * scale)}
                editor = self.make_preview_editor([item])
                with mock.patch.object(ObjectEditor, "placement_contains", return_value=True):
                    editor.preview_press(SimpleNamespace(x=102, y=50))
                self.assertEqual(editor.selected_placement, 0)
                self.assertEqual(editor.drag_offset, (item["x"] - round(102 * scale), 0))
                editor.preview_drag(SimpleNamespace(x=202, y=150))
                # The object keeps the grab offset from the cursor.
                self.assertEqual(
                    (item["x"], item["y"]),
                    (round(202 * scale) + editor.drag_offset[0], round(150 * scale)),
                )
                # Dragging past the right edge keeps the object against the edge.
                editor.preview_drag(SimpleNamespace(x=900, y=150))
                self.assertEqual(item["x"], room[0])

    def test_drawing_places_sprites_with_the_room_scale(self):
        # A tall sprite so a wrong vertical scale would show in the height and y.
        sprite = Image.new("RGBA", (10, 20), "white")
        for room in self.ROOMS:
            with self.subTest(room=room):
                scale = room[0] / 480
                item = {
                    "image": "x.png",
                    "x": round(240 * scale),
                    "y": round(135 * scale),
                    "width": round(40 * scale),
                    "visible": True,
                }
                editor = self.make_preview_editor([item])
                editor.redraw_preview = ObjectEditor.redraw_preview.__get__(editor)
                editor.current_preview_image = mock.Mock(return_value=None)
                editor.preview_canvas = mock.Mock()
                base = mock.Mock(wraps=Image.new("RGBA", (480, 270)))
                editor.preview_base = mock.Mock(copy=mock.Mock(return_value=base))
                with (
                    mock.patch.object(object_editor, "GAME_SIZE", room),
                    mock.patch.object(object_editor, "PREVIEW_SIZE", (480, 270)),
                    mock.patch.object(object_editor.Image, "open", return_value=sprite),
                    mock.patch.object(object_editor.ImageTk, "PhotoImage"),
                ):
                    editor.redraw_preview()
                pasted, position = base.alpha_composite.call_args.args
                self.assertEqual(pasted.size, (40, 80))
                # Sprites are drawn centered on the placement.
                self.assertEqual(position, (220, 95))

    def test_click_hit_test_uses_real_image_and_room_scale(self):
        # Clicks hit the same rounded preview box the sprite is drawn in.
        for room in self.ROOMS:
            with self.subTest(room=room):
                scale = room[0] / 480
                item = {
                    "image": "assets/kadoka.png",
                    "x": round(240 * scale),
                    "y": round(135 * scale),
                    "width": round(40 * scale),
                }
                with (
                    mock.patch.object(object_editor, "GAME_SIZE", room),
                    mock.patch.object(object_editor, "PREVIEW_SIZE", (480, 270)),
                ):
                    inside = self.make_preview_editor([item])
                    inside.preview_press(SimpleNamespace(x=245, y=135))
                    outside = self.make_preview_editor([item])
                    outside.preview_press(SimpleNamespace(x=300, y=135))
                self.assertEqual(inside.selected_placement, 0)
                self.assertIsNone(outside.selected_placement)

    def test_tiny_sprite_edge_pixel_is_selectable(self):
        # 1280x720, width 8, center x=800 is drawn from preview x=298 (min 2 px wide);
        # its first drawn pixel must select it (CodeRabbit on PR #109).
        room = (1280, 720)
        item = {"image": "assets/kadoka.png", "x": 800, "y": 360, "width": 8}
        with (
            mock.patch.object(object_editor, "GAME_SIZE", room),
            mock.patch.object(object_editor, "PREVIEW_SIZE", (480, 270)),
        ):
            with Image.open(object_editor.PROJECT_DIR / item["image"]) as source:
                left, top, width, height = object_editor.preview_rect(800, 360, 8, source.size)
            self.assertEqual((left, width), (298, 3))
            for x in (left, left + width - 1):
                editor = self.make_preview_editor([item])
                editor.preview_press(SimpleNamespace(x=x, y=top))
                self.assertEqual(editor.selected_placement, 0, x)
            editor = self.make_preview_editor([item])
            editor.preview_press(SimpleNamespace(x=left + width, y=top))
            self.assertIsNone(editor.selected_placement)

    def make_saving_editor(self, problems: list[str]) -> ObjectEditor:
        editor = ObjectEditor.__new__(ObjectEditor)
        editor.placements = [{"id": "one"}]
        editor.load_problems = list(problems)
        editor.status_var = mock.Mock()
        return editor

    def test_save_placements_refuses_to_drop_problems_without_consent(self):
        editor = self.make_saving_editor(["配置2: x must be an integer"])
        with mock.patch.object(
            object_editor.messagebox, "askyesno", return_value=False
        ) as ask, mock.patch.object(
            object_editor.PLACEMENT_REPOSITORY, "save_editable"
        ) as save:
            self.assertFalse(editor.save_placements())
        ask.assert_called_once()
        save.assert_not_called()
        self.assertEqual(editor.load_problems, ["配置2: x must be an integer"])

    def test_save_placements_discards_problems_only_after_consent(self):
        editor = self.make_saving_editor(["配置2: x must be an integer"])
        with mock.patch.object(
            object_editor.messagebox, "askyesno", return_value=True
        ), mock.patch.object(
            object_editor.PLACEMENT_REPOSITORY, "save_editable"
        ) as save:
            self.assertTrue(editor.save_placements())
        save.assert_called_once_with(editor.placements)
        self.assertEqual(editor.load_problems, [])

    def test_save_placements_without_problems_does_not_ask(self):
        editor = self.make_saving_editor([])
        with mock.patch.object(
            object_editor.messagebox, "askyesno"
        ) as ask, mock.patch.object(
            object_editor.PLACEMENT_REPOSITORY, "save_editable"
        ) as save:
            self.assertTrue(editor.save_placements())
        ask.assert_not_called()
        save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
