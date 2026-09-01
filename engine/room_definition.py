from __future__ import annotations

from dataclasses import dataclass


Color = tuple[int, int, int]
Point = tuple[int, int]
PolygonLayer = tuple[Color, tuple[Point, ...]]


@dataclass(frozen=True)
class RoomDefinition:
    """Validated room geometry, behavior zones, and drawing settings."""

    width: int
    height: int
    fps: int
    movement_bounds: tuple[int, int, int, int]
    water_rest_area: tuple[int, int, int, int]
    conversation_distance: float
    mote_count: int
    mote_x_range: tuple[float, float]
    mote_y_range: tuple[float, float]
    mote_reset_y_range: tuple[float, float]
    mote_top: float
    mote_speed_range: tuple[float, float]
    mote_drift_speed: float
    mote_drift_amount: float
    mote_radii: tuple[int, ...]
    mote_alpha_range: tuple[int, int]
    mote_color: Color
    gradient_top: Color
    gradient_bottom: Color
    gradient_step: int
    polygon_layers: tuple[PolygonLayer, ...]
    vignette_color: Color
    vignette_max_inset: int
    vignette_step: int
    vignette_border_width: int
    vignette_radius: int
    vignette_alpha_start: int
    vignette_alpha_divisor: int
    vignette_min_alpha: int
