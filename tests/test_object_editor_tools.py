import sys
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

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


if __name__ == "__main__":
    unittest.main()
