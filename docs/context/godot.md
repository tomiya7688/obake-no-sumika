# Godot / GDScriptのコンテキスト

移行第一段階のソース実装は `godot/`。共通のJSON/PNGを読み、Pythonを実行しない。Godot以外のゲーム実装全体は通常読まない。仕様・未移植範囲は [機能説明書](../GDScript移行機能説明書.md)、起動は [README](../../godot/README.md)。Issue #54。

| 変更領域 | 読むファイル | 検証 |
| --- | --- | --- |
| JSON・PNGの読込 | `godot/scripts/content_loader.gd` と対象のJSON | `godot/tests/test_runtime.gd` |
| 行動と移動 | `godot/scripts/ghost_model.gd`, `characters.json`, `room.json` | 同上 |
| 描画・入力 | `godot/scripts/main.gd`, `godot/main.tscn`, `godot/project.godot` | 実描画スモーク |
| 起動とテスト | `run_godot.bat`, `tests/test_godot_runtime.py` | Godot実体でヘッドレス検証 |

`.godot/` は生成キャッシュ。読む必要はなくGitにも含めない。会話やイベントは未移植で、既存の `conversations.json` を修正しても現Godot版では実行されない。
