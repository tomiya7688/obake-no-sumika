# Godot / GDScriptのコンテキスト

移行中のソース実装は `godot/`。個別移動、通常会話、タグ付きmove/take/put、水浴び・ゲーム機イベント、名前ホバー、床の影まで対応。共通のJSON/PNGを読み、Pythonを実行しない。Godot以外のゲーム実装全体は通常読まない。仕様・未移植範囲は [機能説明書](../GDScript移行機能説明書.md)、起動は [README](../../godot/README.md)。Issue #54。

| 変更領域 | 読むファイル | 検証 |
| --- | --- | --- |
| JSON・PNGの読込 | `godot/scripts/content_loader.gd` と対象のJSON | `godot/tests/test_runtime.gd` |
| 行動と移動 | `godot/scripts/ghost_model.gd`, `characters.json`, `room.json` | 同上 |
| 会話データと整列・発話 | `godot/scripts/conversation_deck.gd`, `godot/scripts/conversation_controller.gd`, `conversations.json` | `godot/tests/test_conversations.gd` |
| タグ付き配置物と会話内操作 | `godot/scripts/object_model.gd`, `godot/scripts/conversation_controller.gd`, `godot/scripts/main.gd`, `placed_objects.json` | `godot/tests/test_objects.gd` |
| 専用イベントと清掃 | `godot/scripts/event_catalog.gd`, `godot/scripts/scripted_events.gd`, `godot/scripts/conversation_controller.gd`, `events.json` | `godot/tests/test_events.gd` |
| ゲーム機の発光 | `godot/scripts/event_view.gd`, `godot/scripts/main.gd` | 同上と実描画スモーク |
| 吹き出し | `godot/scripts/bubble_view.gd`, `godot/scripts/main.gd` | 日本語を含む実描画スモーク |
| 名前ホバー | `godot/scripts/name_view.gd`, `godot/scripts/main.gd` | `godot/tests/test_hover.gd`、全画面と日本語の実描画 |
| 床の影 | `godot/scripts/shadow_view.gd`, `godot/scripts/main.gd` | `godot/tests/test_shadows.gd`、左右の宙返りと描画ピクセル |
| 描画・入力 | `godot/scripts/main.gd`, `godot/main.tscn`, `godot/project.godot` | 実描画スモーク |
| 起動とテスト | `run_godot.bat`, `tests/test_godot_runtime.py` | Godot実体でヘッドレス検証 |

`.godot/` は生成キャッシュ。読む必要はなくGitにも含めない。会話はsay/move/take/put/eventを重み付きで実行する。移動完了を待ち、次の発話前に再整列する。既知だが未実装のevent、または必要タグの欠落があるカードは丸ごと抽選から外す。未知IDや終了イベント後の手順はエラー。ゲーム機イベントの終了・中断では取り出した物と光を消す。名前ホバーと影は描画だけでAIや会話を変更しない。影は宙返りを含むモデル位置に追従し、細かな浮遊や回転は継承しない。粒子・ビネット、統合エディター、配布はまだ未移植。ランタイムの取り出し/収納はJSONへ保存しない。
