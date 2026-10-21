# Godot / GDScriptのコンテキスト

同身長・独立乱数・前向き移動・会話整列など、ゲームとして維持する不変条件は [開発契約](../ai-development-contract.md) の Project contract を参照する。Python実装全体を読む必要はない。

移行中のソース実装は `godot/`。個別移動、通常会話、タグ付きmove/take/put、水浴び・ゲーム機イベント、名前ホバー、床の影、背景の周辺減光、環境粒子まで対応。共通のJSON/PNGを読み、Pythonを実行しない。Godot以外のゲーム実装全体は通常読まない。仕様・未移植範囲は [機能説明書](../GDScript移行機能説明書.md)、起動は [README](../../godot/README.md)。Issue #54。

| 変更領域 | 読むファイル | 検証 |
| --- | --- | --- |
| 部屋の基本幾何検証 | `godot/scripts/room_geometry.gd`, `spec/map/room_geometry.md`, `spec/map/room_geometry_cases.json` | `tests/test_portable_room_contract.py` → `godot/tests/test_room_geometry.gd` |
| 背景RGBと描画間隔の共有検証 | `godot/scripts/background_palette.gd`, `spec/map/background_palette.md`, `spec/map/background_palette_cases.json` | `tests/test_portable_palette_contract.py` → `godot/tests/test_background_palette.gd` |
| 背景ポリゴンの点・整数座標 | `godot/scripts/polygon_geometry.gd`, `spec/map/polygon_geometry.md`, `spec/map/polygon_geometry_cases.json` | `tests/test_portable_polygon_contract.py` → `godot/tests/test_polygon_geometry.gd` |
| プロジェクト定義の共有検証 | `godot/scripts/project_manifest.gd`, `spec/engine/project_manifest.md`, `spec/engine/project_manifest_cases.json` | `tests/test_portable_project_contract.py` → `godot/tests/test_project_manifest.gd` |
| キャラクターの基本共有検証 | `godot/scripts/character_schema.gd`, `spec/character/characters.md`, `spec/character/characters_cases.json` | `tests/test_portable_character_contract.py` → `godot/tests/test_character_schema.gd` |
| JSON・PNGの読込 | `godot/scripts/content_loader.gd` と対象のJSON | `godot/tests/test_runtime.gd`, `tests/test_godot_runtime.py` |
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
| テスト用Godot検出・スキップ条件 | `tests/godot_support.py`, `engine/godot_runner.py` | `tests/test_godot_support.py`、実Godotでランタイムと共有契約テスト |
| 統合CLIプレイテスト | `engine/godot_runner.py`, `engine_app.py` | `tests/test_godot_runner.py`、選択プロジェクトと不正データの実起動 |
| 子プロセス起動と永続ログ | `engine/process_launcher.py`, `engine/godot_runner.py` | `tests/test_godot_process_launcher.py`、`tests/test_godot_runtime.py` の実Godot正常/異常終了 |
| バックグラウンド準備と明示起動 | 同上。`prepare_godot_async()` → Future → `launch_prepared_godot()` | `tests/test_godot_preparation.py`、実Godotの2段階起動 |

キャラクターの基本条件はPythonと同じ42ケースで検証する。全件の名前・ID・開始位置・身長・性格・向き・吹き出し位置・行動重みを検証・正規化してからPNGを読む。開始位置は整数化後に部屋内であることを必須とし、空の名前や正規化後の重複を拒否する。既定値と数値の0方向への整数化はPythonに合わせる。数値文字列・非文字列メタデータ等の互換変換、全画像パス互換は後続範囲。基本検証は任意IDを扱えるが、ゲームは引き続きかどか・まるの2匹のみ。詳細は [基本読込契約](../../spec/character/characters.md)。

部屋の基本幾何はPythonと同じ49ケースで検証する。サイズ・fps・移動/水場矩形・会話距離を画像読込前に確認し、矩形は正の幅/高さで部屋内であることを必須とする。入力を変更せず深い複製を返す。基本検証は16:9の複数寸法と距離1〜部屋幅を扱うが、ランタイムは960x540・距離80〜300のまま。fpsの実行時反映や背景/粒子等の全入力互換は未対応。Godot JSONで整数値の小数表記を区別できない境界は [幾何契約](../../spec/map/room_geometry.md) と専用テストに明記する。

