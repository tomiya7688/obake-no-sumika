from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).with_name("thresholds.json")


def load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def section(payload: dict[str, object], name: str) -> dict[str, object]:
    value = payload.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"missing section: {name}")
    return value


def number(payload: dict[str, object], key: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number")
    result = float(value)
    if not math.isfinite(result) or result <= 0.0:
        raise ValueError(f"{key} must be a positive finite number")
    return result


def regression_limit(base: float, percent: float, noise_floor: float) -> float:
    if base <= 0.0 or percent <= 0.0 or noise_floor <= 0.0:
        raise ValueError("regression inputs must be positive")
    return base + max(base * percent / 100.0, noise_floor)


def compare_metric(
    name: str,
    base: float,
    head: float,
    percent: float,
    noise_floor: float,
    unit: str,
) -> bool:
    limit = regression_limit(base, percent, noise_floor)
    delta = head - base
    delta_percent = delta / base * 100.0
    passed = head <= limit
    status = "OK" if passed else "FAIL"
    print(
        f"[{status}] {name} regression: "
        f"base={base:.3f}{unit} head={head:.3f}{unit} "
        f"delta={delta:+.3f}{unit} ({delta_percent:+.1f}%) "
        f"limit={limit:.3f}{unit}"
    )
    return passed


def compare_engine(
    base_result: dict[str, object],
    head_result: dict[str, object],
    config: dict[str, object],
) -> bool:
    base = number(section(base_result, "engine"), "median_ms")
    head = number(section(head_result, "engine"), "median_ms")
    settings = section(config, "engine")
    return compare_metric(
        "engine median",
        base,
        head,
        number(settings, "max_regression_percent"),
        number(settings, "regression_noise_floor_ms"),
        "ms",
    )


def compare_game(
    base_result: dict[str, object],
    head_result: dict[str, object],
    config: dict[str, object],
) -> bool:
    base = number(section(base_result, "game"), "median_ms_per_frame")
    head = number(section(head_result, "game"), "median_ms_per_frame")
    settings = section(config, "game")
    return compare_metric(
        "game median",
        base,
        head,
        number(settings, "max_regression_percent"),
        number(settings, "regression_noise_floor_ms"),
        "ms/frame",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare PR runtime performance against its base commit."
    )
    parser.add_argument("--base-engine", type=Path, required=True)
    parser.add_argument("--head-engine", type=Path, required=True)
    parser.add_argument("--base-game", type=Path, required=True)
    parser.add_argument("--head-game", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.config)
    engine_ok = compare_engine(load_json(args.base_engine), load_json(args.head_engine), config)
    game_ok = compare_game(load_json(args.base_game), load_json(args.head_game), config)
    if engine_ok and game_ok:
        print("[OK] runtime regression")
        return 0
    print("[FAIL] runtime regression")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
