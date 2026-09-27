from __future__ import annotations

import argparse
import json
from pathlib import Path

from engine.manifest_loader import load_project_manifest


DEFAULT_MANIFEST = Path(__file__).resolve().parent / "engine_project.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="プロジェクト統合エンジン")
    parser.add_argument("--project", type=Path, default=DEFAULT_MANIFEST)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--validate", action="store_true")
    action.add_argument("--describe", action="store_true", help="プロジェクト構成をJSONで表示")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_project_manifest(args.project)
    if args.validate:
        print(
            f"OK: {manifest.name} / editors={len(manifest.editors)} "
            f"/ content={len(manifest.content)}"
        )
        return 0
    if args.describe:
        def relative(path: Path) -> str:
            return path.relative_to(manifest.root).as_posix()

        description = {
            "name": manifest.name,
            "project_type": manifest.project_type,
            "entrypoint": relative(manifest.entrypoint),
            "editors": [
                {"id": editor.id, "label": editor.label, "script": relative(editor.script)}
                for editor in manifest.editors
            ],
            "content": {name: relative(path) for name, path in manifest.content.items()},
        }
        print(json.dumps(description, ensure_ascii=True, indent=2))
        return 0
    try:
        import tkinter as tk
    except ModuleNotFoundError as exc:
        raise RuntimeError("GUIの起動にはTkinterが必要です。--validate はTkinterなしで実行できます。") from exc
    from engine.main_window import MainWindow
    from engine.process_launcher import ProcessLauncher

    root = tk.Tk()
    MainWindow(root, manifest, ProcessLauncher(manifest))
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
