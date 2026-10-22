import sys
import unittest
from pathlib import Path
from unittest import mock

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
