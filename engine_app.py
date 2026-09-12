from __future__ import annotations

import argparse
from pathlib import Path

from engine.manifest_loader import load_project_manifest


DEFAULT_MANIFEST = Path(__file__).resolve().parent / "engine_project.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="プロジェクト統合エンジン")
    parser.add_argument("--project", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--validate", action="store_true")
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
