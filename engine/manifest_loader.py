from __future__ import annotations

import json
from pathlib import Path

from .editor_definition import EditorDefinition
from .project_manifest import ProjectManifest


def resolve_project_path(root: Path, raw_path: object) -> Path:
    """Resolve one manifest path while preventing access outside the project."""
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("Project paths must be non-empty strings")
    root = root.resolve()
    candidate = (root / raw_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"Path escapes the project root: {raw_path}")
    if not candidate.exists():
        raise ValueError(f"Project path does not exist: {raw_path}")
    return candidate


def load_editor_definitions(root: Path, raw_editors: object) -> tuple[EditorDefinition, ...]:
    """Validate and load the editor list."""
    if not isinstance(raw_editors, list):
        raise ValueError("editors must be a list")
    editors = []
    seen_ids = set()
    for raw_editor in raw_editors:
        if not isinstance(raw_editor, dict):
            raise ValueError("Each editor must be an object")
        editor_id = str(raw_editor.get("id", "")).strip()
        label = str(raw_editor.get("label", "")).strip()
        if not editor_id or not label:
            raise ValueError("Editor id and label are required")
        if editor_id in seen_ids:
            raise ValueError(f"Duplicate editor id: {editor_id}")
        script = resolve_project_path(root, raw_editor.get("script"))
        if not script.is_file():
            raise ValueError(f"Editor script is not a file: {script.name}")
        editors.append(EditorDefinition(editor_id, label, script))
        seen_ids.add(editor_id)
    return tuple(editors)


def load_content_paths(root: Path, raw_content: object) -> dict[str, Path]:
    """Validate and load named content locations."""
    if not isinstance(raw_content, dict):
        raise ValueError("content must be an object")
    content = {}
    for raw_name, raw_path in raw_content.items():
        name = str(raw_name).strip()
        if not name:
            raise ValueError("Content names must not be empty")
        content[name] = resolve_project_path(root, raw_path)
    return content


def load_content_manifest(root: Path, raw_manifest_path: object) -> tuple[dict[str, Path], Path | None]:
    """Load game-specific content paths from an optional external manifest."""
    if raw_manifest_path is None:
        return {}, None
    manifest_path = resolve_project_path(root, raw_manifest_path)
    if not manifest_path.is_file():
        raise ValueError("content_manifest must be a file")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("content_manifest must contain an object")
    if raw.get("schema_version") != 1:
        raise ValueError("Unsupported content manifest schema version")
    return load_content_paths(root, raw.get("content", {})), manifest_path


def load_project_type(raw_type: object) -> str:
    """Load a project type label used to keep variants explicit."""
    if raw_type is None:
        return "standard"
    project_type = str(raw_type).strip()
    if not project_type:
        raise ValueError("project_type must not be empty")
    if any(character.isspace() for character in project_type):
        raise ValueError("project_type must not contain whitespace")
    return project_type


def load_project_manifest(manifest_path: Path) -> ProjectManifest:
    """Load and validate one engine project manifest."""
    manifest_path = manifest_path.resolve()
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Project manifest must be an object")
    if raw.get("schema_version") != 1:
        raise ValueError("Unsupported project schema version")
    name = str(raw.get("name", "")).strip()
    if not name:
        raise ValueError("Project name is required")
    project_type = load_project_type(raw.get("project_type"))
    root = manifest_path.parent
    entrypoint = resolve_project_path(root, raw.get("entrypoint"))
    if not entrypoint.is_file():
        raise ValueError("Project entrypoint must be a file")
    editors = load_editor_definitions(root, raw.get("editors", []))
    external_content, content_manifest = load_content_manifest(root, raw.get("content_manifest"))
    inline_content = load_content_paths(root, raw.get("content", {}))
    content = {**external_content, **inline_content}
    return ProjectManifest(1, name, project_type, root, entrypoint, editors, content, content_manifest)
