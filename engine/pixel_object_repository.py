from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image


def safe_object_stem(name: str) -> str:
    """Create a readable filename stem for an editable object."""
    cleaned = re.sub(r"[^0-9A-Za-zぁ-んァ-ヶ一-龠々ー_-]+", "_", name.strip())
    return cleaned.strip("_.") or "object"


class PixelObjectRepository:
    """Persist transparent PNG exports and their editable pixel sources."""

    def __init__(
        self,
        project_root: Path,
        object_dir: Path,
        canvas_sizes: tuple[int, ...],
        export_size: int,
    ) -> None:
        self.project_root = project_root.resolve()
        self.object_dir = object_dir.resolve()
        self.canvas_sizes = canvas_sizes
        self.export_size = export_size
        self._inside_project(self.object_dir)

    def paths_for(self, name: str) -> tuple[Path, Path]:
        stem = safe_object_stem(name)
        return (
            self.object_dir / f"{stem}.png",
            self.object_dir / f"{stem}.source.json",
        )

    def save(
        self,
        name: str,
        canvas_size: int,
        pixels: list[list[str | None]],
    ) -> tuple[Path, Path]:
        image = self.image_from_pixels(canvas_size, pixels).resize(
            (self.export_size, self.export_size),
            Image.Resampling.NEAREST,
        )
        self.object_dir.mkdir(parents=True, exist_ok=True)
        png_path, source_path = self.paths_for(name)
        temporary_png = png_path.with_suffix(".tmp.png")
        temporary_source = source_path.with_suffix(source_path.suffix + ".tmp")
        image.save(temporary_png, "PNG")
        temporary_source.write_text(
            json.dumps(
                {"canvas_size": canvas_size, "pixels": pixels},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary_png.replace(png_path)
        temporary_source.replace(source_path)
        return png_path, source_path

    def load(self, source_path: Path) -> tuple[int, list[list[str | None]]]:
        source_path = source_path.resolve()
        self._inside_project(source_path)
        raw = json.loads(source_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Object source must be an object")
        canvas_size = raw.get("canvas_size")
        pixels = raw.get("pixels")
        self.image_from_pixels(canvas_size, pixels)
        return canvas_size, pixels

    def image_from_pixels(
        self,
        canvas_size: object,
        pixels: object,
    ) -> Image.Image:
        if canvas_size not in self.canvas_sizes or not isinstance(canvas_size, int):
            raise ValueError("Unsupported object canvas size")
        if not isinstance(pixels, list) or len(pixels) != canvas_size:
            raise ValueError("Object pixel rows do not match canvas size")
        image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        rgba = []
        for row in pixels:
            if not isinstance(row, list) or len(row) != canvas_size:
                raise ValueError("Object pixel columns do not match canvas size")
            for value in row:
                if value is None:
                    rgba.append((0, 0, 0, 0))
                    continue
                if not isinstance(value, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
                    raise ValueError("Object colors must use #RRGGBB")
                rgba.append(
                    (
                        int(value[1:3], 16),
                        int(value[3:5], 16),
                        int(value[5:7], 16),
                        255,
                    )
                )
        image.putdata(rgba)
        return image

    def library_images(self, extra_images: list[Path]) -> list[Path]:
        self.object_dir.mkdir(parents=True, exist_ok=True)
        paths = {path.resolve() for path in self.object_dir.glob("*.png")}
        for path in extra_images:
            resolved = path.resolve()
            self._inside_project(resolved)
            if resolved.suffix.lower() == ".png" and resolved.is_file():
                paths.add(resolved)
        return sorted(paths, key=lambda path: (path.stem, path.as_posix()))

    def source_for_image(self, image_path: Path) -> Path:
        image_path = image_path.resolve()
        self._inside_project(image_path)
        return image_path.with_name(f"{image_path.stem}.source.json")

    def _inside_project(self, path: Path) -> None:
        if path != self.project_root and self.project_root not in path.parents:
            raise ValueError(f"Path escapes the project root: {path}")
