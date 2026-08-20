"""A tiny, peaceful pygame scene starring Kadoka and Maru."""

from __future__ import annotations

import argparse
import json
import math
import random
from pathlib import Path

import pygame


VERSION = "0.1.0-beta.1"
WIDTH = 960
HEIGHT = 540
FPS = 60
TAU = math.tau
ASSET_DIR = Path(__file__).resolve().parent / "assets"
CONVERSATION_PATH = Path(__file__).resolve().parent / "conversations.json"
PLACED_OBJECTS_PATH = Path(__file__).resolve().parent / "placed_objects.json"
SPRING_RECT = pygame.Rect(410, 408, 204, 48)
SPRING_REST_AREA = SPRING_RECT.inflate(150, 120)
CONVERSATION_DISTANCE = 145.0


def load_legacy_conversation_deck() -> list[dict[str, str]]:
    """Load editable dialogue data, ignoring malformed entries safely."""
    try:
        raw = json.loads(CONVERSATION_PATH.read_text(encoding="utf-8"))
        deck = []
        for item in raw:
            if (
                isinstance(item, dict)
                and isinstance(item.get("kadoka"), str)
                and isinstance(item.get("maru"), str)
                and item["kadoka"].strip()
                and item["maru"].strip()
            ):
                entry = {
                    "kadoka": " ".join(item["kadoka"].split()),
                    "maru": " ".join(item["maru"].split()),
                }
                if item.get("event") in ("water_bath", "game_device"):
                    entry["event"] = item["event"]
                deck.append(entry)
        if deck:
            return deck
    except (OSError, ValueError, TypeError):
        pass
    return [{"kadoka": "しずかだね", "maru": "しずかなのだ〜"}]


def normalize_conversation_step(raw: object) -> dict[str, str] | None:
    if not isinstance(raw, dict):
        return None
    step_type = str(raw.get("type", "say"))
    if step_type == "say":
        speaker = str(raw.get("speaker", "kadoka"))
        text = " ".join(str(raw.get("text", "")).split())
        if speaker in ("kadoka", "maru") and text:
            return {"type": "say", "speaker": speaker, "text": text}
    elif step_type in ("move", "take", "put"):
        actor = str(raw.get("actor", "kadoka"))
        tag = str(raw.get("tag", "")).strip()
        if actor in ("kadoka", "maru", "both") and tag:
            return {"type": step_type, "actor": actor, "tag": tag}
    elif step_type == "event" and raw.get("event") in ("water_bath", "game_device"):
        return {"type": "event", "event": str(raw["event"])}
    return None


def load_conversation_deck() -> list[dict[str, object]]:
    """Load step conversations and transparently upgrade the old pair format."""
    try:
        raw = json.loads(CONVERSATION_PATH.read_text(encoding="utf-8"))
        deck: list[dict[str, object]] = []
        for item in raw if isinstance(raw, list) else []:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("steps"), list):
                steps = [
                    step
                    for raw_step in item["steps"]
                    if (step := normalize_conversation_step(raw_step)) is not None
                ]
            else:
                steps = []
                for speaker in ("kadoka", "maru"):
                    text = " ".join(str(item.get(speaker, "")).split())
                    if text:
                        steps.append({"type": "say", "speaker": speaker, "text": text})
                if item.get("event") in ("water_bath", "game_device"):
                    steps.append({"type": "event", "event": str(item["event"])})
            if steps:
                try:
                    weight = max(1.0, min(999.0, float(item.get("weight", 1))))
                except (TypeError, ValueError):
                    weight = 1.0
                deck.append({"weight": weight, "steps": steps})
        if deck:
            return deck
    except (OSError, ValueError, TypeError):
        pass
    return [{"weight": 1.0, "steps": [
        {"type": "say", "speaker": "kadoka", "text": "しずかだね"},
        {"type": "say", "speaker": "maru", "text": "しずかなのだ"},
    ]}]


class HabitatObject:
    """A tagged habitat placement whose visibility can change during a scene."""

    def __init__(self, item: dict, image: pygame.Surface, rect: pygame.Rect) -> None:
        self.id = str(item.get("id", ""))
        self.name = str(item.get("name", "object"))
        self.tag = str(item.get("tag", "")).strip()
        self.image = image
        self.rect = rect
        self.home_center = pygame.Vector2(rect.center)
        self.visible = bool(item.get("visible", True))
        self.glowing = False

    @property
    def center(self) -> pygame.Vector2:
        return pygame.Vector2(self.rect.center)

    def take_out(self, position: pygame.Vector2, facing: int) -> None:
        self.visible = True
        self.glowing = False
        self.rect.center = (round(position.x + facing * 42), round(position.y + 18))

    def put_away(self) -> None:
        self.visible = False
        self.glowing = False

    def draw(self, surface: pygame.Surface) -> None:
        if self.visible:
            surface.blit(self.image, self.rect)
            if self.glowing:
                color = (202, 194, 126)
                pygame.draw.rect(surface, color, (self.rect.left - 9, self.rect.centery - 1, 6, 2))
                pygame.draw.rect(surface, color, (self.rect.right + 3, self.rect.centery - 1, 6, 2))
                pygame.draw.rect(surface, color, (self.rect.centerx - 1, self.rect.top - 9, 2, 6))


