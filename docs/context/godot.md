# Godot / GDScriptのコンテキスト

移行中のソース実装は `godot/`。個別移動と通常の会話まで対応。共通のJSON/PNGを読み、Pythonを実行しない。Godot以外のゲーム実装全体は通常読まない。仕様・未移植範囲は [機能説明書](../GDScript移行機能説明書.md)、起動は [README](../../godot/README.md)。Issue #54。

| 変更領域 | 読むファイル | 検証 |
| --- | --- | --- |
| JSON・PNGの読込 | `godot/scripts/content_loader.gd` と対象のJSON | `godot/tests/test_runtime.gd` |
| 行動と移動 | `godot/scripts/ghost_model.gd`, `characters.json`, `room.json` | 同上 |
| 会話データと整列・発話 | `godot/scripts/conversation_deck.gd`, `godot/scripts/conversation_controller.gd`, `conversations.json` | `godot/tests/test_conversations.gd` |
| 吹き出し | `godot/scripts/bubble_view.gd`, `godot/scripts/main.gd` | 日本語を含む実描画スモーク |
| 描画・入力 | `godot/scripts/main.gd`, `godot/main.tscn`, `godot/project.godot` | 実描画スモーク |
| 起動とテスト | `run_godot.bat`, `tests/test_godot_runtime.py` | Godot実体でヘッドレス検証 |

`.godot/` は生成キャッシュ。読む必要はなくGitにも含めない。`conversations.json` のsayだけのカードは重み付きで実行する。イベントやmove/take/putがあるカードは丸ごと抽選から外す（途中の台詞も再生しない）。これらのアクション、名前ホバー、エディター、配布はまだ未移植。
