from __future__ import annotations

import json
from pathlib import Path

from .room_definition import Color, Point, PolygonLayer, RoomDefinition


class RoomRepository:
    """Load and validate one JSON room definition."""

    def __init__(self, data_path: Path) -> None:
        self.data_path = data_path.resolve()

    def load(self) -> RoomDefinition:
        raw = json.loads(self.data_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise ValueError("Unsupported room schema version")
        size = self._object(raw.get("size"), "size")
        width = self._integer(size.get("width"), "width", 320, 3840)
        height = self._integer(size.get("height"), "height", 180, 2160)
        if width * 9 != height * 16:
            raise ValueError("Room size must use a 16:9 aspect ratio")

        zones = self._object(raw.get("zones"), "zones")
        motes = self._object(raw.get("motes"), "motes")
        background = self._object(raw.get("background"), "background")
        gradient = self._object(background.get("gradient"), "background.gradient")
        vignette = self._object(background.get("vignette"), "background.vignette")
        movement_bounds = self._rect(raw.get("movement_bounds"), "movement_bounds")
        water_rest_area = self._rect(zones.get("water_rest"), "zones.water_rest")
        self._validate_inside_room(movement_bounds, width, height, "movement_bounds")
        self._validate_inside_room(water_rest_area, width, height, "zones.water_rest")

        return RoomDefinition(
            width=width,
            height=height,
            fps=self._integer(raw.get("fps"), "fps", 1, 240),
            movement_bounds=movement_bounds,
            water_rest_area=water_rest_area,
            conversation_distance=self._number(
                raw.get("conversation_distance"), "conversation_distance", 1.0, float(width)
            ),
            mote_count=self._integer(motes.get("count"), "motes.count", 0, 1000),
            mote_x_range=self._range(motes.get("x_range"), "motes.x_range"),
            mote_y_range=self._range(motes.get("y_range"), "motes.y_range"),
            mote_reset_y_range=self._range(
                motes.get("reset_y_range"), "motes.reset_y_range"
            ),
            mote_top=self._number(motes.get("top"), "motes.top", 0.0, float(height)),
            mote_speed_range=self._nonnegative_range(
                motes.get("speed_range"), "motes.speed_range"
            ),
            mote_drift_speed=self._number(
                motes.get("drift_speed"), "motes.drift_speed", 0.0, 100.0
            ),
            mote_drift_amount=self._number(
                motes.get("drift_amount"), "motes.drift_amount", 0.0, 100.0
            ),
            mote_radii=self._positive_integers(motes.get("radii"), "motes.radii"),
            mote_alpha_range=self._integer_range(
                motes.get("alpha_range"), "motes.alpha_range", 0, 255
            ),
            mote_color=self._color(motes.get("color"), "motes.color"),
            gradient_top=self._color(gradient.get("top"), "background.gradient.top"),
            gradient_bottom=self._color(
                gradient.get("bottom"), "background.gradient.bottom"
            ),
            gradient_step=self._integer(
                gradient.get("step"), "background.gradient.step", 1, height
            ),
            polygon_layers=self._polygons(background.get("polygons")),
            vignette_color=self._color(vignette.get("color"), "background.vignette.color"),
            vignette_max_inset=self._integer(
                vignette.get("max_inset"), "background.vignette.max_inset", 0, width // 2
            ),
            vignette_step=self._integer(
                vignette.get("step"), "background.vignette.step", 1, width
            ),
            vignette_border_width=self._integer(
                vignette.get("border_width"), "background.vignette.border_width", 1, 100
            ),
            vignette_radius=self._integer(
                vignette.get("radius"), "background.vignette.radius", 0, 500
            ),
            vignette_alpha_start=self._integer(
                vignette.get("alpha_start"), "background.vignette.alpha_start", 0, 255
            ),
            vignette_alpha_divisor=self._integer(
                vignette.get("alpha_divisor"),
                "background.vignette.alpha_divisor",
                1,
                1000,
            ),
            vignette_min_alpha=self._integer(
                vignette.get("min_alpha"), "background.vignette.min_alpha", 0, 255
            ),
        )

    def _polygons(self, raw: object) -> tuple[PolygonLayer, ...]:
        if not isinstance(raw, list):
            raise ValueError("background.polygons must be a list")
        layers = []
        for index, value in enumerate(raw):
            item = self._object(value, f"background.polygons[{index}]")
            color = self._color(item.get("color"), f"background.polygons[{index}].color")
            raw_points = item.get("points")
            if not isinstance(raw_points, list) or len(raw_points) < 3:
                raise ValueError(f"background.polygons[{index}].points needs 3 points")
            points: list[Point] = []
            for point_index, raw_point in enumerate(raw_points):
                if not isinstance(raw_point, list) or len(raw_point) != 2:
                    raise ValueError(
                        f"background.polygons[{index}].points[{point_index}] is invalid"
                    )
                points.append(
                    (
                        self._integer_unbounded(raw_point[0], "polygon x"),
                        self._integer_unbounded(raw_point[1], "polygon y"),
                    )
                )
            layers.append((color, tuple(points)))
        return tuple(layers)

    def _color(self, raw: object, label: str) -> Color:
        if not isinstance(raw, list) or len(raw) != 3:
            raise ValueError(f"{label} must contain red, green, and blue")
        return (
            self._integer(raw[0], f"{label}.red", 0, 255),
            self._integer(raw[1], f"{label}.green", 0, 255),
            self._integer(raw[2], f"{label}.blue", 0, 255),
        )

    def _rect(self, raw: object, label: str) -> tuple[int, int, int, int]:
        if not isinstance(raw, list) or len(raw) != 4:
            raise ValueError(f"{label} must contain x, y, width, and height")
        values = [self._integer_unbounded(value, label) for value in raw]
        return values[0], values[1], values[2], values[3]

    def _range(self, raw: object, label: str) -> tuple[float, float]:
        if not isinstance(raw, list) or len(raw) != 2:
            raise ValueError(f"{label} must contain minimum and maximum")
        minimum = self._number(raw[0], label, -10000.0, 10000.0)
        maximum = self._number(raw[1], label, -10000.0, 10000.0)
        if minimum >= maximum:
            raise ValueError(f"{label} minimum must be below maximum")
        return minimum, maximum

    def _integer_range(
        self, raw: object, label: str, minimum: int, maximum: int
    ) -> tuple[int, int]:
        if not isinstance(raw, list) or len(raw) != 2:
            raise ValueError(f"{label} must contain minimum and maximum")
        low = self._integer(raw[0], label, minimum, maximum)
        high = self._integer(raw[1], label, minimum, maximum)
        if low > high:
            raise ValueError(f"{label} minimum must not exceed maximum")
        return low, high

    def _nonnegative_range(self, raw: object, label: str) -> tuple[float, float]:
        minimum, maximum = self._range(raw, label)
        if minimum < 0.0:
            raise ValueError(f"{label} must not contain negative values")
        return minimum, maximum

    def _positive_integers(self, raw: object, label: str) -> tuple[int, ...]:
        if not isinstance(raw, list) or not raw:
            raise ValueError(f"{label} must be a non-empty list")
        return tuple(self._integer(value, label, 1, 100) for value in raw)

    @staticmethod
    def _validate_inside_room(
        rect: tuple[int, int, int, int], width: int, height: int, label: str
    ) -> None:
        x, y, rect_width, rect_height = rect
        if rect_width <= 0 or rect_height <= 0:
            raise ValueError(f"{label} width and height must be positive")
        if x < 0 or y < 0 or x + rect_width > width or y + rect_height > height:
            raise ValueError(f"{label} must stay inside the room")

    @staticmethod
    def _object(raw: object, label: str) -> dict[str, object]:
        if not isinstance(raw, dict):
            raise ValueError(f"{label} must be an object")
        return raw

    @staticmethod
    def _integer_unbounded(value: object, label: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{label} must be an integer")
        return value

    @classmethod
    def _integer(cls, value: object, label: str, minimum: int, maximum: int) -> int:
        number = cls._integer_unbounded(value, label)
        if number < minimum or number > maximum:
            raise ValueError(f"{label} must be between {minimum} and {maximum}")
        return number

    @staticmethod
    def _number(value: object, label: str, minimum: float, maximum: float) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{label} must be a number")
        number = float(value)
        if number < minimum or number > maximum:
            raise ValueError(f"{label} must be between {minimum} and {maximum}")
        return number