def load_placed_objects() -> list[HabitatObject]:
    """Load user-made habitat objects, ignoring broken entries safely."""
    try:
        raw = json.loads(PLACED_OBJECTS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    project_root = PLACED_OBJECTS_PATH.parent.resolve()
    result: list[HabitatObject] = []
    for item in raw.get("objects", []) if isinstance(raw, dict) else []:
        if not isinstance(item, dict):
            continue
        try:
            image_path = (project_root / str(item["image"])).resolve()
            image_path.relative_to(project_root)
            x = int(item["x"])
            y = int(item["y"])
            display_width = max(4, min(512, int(item["width"])))
            source = pygame.image.load(image_path).convert_alpha()
            display_height = max(
                1,
                round(source.get_height() * display_width / source.get_width()),
            )
            # The editor exports 1024 px originals. Smooth reduction keeps
            # enlarged or reduced habitat objects clean at any display size.
            image = pygame.transform.smoothscale(
                source,
                (display_width, display_height),
            )
            result.append(HabitatObject(item, image, image.get_rect(center=(x, y))))
        except (KeyError, TypeError, ValueError, OSError, pygame.error):
            continue
    return result


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def create_display(fullscreen: bool) -> pygame.Surface:
    """Create a scaled logical display, with a safe software fallback."""
    flags = pygame.SCALED
    if fullscreen:
        flags |= pygame.FULLSCREEN
    try:
        return pygame.display.set_mode((WIDTH, HEIGHT), flags, vsync=1)
    except (pygame.error, TypeError):
        fallback_flags = pygame.FULLSCREEN if fullscreen else 0
        return pygame.display.set_mode((WIDTH, HEIGHT), fallback_flags)


def draw_pixel_rock(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color: tuple[int, int, int],
) -> None:
    """Draw an axis-aligned pixel-art cave boulder."""
    x, y, width, height = rect
    unit = max(3, min(width, height) // 6)
    highlight = tuple(min(255, channel + 10) for channel in color)

    shadow_points = [
        (x + unit, y + height - unit),
        (x + width - unit, y + height - unit),
        (x + width - unit, y + height),
        (x + unit, y + height),
    ]
    pygame.draw.polygon(surface, (5, 7, 14), shadow_points)

    rock_points = [
        (x, y + unit * 3),
        (x + unit, y + unit * 3),
        (x + unit, y + unit * 2),
        (x + unit * 2, y + unit * 2),
        (x + unit * 2, y + unit),
        (x + width - unit * 2, y + unit),
        (x + width - unit * 2, y + unit * 2),
        (x + width - unit, y + unit * 2),
        (x + width - unit, y + unit * 3),
        (x + width, y + unit * 3),
        (x + width, y + height - unit),
        (x + width - unit, y + height - unit),
        (x + width - unit, y + height),
        (x + unit, y + height),
        (x + unit, y + height - unit),
        (x, y + height - unit),
    ]
    pygame.draw.polygon(surface, color, rock_points)
    pygame.draw.rect(
        surface,
        highlight,
        (x + unit * 2, y + unit * 2, max(unit, width // 3), unit),
    )
    pygame.draw.rect(
        surface,
        (8, 10, 18),
        (x + width - unit * 3, y + height - unit * 2, unit * 2, unit),
    )


def make_cave_background() -> pygame.Surface:
    """Build the static cave scene once so the main loop stays lightweight."""
    background = pygame.Surface((WIDTH, HEIGHT)).convert()

    for y in range(0, HEIGHT, 8):
        depth = y / HEIGHT
        color = (
            int(8 + depth * 7),
            int(10 + depth * 8),
            int(20 + depth * 10),
        )
        pygame.draw.rect(background, color, (0, y, WIDTH, 8))

    # Far wall shapes.
    pygame.draw.polygon(
        background,
        (5, 7, 14),
        [(0, 0), (WIDTH, 0), (WIDTH, 48), (900, 62), (820, 52), (745, 73),
         (660, 55), (565, 70), (475, 49), (385, 66), (290, 52), (195, 74),
         (102, 50), (0, 68)],
    )
    pygame.draw.polygon(
        background,
        (7, 9, 17),
        [(0, 0), (82, 0), (92, 103), (72, 178), (88, 253), (65, 329),
         (79, 418), (53, 522), (0, 548)],
    )
    pygame.draw.polygon(
        background,
        (7, 9, 17),
        [(WIDTH, 0), (886, 0), (875, 112), (898, 188), (879, 281),
         (900, 369), (881, 454), (910, 535), (WIDTH, 556)],
    )

    # Stalactites.
    for points in (
        [(128, 0), (176, 0), (176, 32), (168, 32), (168, 64), (160, 64), (160, 104), (152, 104), (152, 64), (144, 64), (144, 32), (128, 32)],
        [(312, 0), (352, 0), (352, 24), (344, 24), (344, 56), (336, 56), (336, 80), (328, 56), (328, 24), (312, 24)],
        [(592, 0), (640, 0), (640, 24), (632, 24), (632, 56), (624, 56), (624, 96), (608, 96), (608, 56), (600, 56), (600, 24), (592, 24)],
        [(760, 0), (808, 0), (808, 32), (800, 32), (800, 72), (792, 72), (792, 112), (784, 112), (784, 72), (776, 72), (776, 32), (760, 32)],
    ):
        pygame.draw.polygon(background, (6, 8, 15), points)

    # The cave floor begins in the middle distance and widens toward the viewer.
    floor_horizon = [
        (0, 286), (96, 274), (192, 282), (288, 268), (384, 279),
        (480, 264), (576, 278), (672, 269), (768, 282), (864, 272), (960, 286),
    ]
    floor_points = floor_horizon + [(WIDTH, HEIGHT), (0, HEIGHT)]
    pygame.draw.polygon(background, (10, 12, 21), floor_points)

    # Soft vignette keeps the center visible while the cave edges stay dark.
    vignette = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for inset in range(0, 112, 8):
        alpha = max(2, 13 - inset // 10)
        pygame.draw.rect(
            vignette,
            (0, 0, 4, alpha),
            pygame.Rect(inset, inset // 2, WIDTH - inset * 2, HEIGHT - inset),
            width=10,
            border_radius=48,
        )
    background.blit(vignette, (0, 0))
    return background


class Mote:
    """A dim dust mote that helps the cave feel gently alive."""

    def __init__(self, rng: random.Random) -> None:
        self.rng = rng
        self.x = rng.uniform(85, WIDTH - 85)
        self.y = rng.uniform(85, 520)
        self.speed = rng.uniform(2.0, 8.0)
        self.phase = rng.uniform(0, TAU)
        self.radius = rng.choice((1, 1, 1, 2))
        self.alpha = rng.randint(18, 45)

    def update(self, dt: float, elapsed: float) -> None:
        self.y -= self.speed * dt
        self.x += math.sin(elapsed * 0.45 + self.phase) * 2.2 * dt
        if self.y < 72:
            self.y = self.rng.uniform(500, 545)
            self.x = self.rng.uniform(85, WIDTH - 85)

    def draw(self, surface: pygame.Surface) -> None:
        layer = pygame.Surface((self.radius * 4, self.radius * 4), pygame.SRCALPHA)
        pygame.draw.rect(
            layer,
            (146, 160, 175, self.alpha),
            (self.radius, self.radius, self.radius * 2, self.radius * 2),
        )
        surface.blit(layer, (int(self.x) - self.radius * 2, int(self.y) - self.radius * 2))


class Ghost:
    """Autonomous floating, pausing, bouncing, somersaulting ghost."""

    def __init__(
        self,
        image_path: Path,
        position: tuple[float, float],
        target_height: int,
        rng: random.Random,
        personality: float,
        native_facing: int = 1,
        name: str = "ghost",
        conversation_deck: list[dict[str, object]] | None = None,
        habitat_objects: list[HabitatObject] | None = None,
    ) -> None:
        source = pygame.image.load(image_path).convert_alpha()
        visible_bounds = source.get_bounding_rect(min_alpha=1)
        if visible_bounds.width and visible_bounds.height:
            source = source.subsurface(visible_bounds).copy()
        target_width = max(1, round(source.get_width() * target_height / source.get_height()))
        self.image = pygame.transform.smoothscale(source, (target_width, target_height))
        self.position = pygame.Vector2(position)
        self.rng = rng
        self.personality = personality
        self.native_facing = 1 if native_facing >= 0 else -1
        self.name = name
        self.conversation_deck = conversation_deck or load_conversation_deck()
        self.habitat_objects = habitat_objects if habitat_objects is not None else []

        if rng.random() < 0.78:
            angle = rng.choice((0.0, math.pi)) + rng.uniform(-0.38, 0.38)
        else:
            angle = rng.uniform(0, TAU)
        speed = rng.uniform(22.0, 39.0) * personality
        self.velocity = pygame.Vector2(math.cos(angle), math.sin(angle)) * speed
        self.desired_velocity = self.velocity.copy()
        self.pending_velocity = self.velocity.copy()
        self.current_action = "forward"
        self.action_timer = rng.uniform(1.5, 6.0)
        self.steering_speed = rng.uniform(0.55, 2.2)
        self.talk_text = ""
        self.talk_cooldown = rng.uniform(3.0, 9.0)
        self.talk_bubble_offset = 0
        self.talk_bubble_y_offset = 0
        self.click_target: pygame.Vector2 | None = None
        self.talk_target: Ghost | None = None
        self.talk_side = -1
        self.arrival_action = "stop"
        self.pending_event: str | None = None
        self.event_owner = False
        self.script_stage = 0
        self.script_timer = 0.0
        self.sequence_steps: list[dict[str, str]] = []
        self.sequence_index = 0
        self.sequence_movers: set[str] = set()

        # The source art has a visible light/shadow side. Mirroring it makes a
        # real turn readable even though both drawings mostly face the viewer.
        self.facing = 1 if self.velocity.x >= 0.0 else -1
        self.turning = False
        self.turn_target = self.facing
        self.turn_elapsed = 0.0
        self.turn_duration = 0.58
        self.turn_scale = 1.0

        self.bob_phase = rng.uniform(0, TAU)
        self.bob_speed = rng.uniform(0.17, 0.29) * personality
        self.bob_height = rng.uniform(3.5, 6.5)

        self.spin_elapsed: float | None = None
        self.spin_duration = 1.0
        self.spin_direction = 1
        self.spin_angle = 0.0
        self.spin_offset = pygame.Vector2()
        self.spin_radius = pygame.Vector2(72.0, 88.0)
        self.spin_travel = 150.0
        self.spin_progress = 0.0

    @property
    def half_width(self) -> float:
        return self.image.get_width() * 0.5

    @property
    def half_height(self) -> float:
        return self.image.get_height() * 0.5

    def random_speed(self) -> float:
        speed_roll = self.rng.random()
        if speed_roll < 0.28:
            speed = self.rng.uniform(7.0, 15.0)
        else:
            speed = self.rng.uniform(17.0, 38.0)
        return speed * self.personality

    def can_seek_conversation(self, partner: "Ghost | None") -> bool:
        return (
            partner is not None
            and self.talk_cooldown <= 0.0
            and partner.talk_cooldown <= 0.0
            and not self.turning
            and not partner.turning
            and self.spin_elapsed is None
            and partner.spin_elapsed is None
            and self.current_action not in (
                "talk", "talk_turn", "talk_align", "talk_wait_align",
                "talk_pause", "seek_talk", "talk_sequence", "sequence_move",
                "sequence_wait", "sequence_pause",
            )
            and partner.current_action not in (
                "talk", "talk_turn", "talk_align", "talk_wait_align",
                "talk_pause", "seek_talk", "loop", "turn", "approach",
                "talk_sequence", "sequence_move", "sequence_wait", "sequence_pause",
            )
        )

    def seek_conversation(self, partner: "Ghost") -> None:
        """Approach the other ghost; only the initiator changes behavior."""
        self.current_action = "seek_talk"
        self.talk_target = partner
        self.talk_side = -1 if self.position.x <= partner.position.x else 1
        self.talk_text = ""
        self.action_timer = 18.0

    def prepare_talking(self, partner: "Ghost") -> None:
        """Begin: turn, align horizontally, pause, then finally speak."""
        for ghost, target in ((self, partner), (partner, self)):
            # The other ghost is allowed to wander until approached, so it may
            # have begun a loop or turn in the meantime. Finish that old motion
            # before entering the conversation choreography.
            if ghost.spin_elapsed is not None:
                ghost.position += ghost.spin_offset
            ghost.spin_elapsed = None
            ghost.spin_angle = 0.0
            ghost.spin_progress = 0.0
            ghost.spin_offset.update(0.0, 0.0)
            ghost.turning = False
            ghost.turn_scale = 1.0
            ghost.click_target = None
            ghost.current_action = "talk_turn"
            ghost.talk_target = target
            ghost.talk_text = ""
            ghost.action_timer = 4.0
            ghost.velocity.update(0.0, 0.0)
            ghost.desired_velocity.update(0.0, 0.0)
            ghost.pending_velocity.update(0.0, 0.0)
            ghost.face_toward(target)
        self.event_owner = True
        partner.event_owner = False

    def start_talking(self, partner: "Ghost", bounds: pygame.Rect) -> None:
        entry = self.rng.choices(
            self.conversation_deck,
            weights=[float(item.get("weight", 1.0)) for item in self.conversation_deck],
            k=1,
        )[0]
        self.sequence_steps = list(entry.get("steps", []))
        self.sequence_index = 0
        self.sequence_movers.clear()
        for ghost, target in ((self, partner), (partner, self)):
            ghost.current_action = "sequence_wait"
            ghost.talk_target = target
            ghost.talk_text = ""
            ghost.talk_cooldown = self.rng.uniform(12.0, 24.0)
            ghost.talk_bubble_y_offset = -34 if ghost.name == "maru" else 0
            ghost.pending_event = None
            ghost.event_owner = ghost is self
            ghost.velocity.update(0.0, 0.0)
            ghost.desired_velocity.update(0.0, 0.0)
            ghost.pending_velocity.update(0.0, 0.0)
            ghost.face_toward(target)
        if self.position.x <= partner.position.x:
            self.talk_bubble_offset = -28
            partner.talk_bubble_offset = 28
        else:
            self.talk_bubble_offset = 28
            partner.talk_bubble_offset = -28
        self.run_next_conversation_step(partner, bounds)

    def tagged_object(self, tag: str) -> HabitatObject | None:
        return next((item for item in self.habitat_objects if item.tag == tag), None)

    def sequence_actors(self, actor: str, partner: "Ghost") -> list["Ghost"]:
        ghosts = [self, partner]
        if actor == "both":
            return ghosts
        return [next((ghost for ghost in ghosts if ghost.name == actor), self)]

    def finish_conversation_sequence(self, partner: "Ghost", bounds: pygame.Rect) -> None:
        for ghost in (self, partner):
            ghost.talk_text = ""
            ghost.talk_target = None
            ghost.event_owner = False
            ghost.sequence_movers.clear()
            ghost.begin_random_action(bounds, partner if ghost is self else self)
        self.sequence_steps = []
        self.sequence_index = 0

    def run_next_conversation_step(
        self,
        partner: "Ghost",
        bounds: pygame.Rect | None = None,
    ) -> None:
        """Execute steps until one needs time or movement to finish."""
        while self.sequence_index < len(self.sequence_steps):
            step = self.sequence_steps[self.sequence_index]
            self.sequence_index += 1
            step_type = step.get("type")
            if step_type == "say":
                speaker = step.get("speaker", "kadoka")
                text = step.get("text", "…")
                duration = clamp(1.8 + len(text) * 0.10, 2.2, 5.5)
                for ghost in (self, partner):
                    ghost.current_action = "talk_sequence"
                    ghost.action_timer = duration
                    ghost.talk_text = text if ghost.name == speaker else ""
                    ghost.velocity.update(0.0, 0.0)
                return

            if step_type == "event" and bounds is not None:
                self.sequence_steps = []
                self.begin_scripted_event(step.get("event", ""), partner, bounds)
                return

            if step_type in ("move", "take", "put"):
                target_object = self.tagged_object(step.get("tag", ""))
                if target_object is None:
                    continue
                actors = self.sequence_actors(step.get("actor", "kadoka"), partner)
                if step_type == "move" and bounds is not None:
                    self.sequence_movers = {ghost.name for ghost in actors}
                    spacing = 54 if len(actors) > 1 else 42
                    destination = target_object.center if target_object.visible else target_object.home_center
                    for index, ghost in enumerate(actors):
                        offset = (index * 2 - (len(actors) - 1)) * spacing
                        ghost.go_to(
                            (round(destination.x + offset), round(destination.y - 38)),
                            bounds,
                            travel_action="sequence_move",
                            arrival_action="sequence_wait",
                        )
                        ghost.talk_target = partner if ghost is self else self
                    for ghost in (self, partner):
                        if ghost not in actors:
                            ghost.current_action = "sequence_wait"
                            ghost.velocity.update(0.0, 0.0)
                    return
                if step_type == "take":
                    actor = actors[0]
                    target_object.take_out(actor.position, actor.facing)
                else:
                    target_object.put_away()
                for ghost in (self, partner):
                    ghost.current_action = "sequence_pause"
                    ghost.action_timer = 0.8
                    ghost.talk_text = ""
                    ghost.velocity.update(0.0, 0.0)
                return

        if bounds is not None:
            self.finish_conversation_sequence(partner, bounds)

    def face_toward(self, partner: "Ghost") -> None:
        target_facing = 1 if partner.position.x >= self.position.x else -1
        if target_facing == self.facing:
            return
        self.pending_velocity.update(0.0, 0.0)
        self.turn_target = target_facing
        self.turn_elapsed = 0.0
        self.turn_duration = self.rng.uniform(0.42, 0.62)
        self.turning = True

    def begin_random_action(
        self,
        bounds: pygame.Rect,
        partner: "Ghost | None" = None,
    ) -> None:
        """Choose one action; conversation begins by approaching a partner."""
        being_approached = (
            partner is not None
            and partner.current_action == "seek_talk"
            and partner.talk_target is self
        )
        self.talk_target = None
        if self.personality < 1.0:
            actions = (
                "stop", "stop", "forward", "forward", "forward", "forward",
                "turn", "loop", "dash", "dash",
            )
        else:
            actions = (
                "stop", "forward", "forward", "forward", "forward", "turn",
                "loop", "dash", "dash", "dash",
            )

        if being_approached:
            actions = tuple(action for action in actions if action != "loop")

        if self.can_seek_conversation(partner):
            actions += ("seek_talk", "seek_talk")
        if SPRING_REST_AREA.collidepoint(self.position):
            actions += ("water_stop", "water_stop")

        action = self.rng.choice(actions)
        if action == "seek_talk" and partner is not None:
            self.seek_conversation(partner)
            return
        if action == "water_stop":
            self.current_action = "water_stop"
            self.action_timer = self.rng.uniform(2.5, 6.5)
            self.talk_text = ""
            return
        if action == "loop":
            if self.start_spin(bounds):
                self.current_action = "loop"
                self.action_timer = self.spin_duration
                return
            action = self.rng.choice(("stop", "forward", "forward", "dash"))

        self.current_action = action
        if action == "stop":
            self.action_timer = (
                self.rng.uniform(1.1, 5.2)
                if self.personality < 1.0
                else self.rng.uniform(0.35, 2.8)
            )
            return

        if action == "forward":
            heading = (
                self.desired_velocity.normalize()
                if self.desired_velocity.length_squared() > 0.1
                else pygame.Vector2(self.facing, 0.0)
            )
            self.desired_velocity = heading * self.random_speed()
            self.pending_velocity = self.desired_velocity.copy()
            self.steering_speed = self.rng.uniform(0.55, 1.8)
            self.action_timer = self.rng.uniform(1.4, 7.5)
            return

        if action == "dash":
            heading = (
                self.desired_velocity.normalize()
                if self.desired_velocity.length_squared() > 0.1
                else pygame.Vector2(self.facing, 0.0)
            )
            self.desired_velocity = (
                heading * self.rng.uniform(110.0, 160.0) * self.personality
            )
            self.pending_velocity = self.desired_velocity.copy()
            self.steering_speed = self.rng.uniform(4.0, 6.5)
            self.action_timer = self.rng.uniform(0.65, 1.7)
            return

        # The cave is much wider than it is tall. Most new headings therefore
        # travel broadly left or right, without targeting whichever edge is near.
        if self.rng.random() < 0.78:
            base_angle = self.rng.choice((0.0, math.pi))
            angle = base_angle + self.rng.uniform(-0.38, 0.38)
        else:
            angle = self.rng.uniform(0.0, TAU)
        target = pygame.Vector2(math.cos(angle), math.sin(angle)) * self.random_speed()

        self.steering_speed = self.rng.uniform(0.45, 2.6)
        self.set_motion_target(target)
        self.action_timer = self.rng.uniform(0.7, 1.8)

    def set_motion_target(self, target: pygame.Vector2) -> None:
        """Turn first when the next movement would otherwise be backwards."""
        target_facing = self.facing
        if target.x > 3.0:
            target_facing = 1
        elif target.x < -3.0:
            target_facing = -1

        if target_facing != self.facing:
            self.pending_velocity = target.copy()
            self.turn_target = target_facing
            self.turn_elapsed = 0.0
            self.turn_duration = self.rng.uniform(0.48, 0.72)
            self.turning = True
        else:
            self.desired_velocity = target.copy()
            self.pending_velocity = target.copy()

    def go_to(
        self,
        point: tuple[int, int],
        bounds: pygame.Rect,
        travel_action: str = "approach",
        arrival_action: str = "stop",
    ) -> None:
        """Interrupt the current action and move toward a fixed point."""
        if self.spin_elapsed is not None:
            self.position += self.spin_offset
            self.spin_elapsed = None
            self.spin_angle = 0.0
            self.spin_progress = 0.0
            self.spin_offset.update(0.0, 0.0)

        target = pygame.Vector2(
            clamp(point[0], bounds.left + self.half_width, bounds.right - self.half_width),
            clamp(point[1], bounds.top + self.half_height, bounds.bottom - self.half_height),
        )
        self.click_target = target
        self.talk_target = None
        self.current_action = travel_action
        self.arrival_action = arrival_action
        self.talk_text = ""
        self.action_timer = 30.0
        self.turning = False

        direction = target - self.position
        if direction.length_squared() > 1.0:
            self.steering_speed = 2.4
            self.set_motion_target(direction.normalize() * 46.0 * self.personality)

    def flee_from(self, source: "Ghost", bounds: pygame.Rect) -> None:
        direction_sign = 1 if self.position.x >= source.position.x else -1
        target_x = (
            bounds.right - self.half_width
            if direction_sign > 0
            else bounds.left + self.half_width
        )
        target_y = clamp(
            self.position.y + self.rng.uniform(-100.0, 100.0),
            bounds.top + self.half_height,
            bounds.bottom - self.half_height,
        )
        self.go_to(
            (round(target_x), round(target_y)),
            bounds,
            travel_action="flee",
            arrival_action="stop",
        )
        direction = self.click_target - self.position
        if direction.length_squared() > 1.0:
            self.steering_speed = 7.0
            self.set_motion_target(direction.normalize() * 175.0)

    def begin_scripted_event(
        self,
        event_name: str,
        partner: "Ghost",
        bounds: pygame.Rect,
    ) -> None:
        self.pending_event = None
        partner.pending_event = None
        if event_name == "water_bath":
            kadoka = self if self.name == "kadoka" else partner
            maru = self if self.name == "maru" else partner
            kadoka.go_to(
                (458, 420),
                bounds,
                travel_action="event_move",
                arrival_action="water_bath",
            )
            maru.go_to(
                (566, 420),
                bounds,
                travel_action="event_move",
                arrival_action="water_bath",
            )
            return

        if event_name == "game_device":
            kadoka = self if self.name == "kadoka" else partner
            maru = self if self.name == "maru" else partner
            device = kadoka.tagged_object("game_device")
            if device is not None:
                device.put_away()
            maru.current_action = "script"
            maru.script_stage = 0
            maru.script_timer = 0.8
            maru.talk_text = ""
            kadoka.current_action = "script_wait"
            kadoka.action_timer = 30.0
            kadoka.talk_text = ""
            kadoka.velocity.update(0.0, 0.0)
            maru.velocity.update(0.0, 0.0)

    def update_script(
        self,
        dt: float,
        bounds: pygame.Rect,
        partner: "Ghost | None",
    ) -> None:
        self.velocity = self.velocity.lerp(pygame.Vector2(), min(1.0, dt * 6.0))
        if partner is None:
            return
        self.script_timer -= dt
        if self.script_timer > 0.0:
            return
        if self.script_stage == 0:
            self.script_stage = 1
            self.script_timer = 1.2
            device = self.tagged_object("game_device")
            if device is not None:
                device.take_out(self.position, self.facing)
                device.glowing = True
            self.talk_text = "ピカーン"
        elif self.script_stage == 1:
            self.script_stage = 2
            self.script_timer = 2.4
            self.talk_text = "まぶしいのだーーー"
            partner.talk_text = "まぶしい"
        else:
            device = self.tagged_object("game_device")
            if device is not None:
                device.glowing = False
            self.talk_text = ""
            partner.talk_text = ""
            left_ghost, right_ghost = sorted(
                (self, partner), key=lambda ghost: ghost.position.x
            )
            left_ghost.go_to(
                (bounds.left + left_ghost.half_width, left_ghost.position.y),
                bounds,
                travel_action="flee",
                arrival_action="stop",
            )
            right_ghost.go_to(
                (bounds.right - right_ghost.half_width, right_ghost.position.y),
                bounds,
                travel_action="flee",
                arrival_action="stop",
            )
            for ghost in (left_ghost, right_ghost):
                direction = ghost.click_target - ghost.position
                if direction.length_squared() > 1.0:
                    ghost.steering_speed = 7.0
                    ghost.set_motion_target(direction.normalize() * 175.0)

    def start_spin(self, bounds: pygame.Rect) -> bool:
        """Begin a slow travelling loop when there is space around the ghost."""
        forward_edge = (
            bounds.right - self.half_width
            if self.facing > 0
            else bounds.left + self.half_width
        )
        forward_room = (forward_edge - self.position.x) * self.facing
        top_room = self.position.y - (bounds.top + self.half_height)
        if (
            forward_room < 115.0
            or top_room < 164.0
            or self.turning
        ):
            return False

        self.spin_elapsed = 0.0
        self.spin_duration = self.rng.uniform(5.8, 8.2)
        self.spin_direction = self.facing
        self.spin_progress = 0.0
        self.spin_travel = min(self.rng.uniform(135.0, 175.0), forward_room - 8.0)
        self.spin_radius.update(
            self.rng.uniform(62.0, 78.0),
            min(self.rng.uniform(78.0, 98.0), (top_room - 4.0) * 0.5),
        )
        return True

    def update_turn(self, dt: float) -> None:
        if not self.turning:
            self.turn_scale = 1.0
            return

        self.turn_elapsed += dt
        progress = clamp(self.turn_elapsed / self.turn_duration, 0.0, 1.0)
        # Visually narrow to an edge, switch sides, and open again.
        self.turn_scale = max(0.08, abs(math.cos(progress * math.pi)))
        self.velocity = self.velocity.lerp(pygame.Vector2(), min(1.0, dt * 5.5))
        if progress >= 0.5:
            self.facing = self.turn_target
        if progress >= 1.0:
            self.turning = False
            self.turn_scale = 1.0
            self.desired_velocity = self.pending_velocity.copy()

    def update(
        self,
        dt: float,
        bounds: pygame.Rect,
        partner: "Ghost | None" = None,
    ) -> None:
        self.talk_cooldown = max(0.0, self.talk_cooldown - dt)
        if self.spin_elapsed is not None:
            self.spin_elapsed += dt
            progress = clamp(self.spin_elapsed / self.spin_duration, 0.0, 1.0)
            self.spin_progress = progress
            orbit = progress * TAU
            # A travelling loop: enter along the baseline, make one large loop,
            # then leave farther ahead instead of returning to the start.
            self.spin_offset.update(
                self.facing
                * (self.spin_travel * progress + self.spin_radius.x * math.sin(orbit)),
                -self.spin_radius.y * (1.0 - math.cos(orbit)),
            )
            # Turn with the loop's tangent. Rightward loops rotate CCW on screen;
            # leftward loops are the exact mirror image.
            self.spin_angle = self.spin_direction * 360.0 * progress
            if progress >= 1.0:
                self.position.x += self.facing * self.spin_travel
                self.spin_elapsed = None
                self.spin_angle = 0.0
                self.spin_progress = 0.0
                self.spin_offset.update(0.0, 0.0)
                # Leave every loop as one complete revolution followed by a
                # stretch of forward travel. This also prevents two loops from
                # being selected back-to-back and looking like a double spin.
                self.current_action = "forward"
                self.desired_velocity = pygame.Vector2(
                    self.facing * self.random_speed(),
                    self.rng.uniform(-7.0, 7.0),
                )
                self.pending_velocity = self.desired_velocity.copy()
                self.action_timer = self.rng.uniform(2.5, 5.5)

        self.update_turn(dt)

        if self.turning:
            pass
        elif self.spin_elapsed is not None:
            blend = min(1.0, dt * 1.25)
            self.velocity = self.velocity.lerp(self.desired_velocity, blend)
        elif self.current_action == "script":
            self.update_script(dt, bounds, partner)
        elif self.current_action == "script_wait":
            self.velocity = self.velocity.lerp(pygame.Vector2(), min(1.0, dt * 6.0))
        elif self.current_action == "talk_turn":
            self.velocity = self.velocity.lerp(pygame.Vector2(), min(1.0, dt * 7.0))
            if (
                self.event_owner
                and self.talk_target is not None
                and self.talk_target.current_action == "talk_turn"
                and not self.turning
                and not self.talk_target.turning
            ):
                self.current_action = "talk_align"
                self.talk_target.current_action = "talk_wait_align"
        elif self.current_action == "talk_align" and self.talk_target is not None:
            left = bounds.left + self.half_width
            right = bounds.right - self.half_width
            meeting_point = pygame.Vector2(
                clamp(
                    self.talk_target.position.x
                    + self.talk_side * CONVERSATION_DISTANCE,
                    left,
                    right,
                ),
                self.talk_target.position.y,
            )
            direction = meeting_point - self.position
            if direction.length() <= 2.0:
                self.position = meeting_point
                for ghost in (self, self.talk_target):
                    ghost.current_action = "talk_pause"
                    ghost.action_timer = 0.65
                    ghost.velocity.update(0.0, 0.0)
                    ghost.desired_velocity.update(0.0, 0.0)
                    ghost.pending_velocity.update(0.0, 0.0)
            else:
                self.velocity = direction.normalize() * 28.0
                self.desired_velocity = self.velocity.copy()
                self.pending_velocity = self.velocity.copy()
        elif self.current_action == "talk_wait_align":
            self.velocity = self.velocity.lerp(pygame.Vector2(), min(1.0, dt * 8.0))
        elif self.current_action == "talk_pause":
            self.velocity.update(0.0, 0.0)
            self.action_timer -= dt
            if (
                self.event_owner
                and self.action_timer <= 0.0
                and self.talk_target is not None
                and self.talk_target.current_action == "talk_pause"
            ):
                self.start_talking(self.talk_target, bounds)
            elif (
                not self.event_owner
                and self.action_timer <= -1.0
                and (
                    self.talk_target is None
                    or self.talk_target.current_action != "talk_pause"
                )
            ):
                self.talk_target = None
                self.begin_random_action(bounds, partner)
        elif self.current_action == "talk_sequence":
            self.velocity = self.velocity.lerp(pygame.Vector2(), min(1.0, dt * 8.0))
            self.action_timer -= dt
            if self.event_owner and self.action_timer <= 0.0 and partner is not None:
                for ghost in (self, partner):
                    ghost.talk_text = ""
                    ghost.current_action = "sequence_wait"
                self.run_next_conversation_step(partner, bounds)
        elif self.current_action == "sequence_pause":
            self.velocity = self.velocity.lerp(pygame.Vector2(), min(1.0, dt * 8.0))
            self.action_timer -= dt
            if self.event_owner and self.action_timer <= 0.0 and partner is not None:
                for ghost in (self, partner):
                    ghost.current_action = "sequence_wait"
                self.run_next_conversation_step(partner, bounds)
        elif self.current_action == "sequence_wait":
            self.velocity = self.velocity.lerp(pygame.Vector2(), min(1.0, dt * 8.0))
            if self.event_owner and partner is not None and self.sequence_movers:
                ghosts = {self.name: self, partner.name: partner}
                if all(
                    ghosts[name].current_action != "sequence_move"
                    for name in self.sequence_movers
                    if name in ghosts
                ):
                    self.sequence_movers.clear()
                    self.run_next_conversation_step(partner, bounds)
        elif self.current_action == "seek_talk" and self.talk_target is not None:
            self.action_timer -= dt
            left = bounds.left + self.half_width
            right = bounds.right - self.half_width
            meeting_x = (
                self.talk_target.position.x
                + self.talk_side * CONVERSATION_DISTANCE
            )
            if meeting_x < left or meeting_x > right:
                self.talk_side *= -1
                meeting_x = (
                    self.talk_target.position.x
                    + self.talk_side * CONVERSATION_DISTANCE
                )
            meeting_point = pygame.Vector2(
                clamp(meeting_x, left, right),
                self.talk_target.position.y,
            )
            direction = meeting_point - self.position
            if direction.length() <= 32.0:
                self.prepare_talking(self.talk_target)
            elif self.action_timer <= 0.0:
                self.talk_cooldown = self.rng.uniform(3.0, 7.0)
                self.begin_random_action(bounds, partner)
            else:
                target_velocity = direction.normalize() * 42.0 * self.personality
                target_facing = 1 if target_velocity.x >= 0.0 else -1
                if target_facing != self.facing:
                    self.set_motion_target(target_velocity)
                else:
                    self.desired_velocity = target_velocity
                    self.pending_velocity = target_velocity.copy()
                self.steering_speed = 2.5
                self.velocity = self.velocity.lerp(
                    self.desired_velocity,
                    min(1.0, dt * self.steering_speed),
                )
        elif self.current_action in ("approach", "event_move", "flee", "sequence_move") and self.click_target is not None:
            direction = self.click_target - self.position
            if direction.length() <= 10.0:
                self.position = self.click_target.copy()
                self.click_target = None
                if self.arrival_action == "water_bath":
                    self.current_action = "water_bath"
                    self.action_timer = self.rng.uniform(4.0, 8.0)
                elif self.arrival_action == "sequence_wait":
                    self.current_action = "sequence_wait"
                    self.action_timer = 30.0
                else:
                    self.current_action = "stop"
                    self.action_timer = self.rng.uniform(0.35, 0.9)
                self.velocity.update(0.0, 0.0)
                self.desired_velocity.update(0.0, 0.0)
            else:
                travel_speed = {
                    "approach": 46.0 * self.personality,
                    "event_move": 52.0 * self.personality,
                    "flee": 175.0,
                    "sequence_move": 52.0 * self.personality,
                }[self.current_action]
                target_velocity = direction.normalize() * travel_speed
                target_facing = 1 if target_velocity.x >= 0.0 else -1
                if target_facing != self.facing:
                    self.set_motion_target(target_velocity)
                else:
                    self.desired_velocity = target_velocity
                    self.pending_velocity = target_velocity.copy()
                self.velocity = self.velocity.lerp(
                    self.desired_velocity,
                    min(1.0, dt * self.steering_speed),
                )
        elif self.current_action in ("stop", "talk", "water_stop", "water_bath"):
            finished_action = self.current_action
            if (
                finished_action == "water_bath"
                and partner is not None
                and partner.current_action == "water_bath"
                and not self.turning
            ):
                self.face_toward(partner)
            self.action_timer -= dt
            blend = min(1.0, dt * 5.0)
            self.velocity = self.velocity.lerp(pygame.Vector2(), blend)
            if self.action_timer <= 0.0:
                self.talk_text = ""
                if (
                    finished_action == "talk"
                    and self.pending_event
                    and partner is not None
                ):
                    if self.event_owner:
                        self.begin_scripted_event(self.pending_event, partner, bounds)
                    else:
                        self.current_action = "script_wait"
                        self.action_timer = 30.0
                else:
                    self.pending_event = None
                    self.begin_random_action(bounds, partner)
        else:
            self.action_timer -= dt
            if self.action_timer <= 0.0:
                self.begin_random_action(bounds, partner)

            if self.current_action not in ("stop", "loop"):
                blend = min(1.0, dt * self.steering_speed)
                self.velocity = self.velocity.lerp(self.desired_velocity, blend)

        # The loop path already carries the ghost forward, so do not add the
        # ordinary drift on top of it.
        travel_scale = 0.0 if self.spin_elapsed is not None else 1.0
        self.position += self.velocity * dt * travel_scale
        self._reflect_from_walls(bounds)

    def _reflect_from_walls(self, bounds: pygame.Rect) -> None:
        left = bounds.left + self.half_width
        right = bounds.right - self.half_width
        top = bounds.top + self.half_height
        bottom = bounds.bottom - self.half_height

        if self.position.x < left:
            self.position.x = left
            reflected = self.desired_velocity.copy()
            reflected.x = abs(reflected.x) or 20.0
            self.velocity.x = 0.0
            self.current_action = "turn"
            self.action_timer = self.rng.uniform(0.7, 1.8)
            self.set_motion_target(reflected)
        elif self.position.x > right:
            self.position.x = right
            reflected = self.desired_velocity.copy()
            reflected.x = -(abs(reflected.x) or 20.0)
            self.velocity.x = 0.0
            self.current_action = "turn"
            self.action_timer = self.rng.uniform(0.7, 1.8)
            self.set_motion_target(reflected)

        if self.position.y < top:
            self.position.y = top
            self.velocity.y = abs(self.velocity.y)
            self.desired_velocity.y = abs(self.desired_velocity.y)
            self.current_action = "turn"
            self.action_timer = self.rng.uniform(0.7, 1.8)
        elif self.position.y > bottom:
            self.position.y = bottom
            self.velocity.y = -abs(self.velocity.y)
            self.desired_velocity.y = -abs(self.desired_velocity.y)
            self.current_action = "turn"
            self.action_timer = self.rng.uniform(0.7, 1.8)

    def draw(
        self,
        surface: pygame.Surface,
        elapsed: float,
        talk_font: pygame.font.Font,
    ) -> None:
        bob = math.sin(elapsed * self.bob_speed * TAU + self.bob_phase) * self.bob_height
        draw_position = self.position + self.spin_offset + pygame.Vector2(0.0, bob)

        shadow_width = int(self.image.get_width() * 0.58)
        shadow_height = max(5, int(self.image.get_height() * 0.08))
        shadow = pygame.Surface((shadow_width, shadow_height), pygame.SRCALPHA)
        pygame.draw.rect(
            shadow,
            (0, 0, 5, 46),
            (shadow_width // 6, 0, shadow_width * 4 // 6, shadow_height),
        )
        pygame.draw.rect(
            shadow,
            (0, 0, 5, 34),
            (0, shadow_height // 3, shadow_width, max(2, shadow_height // 3)),
        )
        shadow_y = int(self.position.y + self.half_height + 19)
        surface.blit(shadow, (int(self.position.x - shadow_width / 2), shadow_y))

        tilt = clamp(-self.velocity.x * 0.08, -5.5, 5.5)
        facing_image = pygame.transform.flip(
            self.image,
            self.facing != self.native_facing,
            False,
        )
        if self.turn_scale < 0.999:
            turned_width = max(1, round(facing_image.get_width() * self.turn_scale))
            facing_image = pygame.transform.scale(
                facing_image,
                (turned_width, facing_image.get_height()),
            )
        rendered = pygame.transform.rotate(facing_image, self.spin_angle + tilt)
        rect = rendered.get_rect(center=(round(draw_position.x), round(draw_position.y)))
        surface.blit(rendered, rect)

        if self.current_action in ("talk", "talk_sequence", "script", "script_wait") and self.talk_text:
            text_surface = talk_font.render(self.talk_text, True, (25, 27, 34))
            bubble = text_surface.get_rect()
            bubble.inflate_ip(16, 10)
            bubble.midbottom = (
                rect.centerx + self.talk_bubble_offset,
                rect.top - 8 + self.talk_bubble_y_offset,
            )
            bubble.clamp_ip(surface.get_rect().inflate(-12, -12))
            pygame.draw.rect(surface, (225, 226, 218), bubble)
            pygame.draw.rect(surface, (91, 94, 101), bubble, 2)
            tail_x = max(bubble.left + 8, min(rect.centerx, bubble.right - 8))
            pygame.draw.polygon(
                surface,
                (225, 226, 218),
                [(tail_x - 5, bubble.bottom), (tail_x + 5, bubble.bottom), (rect.centerx, bubble.bottom + 7)],
            )
            surface.blit(text_surface, text_surface.get_rect(center=bubble.center))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="おばけの住処 - a peaceful pygame scene")
    parser.add_argument(
        "--test-frames",
        type=int,
        default=0,
        help="quit automatically after this many frames (used for verification)",
    )
    parser.add_argument(
        "--screenshot",
        type=Path,
        help="save the final rendered frame as a PNG",
    )
    parser.add_argument("--seed", type=int, default=None, help="optional random seed")
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="start in fullscreen mode",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rng = random.Random(args.seed)
    # Each ghost owns a separate random stream. One ghost's choices never
    # consume or synchronize the other ghost's future behavior.
    kadoka_rng = random.Random(rng.getrandbits(64))
    maru_rng = random.Random(rng.getrandbits(64))
    scenery_rng = random.Random(rng.getrandbits(64))

    pygame.init()
    pygame.display.set_caption(f"おばけの住処 v{VERSION} | Obake no Sumika")
    fullscreen = args.fullscreen
    screen = create_display(fullscreen)
    clock = pygame.time.Clock()

    background = make_cave_background()
    placed_objects = load_placed_objects()
    talk_font = pygame.font.SysFont("Yu Gothic UI,Meiryo", 15)
    conversation_deck = load_conversation_deck()
    movement_bounds = pygame.Rect(74, 80, WIDTH - 148, 446)
    ghosts = [
        Ghost(
            ASSET_DIR / "kadoka.png",
            (320, 340),
            64,
            kadoka_rng,
            0.92,
            name="kadoka",
            conversation_deck=conversation_deck,
            habitat_objects=placed_objects,
        ),
        Ghost(
            ASSET_DIR / "maru.png",
            (640, 340),
            64,
            maru_rng,
            1.08,
            native_facing=-1,
            name="maru",
            conversation_deck=conversation_deck,
            habitat_objects=placed_objects,
        ),
    ]
    motes = [Mote(scenery_rng) for _ in range(34)]

    running = True
    elapsed = 0.0
    frame_count = 0
    click_marker: pygame.Vector2 | None = None
    click_marker_timer = 0.0

    while running:
        if args.test_frames:
            dt = 1.0 / FPS
        else:
            dt = min(clock.tick(FPS) / 1000.0, 0.05)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_F11 or (
                    event.key == pygame.K_RETURN
                    and event.mod & pygame.KMOD_ALT
                ):
                    fullscreen = not fullscreen
                    screen = create_display(fullscreen)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                click_marker = pygame.Vector2(event.pos)
                click_marker_timer = 1.0
                ghosts[0].go_to((event.pos[0] - 24, event.pos[1]), movement_bounds)
                ghosts[1].go_to((event.pos[0] + 24, event.pos[1]), movement_bounds)

        elapsed += dt
        click_marker_timer = max(0.0, click_marker_timer - dt)
        for mote in motes:
            mote.update(dt, elapsed)
        ghosts[0].update(dt, movement_bounds, ghosts[1])
        ghosts[1].update(dt, movement_bounds, ghosts[0])

        screen.blit(background, (0, 0))
        for habitat_object in placed_objects:
            habitat_object.draw(screen)
        for mote in motes:
            mote.draw(screen)
        if click_marker is not None and click_marker_timer > 0.0:
            marker_color = (91, 116, 124)
            marker_x = round(click_marker.x)
            marker_y = round(click_marker.y)
            pygame.draw.rect(screen, marker_color, (marker_x - 10, marker_y - 2, 6, 4))
            pygame.draw.rect(screen, marker_color, (marker_x + 4, marker_y - 2, 6, 4))
            pygame.draw.rect(screen, marker_color, (marker_x - 2, marker_y - 10, 4, 6))
            pygame.draw.rect(screen, marker_color, (marker_x - 2, marker_y + 4, 4, 6))
        for ghost in sorted(ghosts, key=lambda item: item.position.y):
            ghost.draw(screen, elapsed, talk_font)

        pygame.display.flip()
        frame_count += 1

        if args.test_frames and frame_count >= args.test_frames:
            running = False

    if args.screenshot:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        pygame.image.save(screen, args.screenshot)

    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
