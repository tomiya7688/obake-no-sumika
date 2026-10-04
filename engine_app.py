from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from engine.manifest_loader import load_project_manifest


DEFAULT_MANIFEST = Path(__file__).resolve().parent / "engine_project.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="プロジェクト統合エンジン")
    parser.add_argument("--project", type=Path, default=DEFAULT_MANIFEST)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--validate", action="store_true")
    action.add_argument("--describe", action="store_true", help="プロジェクト構成をJSONで表示")
    action.add_argument("--playtest-godot", action="store_true", help="共有データでGodot版を実行（終了まで待機）")
    parser.add_argument("--godot-bin", type=Path, help="Godot 4実行ファイルのパス")
    parser.add_argument("--headless", action="store_true", help="Godotを画面なしで検証")
    parser.add_argument("--test-frames", type=int, help="Godotを指定フレーム数で終了")
    parser.add_argument("--seed", type=int, help="Godotの乱数seedを固定")
    args = parser.parse_args()
    if not args.playtest_godot and (
        args.godot_bin is not None or args.headless or args.test_frames is not None or args.seed is not None
    ):
        parser.error("--godot-bin / --headless / --test-frames / --seed は --playtest-godot と併用してください")
    return args


def main() -> int:
    args = parse_args()
    if args.playtest_godot:
        from engine.godot_runner import run_godot

        try:
            return run_godot(
                args.project,
                executable=args.godot_bin,
                headless=args.headless,
                test_frames=args.test_frames,
                seed=args.seed,
            )
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"Godot playtest failed: {exc}", file=sys.stderr)
            return 1
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
