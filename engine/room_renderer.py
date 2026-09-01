from __future__ import annotations

import pygame

from .room_definition import RoomDefinition


class RoomRenderer:
    """Render a static room background from a validated definition."""

    def __init__(self, definition: RoomDefinition) -> None:
        self.definition = definition

    def render(self) -> pygame.Surface:
        room = self.definition
        background = pygame.Surface((room.width, room.height)).convert()
        self._draw_gradient(background)
        for color, points in room.polygon_layers:
            pygame.draw.polygon(background, color, points)
        background.blit(self._render_vignette(), (0, 0))
        return background

    def _draw_gradient(self, surface: pygame.Surface) -> None:
        room = self.definition
        for y in range(0, room.height, room.gradient_step):
            depth = y / room.height
            color = tuple(
                int(start + depth * (end - start))
                for start, end in zip(room.gradient_top, room.gradient_bottom)
            )
            pygame.draw.rect(surface, color, (0, y, room.width, room.gradient_step))

    def _render_vignette(self) -> pygame.Surface:
        room = self.definition
        vignette = pygame.Surface((room.width, room.height), pygame.SRCALPHA)
        for inset in range(0, room.vignette_max_inset, room.vignette_step):
            alpha = max(
                room.vignette_min_alpha,
                room.vignette_alpha_start - inset // room.vignette_alpha_divisor,
            )
            pygame.draw.rect(
                vignette,
                (*room.vignette_color, alpha),
                pygame.Rect(
                    inset,
                    inset // 2,
                    room.width - inset * 2,
                    room.height - inset,
                ),
                width=room.vignette_border_width,
                border_radius=room.vignette_radius,
            )
        return vignette
