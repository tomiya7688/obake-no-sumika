import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

import pygame

from engine.room_renderer import RoomRenderer
from engine.room_repository import RoomRepository


class RoomRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        pygame.display.set_mode((960, 540))

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.quit()

    def test_current_room_is_valid_and_uses_16_by_9(self):
        room = RoomRepository(PROJECT_DIR / "room.json").load()
        self.assertEqual((room.width, room.height), (960, 540))
        self.assertEqual(room.movement_bounds, (74, 80, 812, 446))
        self.assertEqual(room.water_rest_area, (335, 348, 354, 168))
        self.assertEqual(room.mote_count, 34)
        self.assertEqual(len(room.polygon_layers), 8)

    def test_renderer_uses_room_dimensions(self):
        room = RoomRepository(PROJECT_DIR / "room.json").load()
        surface = RoomRenderer(room).render()
        self.assertEqual(surface.get_size(), (room.width, room.height))

    def test_non_16_by_9_room_is_rejected(self):
        raw = self.current_payload()
        raw["size"]["height"] = 541
        with self.assertRaisesRegex(ValueError, "16:9"):
            self.load_temporary(raw)

    def test_movement_bounds_outside_room_are_rejected(self):
        raw = self.current_payload()
        raw["movement_bounds"] = [900, 500, 100, 100]
        with self.assertRaisesRegex(ValueError, "inside"):
            self.load_temporary(raw)

    # Every float field of room.json: (path in the document, index inside a range or None).
    FLOAT_FIELDS = (
        (("conversation_distance",), None),
        (("motes", "x_range"), 0),
        (("motes", "x_range"), 1),
        (("motes", "y_range"), 0),
        (("motes", "y_range"), 1),
        (("motes", "reset_y_range"), 0),
        (("motes", "reset_y_range"), 1),
        (("motes", "speed_range"), 0),
        (("motes", "speed_range"), 1),
        (("motes", "top"), None),
        (("motes", "drift_speed"), None),
        (("motes", "drift_amount"), None),
    )

    def test_every_float_field_rejects_non_finite_numbers(self):
        # NaN fails both `< minimum` and `> maximum`, so a range check alone lets it
        # through; 1e999 is read by the JSON decoder as infinity (Issue #31).
        for path, index in self.FLOAT_FIELDS:
            for text in ("NaN", "Infinity", "-Infinity", "1e999", "-1e999"):
                with self.subTest(field=".".join(path), index=index, value=text):
                    raw = self.current_payload()
                    holder = raw
                    for key in path[:-1]:
                        holder = holder[key]
                    marker = "__NON_FINITE__"
                    if index is None:
                        holder[path[-1]] = marker
                    else:
                        holder[path[-1]][index] = marker
                    with tempfile.TemporaryDirectory() as temp_dir:
                        room_path = Path(temp_dir) / "room.json"
                        room_path.write_text(
                            json.dumps(raw).replace(f'"{marker}"', text), encoding="utf-8"
                        )
                        with self.assertRaisesRegex(ValueError, "finite"):
                            RoomRepository(room_path).load()

    def test_huge_integers_are_a_value_error_not_an_overflow(self):
        raw = self.current_payload()
        raw["conversation_distance"] = 10**400  # float() of this raises OverflowError
        with self.assertRaisesRegex(ValueError, "finite"):
            self.load_temporary(raw)

    @staticmethod
    def current_payload() -> dict[str, object]:
        return json.loads((PROJECT_DIR / "room.json").read_text(encoding="utf-8"))

    @staticmethod
    def load_temporary(payload: dict[str, object]):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "room.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return RoomRepository(path).load()


if __name__ == "__main__":
    unittest.main()