背景色・グラデーションstepはPythonと同じ39ケースで検証する。RGBは0〜255、stepは1〜部屋高さの有限な整数値として画像読込前に拒否/正規化する。未知の設定や座標・減光を深く複製して保持する。ポリゴン座標の完全な整数/大数互換や全背景入力は未対応。整数値の小数表記の違い、テスト用の幾何fixtureは [パレット契約](../../spec/map/background_palette.md) に記す。

ポリゴンの配列形状・3点以上・XYの有限な整数値はPythonと同じ35ケースで検証する。絶対値2^53-1以下の共有範囲で正規化し、全層を画像読込前に検証する。負/画面外座標と重複/共線の点は許可し、色・追加メタデータを深く複製して保持する。整数値の小数表記・Python任意精度整数との差、描画可能性や全入力互換を保証しない境界は [ポリゴン契約](../../spec/map/polygon_geometry.md) を読む。

テストも起動側と同じ処理で `GODOT_BIN` → PATHの `godot` → `godot4` の順に検出する。未設定かつどちらも見つからない時だけ実Godotのテストをスキップする。空文字・存在しないファイル・ディレクトリを `GODOT_BIN` に設定した場合はエラーにし、PATHへのフォールバックやスキップで隠さない。検出とスキップ条件の回帰テストはGodotの実体なしでも実行できる。

`tests/test_portable_*_contract.py`、`tests/test_godot_runtime.py`、`tests/test_godot_support.py` は、`python tests/<ファイル>.py` の直接起動と `python -m unittest` / discoverの両方を使える。直接起動時だけファイル位置からリポジトリを参照し、カレントディレクトリや `PYTHONPATH` に依存しない。隔離したPython子プロセスを別カレントから起動し、Godot不在時のスキップと不正な設定のエラーを回帰検証する。

プロジェクト定義はPythonと同じ共有22ケースで受理・正規化・拒否を検証する。名前、入口ファイル、エディター、外部/インラインcontentを描画前に検証し、上書きされる外部パスも不正なら拒否する。相対パスの内部 `..` は正規化できるが、絶対パスとリンクはGodot側では引き続き拒否する。定義の読込APIは別名ファイルも読める一方、ゲーム/統合CLIの入口名はまだ `engine_project.json` 固定。各コンテンツの完全な検証互換は後続範囲。

`engine_app.py --playtest-godot` から同じ共有データで起動できる。`--project` は通常版の `engine_project.json` を指定し、終了まで待機する。Godotの指定優先度は `--godot-bin`、`GODOT_BIN`、PATHのgodot/godot4。Godot 4のバージョンを確認し、出力と終了コードをそのまま返す。`--headless` は正の `--test-frames` を必須とする。詳しいコマンドは [CUIコマンドシート](cli_commands.md)。GUI側の起動連携・監視は未対応。

`ProcessLauncher.launch_godot()` は同期準備（probeのみ10秒上限）後、ゲーム終了を待たず子プロセスとUTF-8ログを返す。`prepare_godot_async()` は同じ準備をdaemon workerで実行してFutureを返し、ゲームは自動起動しない。main threadでdoneを確認した後、結果を1回だけ `launch_prepared_godot()` へ渡す。失敗はFutureから取得し、未開始だけキャンセル可能。実行中の準備は止められないが結果を捨ててもゲームは始まらない。選択変更後の別launcherへの引渡しは拒否する。GUIの操作・ポーリング接続は未実装。API戻り値やpoll=Noneを初期化成功とは扱わない。例と共有ファイルの時間差は [機能説明書](../GDScript移行機能説明書.md#godotの子プロセス起動api) を読む。

`.godot/` は生成キャッシュ。読む必要はなくGitにも含めない。会話はsay/move/take/put/eventを重み付きで実行する。移動完了を待ち、次の発話前に再整列する。既知だが未実装のevent、または必要タグの欠落があるカードは丸ごと抽選から外す。未知IDや終了イベント後の手順はエラー。ゲーム機イベントの終了・中断では取り出した物と光を消す。他の通常take済みオブジェクトは変更しない。名前ホバー・影・周辺減光・環境粒子はAIや会話を変更しない。影は宙返りを含むモデル位置に追従し、細かな浮遊や回転は継承しない。減光は一度だけ生成し背景だけにかける。粒子は共有部屋設定と独立した環境用乱数で上昇・横揺れ・再出現し、更新はmainのdeltaだけで進む。GUI側の起動連携、完全な入力検証互換、Python/Godot評価ログ比較・配布は後続対応。ランタイムの取り出し/収納はJSONへ保存しない。
