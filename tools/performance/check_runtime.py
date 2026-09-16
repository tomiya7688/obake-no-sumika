from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from engine.character_repository import CharacterRepository  # noqa: E402
from engine.conversation_repository import ConversationRepository  # noqa: E402
from engine.event_repository import EventRepository  # noqa: E402
from engine.placement_repository import PlacementRepository  # noqa: E402
from engine.room_renderer import RoomRenderer  # noqa: E402
from engine.room_repository import RoomRepository  # noqa: E402

DEFAULT_CONFIG = PROJECT_ROOT / "tools" / "performance" / "thresholds.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "tmp" / "performance" / "latest.json"


def load_config(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("performance config must be a JSON object")
    return payload


def positive_int(section: dict[str, object], key: str) -> int:
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return value


def positive_number(section: dict[str, object], key: str) -> float:
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{key} must be a positive number")
    return float(value)


def config_section(config: dict[str, object], key: str) -> dict[str, object]:
    value = config.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"missing performance config section: {key}")
    return value


def run_engine_pipeline() -> None:
    room = RoomRepository(PROJECT_ROOT / "room.json").load()
    events = EventRepository(PROJECT_ROOT / "events.json").load()
    placements = PlacementRepository(
        PROJECT_ROOT,
        PROJECT_ROOT / "placed_objects.json",
        (room.width, room.height),
    )
    definitions = placements.load()
    available_tags = sorted(definition.tag for definition in definitions if definition.tag)
    EventRepository.validate_required_tags(events, available_tags)
    characters = CharacterRepository(
        PROJECT_ROOT,
        PROJECT_ROOT / "characters.json",
        (room.width, room.height),
    ).load()
    conversations = ConversationRepository(
        PROJECT_ROOT / "conversations.json",
        tuple(definition.id for definition in characters),
        tuple(definition.id for definition in characters) + ("both",),
        tuple(definition.id for definition in events),
    ).load()
    surface = RoomRenderer(room).render()
    if not characters or not conversations or surface.get_size() != (room.width, room.height):
        raise RuntimeError("engine performance probe produced incomplete project state")


def benchmark_engine(section: dict[str, object]) -> dict[str, object]:
    warmup = positive_int(section, "warmup")
    runs = positive_int(section, "runs")
    max_median_ms = positive_number(section, "max_median_ms")
    max_single_ms = positive_number(section, "max_single_ms")

    pygame.init()
    pygame.display.set_mode((1, 1))
    try:
        for _ in range(warmup):
            run_engine_pipeline()

        samples_ms: list[float] = []
        for _ in range(runs):
            started = time.perf_counter()
            run_engine_pipeline()
            samples_ms.append((time.perf_counter() - started) * 1000.0)
    finally:
        pygame.quit()

    median_ms = statistics.median(samples_ms)
    worst_ms = max(samples_ms)
    passed = median_ms <= max_median_ms and worst_ms <= max_single_ms
    print(
        "[PERF] engine "
        f"median={median_ms:.2f}ms worst={worst_ms:.2f}ms "
        f"limits={max_median_ms:.2f}/{max_single_ms:.2f}ms"
    )
    return {
        "passed": passed,
        "median_ms": round(median_ms, 3),
        "worst_ms": round(worst_ms, 3),
        "samples_ms": [round(value, 3) for value in samples_ms],
        "max_median_ms": max_median_ms,
        "max_single_ms": max_single_ms,
    }


def run_game_once(frame_count: int) -> float:
    env = os.environ.copy()
    env.update(
        {
            "SDL_VIDEODRIVER": "dummy",
            "SDL_AUDIODRIVER": "dummy",
            "PYGAME_HIDE_SUPPORT_PROMPT": "1",
        }
    )
    started = time.perf_counter()
    result = subprocess.run(
        [
            sys.executable,
            "game.py",
            "--test-frames",
            str(frame_count),
            "--seed",
            "12345",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.perf_counter() - started
    if result.returncode != 0:
        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
        raise RuntimeError(f"game performance probe failed: exit={result.returncode}")
    return elapsed * 1000.0 / frame_count


def benchmark_game(section: dict[str, object]) -> dict[str, object]:
    frames = positive_int(section, "frames")
    runs = positive_int(section, "runs")
    max_median_ms_per_frame = positive_number(section, "max_median_ms_per_frame")
    max_single_ms_per_frame = positive_number(section, "max_single_ms_per_frame")

    samples_ms_per_frame = [run_game_once(frames) for _ in range(runs)]
    median_ms_per_frame = statistics.median(samples_ms_per_frame)
    worst_ms_per_frame = max(samples_ms_per_frame)
    effective_fps = 1000.0 / median_ms_per_frame
    passed = (
        median_ms_per_frame <= max_median_ms_per_frame
        and worst_ms_per_frame <= max_single_ms_per_frame
    )
    print(
        "[PERF] game "
        f"median={median_ms_per_frame:.3f}ms/frame "
        f"worst={worst_ms_per_frame:.3f}ms/frame "
        f"effective={effective_fps:.1f}fps "
        f"limits={max_median_ms_per_frame:.3f}/{max_single_ms_per_frame:.3f}ms/frame"
    )
    return {
        "passed": passed,
        "frames_per_run": frames,
        "median_ms_per_frame": round(median_ms_per_frame, 4),
        "worst_ms_per_frame": round(worst_ms_per_frame, 4),
        "effective_fps": round(effective_fps, 2),
        "samples_ms_per_frame": [round(value, 4) for value in samples_ms_per_frame],
        "max_median_ms_per_frame": max_median_ms_per_frame,
        "max_single_ms_per_frame": max_single_ms_per_frame,
    }


def write_results(path: Path, results: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check engine and game runtime performance.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--only", choices=("all", "engine", "game"), default="all")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    results: dict[str, dict[str, object]] = {}

    if args.only in ("all", "engine"):
        results["engine"] = benchmark_engine(config_section(config, "engine"))
    if args.only in ("all", "game"):
        results["game"] = benchmark_game(config_section(config, "game"))

    write_results(args.output, results)
    failed = [name for name, value in results.items() if not bool(value.get("passed"))]
    if failed:
        print("[FAIL] runtime performance: " + ", ".join(failed))
        return 1
    print("[OK] runtime performance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
