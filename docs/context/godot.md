# Godot / GDScriptのコンテキスト

移行中のソース実装は `godot/`。個別移動、通常会話、タグ付きmove/take/put、水浴び・ゲーム機イベント、名前ホバー、床の影、背景の周辺減光、環境粒子まで対応。共通のJSON/PNGを読み、Pythonを実行しない。Godot以外のゲーム実装全体は通常読まない。仕様・未移植範囲は [機能説明書](../GDScript移行機能説明書.md)、起動は [README](../../godot/README.md)。Issue #54。

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
| 背景の周辺減光 | `godot/scripts/vignette_view.gd`, `godot/scripts/content_loader.gd`, `godot/scripts/main.gd`, `room.json` | `godot/tests/test_vignette.gd`、前景・余白付きウィンドウ・全画面の描画ピクセル |
| 環境粒子 | `godot/scripts/mote_field.gd`, `godot/scripts/mote_view.gd`, `godot/scripts/main.gd`, `room.json` | `godot/tests/test_motes.gd`、再出現・乱数独立性・描画順と全画面 |
| 描画・入力 | `godot/scripts/main.gd`, `godot/main.tscn`, `godot/project.godot` | 実描画スモーク |
| 起動とテスト | `run_godot.bat`, `tests/test_godot_runtime.py` | Godot実体でヘッドレス検証 |
| 統合CLIプレイテスト | `engine/godot_runner.py`, `engine_app.py` | `tests/test_godot_runner.py`、選択プロジェクトと不正データの実起動 |

`engine_app.py --playtest-godot` から同じ共有データで起動できる。`--project` は通常版の `engine_project.json` を指定し、終了まで待機する。Godotの指定優先度は `--godot-bin`、`GODOT_BIN`、PATHのgodot/godot4。Godot 4のバージョンを確認し、出力と終了コードをそのまま返す。`--headless` は正の `--test-frames` を必須とする。詳しいコマンドは [CUIコマンドシート](cli_commands.md)。GUI側の起動連携・監視は未対応。

`.godot/` は生成キャッシュ。読む必要はなくGitにも含めない。会話はsay/move/take/put/eventを重み付きで実行する。移動完了を待ち、次の発話前に再整列する。既知だが未実装のevent、または必要タグの欠落があるカードは丸ごと抽選から外す。未知IDや終了イベント後の手順はエラー。ゲーム機イベントの終了・中断では取り出した物と光を消す。他の通常take済みオブジェクトは変更しない。名前ホバー・影・周辺減光・環境粒子はAIや会話を変更しない。影は宙返りを含むモデル位置に追従し、細かな浮遊や回転は継承しない。減光は一度だけ生成し背景だけにかける。粒子は共有部屋設定と独立した環境用乱数で上昇・横揺れ・再出現し、更新はmainのdeltaだけで進む。GUI側の起動連携、完全な入力検証互換、Python/Godot評価ログ比較・配布は後続対応。ランタイムの取り出し/収納はJSONへ保存しない。
