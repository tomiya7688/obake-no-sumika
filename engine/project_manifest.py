from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .editor_definition import EditorDefinition


@dataclass(frozen=True)
class ProjectManifest:
    """Validated paths and metadata for one engine project."""

    schema_version: int
    name: str
    project_type: str
    root: Path
    entrypoint: Path
    editors: tuple[EditorDefinition, ...]
    content: dict[str, Path]

    def editor(self, editor_id: str) -> EditorDefinition:
        for editor in self.editors:
            if editor.id == editor_id:
                return editor
        raise KeyError(f"Unknown editor id: {editor_id}")
