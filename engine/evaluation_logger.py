from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


class EvaluationLogger:
    """Write compact JSONL snapshots for development-time behavior checks."""

    def __init__(self, path: Path, sample_interval: int = 1) -> None:
        if sample_interval < 1:
            raise ValueError("sample_interval must be 1 or greater")
        self.path = path
        self.sample_interval = sample_interval
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("w", encoding="utf-8")

    def log_frame(
        self,
        frame: int,
        elapsed: float,
        ghosts: Iterable[object],
        objects: Iterable[object],
    ) -> None:
        if frame % self.sample_interval != 0:
            return
        payload = {
            "frame": frame,
            "elapsed": round(elapsed, 4),
            "ghosts": [self._ghost_payload(ghost) for ghost in ghosts],
            "objects": [self._object_payload(item) for item in objects],
        }
        self.file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        self.file.flush()

    def close(self) -> None:
        self.file.close()

    def _ghost_payload(self, ghost: object) -> dict[str, object]:
        position = getattr(ghost, "position")
        velocity = getattr(ghost, "velocity")
        click_target = getattr(ghost, "click_target", None)
        return {
            "name": getattr(ghost, "name", ""),
            "x": round(float(position.x), 3),
            "y": round(float(position.y), 3),
            "vx": round(float(velocity.x), 3),
            "vy": round(float(velocity.y), 3),
            "facing": int(getattr(ghost, "facing", 1)),
            "action": getattr(ghost, "current_action", ""),
            "turning": bool(getattr(ghost, "turning", False)),
            "spin": getattr(ghost, "spin_elapsed", None) is not None,
            "talk": getattr(ghost, "talk_text", ""),
            "target": self._vector_payload(click_target),
        }

    def _object_payload(self, item: object) -> dict[str, object]:
        rect = getattr(item, "rect")
        return {
            "id": getattr(item, "id", ""),
            "tag": getattr(item, "tag", ""),
            "x": int(rect.centerx),
            "y": int(rect.centery),
            "visible": bool(getattr(item, "visible", False)),
            "glowing": bool(getattr(item, "glowing", False)),
        }

    def _vector_payload(self, value: object | None) -> dict[str, float] | None:
        if value is None:
            return None
        return {"x": round(float(value.x), 3), "y": round(float(value.y), 3)}
