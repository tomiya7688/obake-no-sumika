# Codex cheat sheet

このファイルは開発時の最初の参照先。全体説明が必要な場合だけ `README.md` を読む。

## Required roadmap

- 実装を始める前に `docs/開発予定.md` を毎回全文読む。この文書を現在の開発予定と優先順位の正とする。
- 深い設計が必要な機能は、同文書の指示に従って機能説明書を作る。表はMarkdown、図はMermaidを使う。
- 実装完了後は、対応する項目を `docs/開発予定.md` から削除する。
- 文書内の対象ファイル名や `doc/`・`docs/` の違いが実装範囲に影響する場合は、推測で直さずユーザーへ確認する。

## Project contract

- Python 3.10+ / pygame。戦闘・スコア・ゲームオーバーのない観察ゲーム。
- 内部画面は `960x540`（16:9）。全画面でもゲーム座標と縦横比を維持する。
- 主役は同じ表示身長の「かどか」と「まる」。通常表示幅は `64px`。
- 2匹は別々の乱数ストリームで独立して行動する。片方の抽選で他方の行動列を変えない。
- 行動候補は停止、前進、高速前進、360度の進路変更、1回の大きく遅い宙返り、会話しに行く、水場付近で停止。
- 移動は常に顔の前方。逆方向へ進む必要がある場合は先に振り返る。まるの画像の素の向きは `native_facing=-1`。
- 横長画面なので進路変更の約78%は左右主体。ただし上下を含む360度も残す。上下の浮遊揺れはゆっくり。
- 左クリックで2匹がクリック地点の左右へ寄り、到着後に通常AIへ戻る。F11 / Alt+Enterで全画面、Escで終了。
- 会話開始側だけが相手へ接近する。回転・宙返りを完了してから横方向に間隔を空けて整列し、停止（浮遊揺れのみ）して話す。吹き出しを重ねない。
- 会話と水浴び中の向き・整列を崩さない。会話中に回転や自由行動を再開させない。

## Source map

- `game.py`: ゲーム、AI、会話シーケンス、イベント、描画。主なクラスは `Ghost`、`HabitatObject`、`Mote`。
- `characters.json`: ゲームが直接読むキャラクター定義。表示名、画像、開始位置、表示身長、性格速度倍率、元画像の向き、吹き出し高さを保存。
- `character_editor.py`: `characters.json` を共有処理経由で編集するTkエディター。
- `room.json`: 16:9の部屋寸法、移動・水場領域、背景ポリゴン、環境粒子を保存する部屋定義。
- `conversations.json`: 実行時に直接読む会話デッキ。会話変更はここを正とする。
- `events.json`: イベントID、表示名、終了属性、必要な配置タグを保存するイベントカタログ。
- `conversation_editor.py`: 会話JSONを直接編集するTkエディタ。
- `placed_objects.json`: 配置、表示幅、タグ、初期表示状態。ゲーム座標で保存。
- `object_editor.py`: ドット絵作成、1024x1024透過PNG出力、既存物の挿入・移動・削除。
- `engine_project.json`: 統合エンジンが読むゲーム・エディター・コンテンツの定義。
- `engine/`: プロジェクト定義、読込処理、起動処理、統合GUIを分離した共通層。
- `engine/*_repository.py`: キャラクター、部屋、会話、イベント、配置物、ドット絵ソースの共有JSON処理。GUIから直接JSONを読み書きしない。
- `engine_app.py` / `run_engine.bat`: 統合エンジンの起動入口。
- `objects/`: 編集用 `*.source.json` と1024x1024 PNG。
- `assets/`: かどか、まる、ゲーム機などの固定画像。
- `tests/test_tagged_conversations.py`: 会話・タグ・イベント・名前ホバーの回帰テスト。
- `VERSION`: 現在バージョンの正。公開時は `game.py`、`README.md`、`CHANGELOG.md`、`RELEASE_NOTES.md` も揃える。

## Data contracts

部屋:

```json
{"schema_version":1,"size":{"width":960,"height":540},"movement_bounds":[74,80,812,446],"zones":{"water_rest":[335,348,354,168]}}
```

- 部屋サイズは16:9を維持する。キャラクター開始位置とオブジェクトエディターの座標上限もこの値を使う。
- 背景は `background.gradient`、`background.polygons`、`background.vignette` の順で描画する。
- 洞窟形状を変える場合は `room.json` を編集し、分離前基準との比較ではなく新しい意図した見た目を実画面確認する。

キャラクター1件:

```json
{"id":"kadoka","display_name":"かどか","image":"assets/kadoka.png","start_position":[320,340],"display_height":64,"personality":0.92,"native_facing":1,"bubble_y_offset":0}
```

- `id` は会話・イベントとの接続に使うため、現在のゲームでは `kadoka` と `maru` を維持する。
- 画像はプロジェクト内の相対パスだけを許可する。
- 2匹を同じ身長・横並びにするときは `display_height` と開始位置Yを同じにする。

会話1件:

```json
{"weight": 1, "steps": [{"type": "say", "speaker": "kadoka", "text": "..."}]}
```

- `weight`: 1〜999。値に比例して選ばれやすい。
- `say`: `speaker` は `kadoka|maru`。
- `move|take|put`: `actor` は `kadoka|maru|both`、`tag` は配置物のタグ。
- `event`: `event` は `water_bath|game_device`。終了イベントなので原則最後に置く。
- 不透明な中間形式を作らず、エディタとゲームは同じJSONを直接使う。

イベント1件:

```json
{"id":"game_device","label":"ゲーム機イベント","terminal":true,"required_tag":"game_device"}
```

- 会話の `event` は `events.json` に存在するIDだけを許可する。
- `required_tag` があるイベントは、配置物に同じタグが存在しない場合に起動を拒否する。

配置物:

```json
{"id":"...","name":"...","image":"objects/x.png","tag":"x","x":480,"y":270,"width":64,"visible":true}
```

- `tag` は配置ごとに一意。既定タグは `water`、`small_rock`、`large_rock`、`found_item`、`game_device`。
- `game_device` は初期非表示で、イベント中にまるが取り出して発光させ、2匹が反対側へ高速で逃げる。
- 保存画像は1024x1024透過PNG。`width` はゲーム内表示幅で、画像の保存解像度とは別。

## Safe workflow

- 作業前に `git status --short --branch`。ユーザーの既存変更や無関係ファイルを巻き込まない。
- JSONはUTF-8の可読形式を維持し、エディタで再編集できる状態を守る。
- AIや会話姿勢を変えたら、独立行動、前向き移動、回転終了後の会話、吹き出し間隔、水浴び、ゲーム機イベントを確認する。
- 画像・配置変更は画面上でも確認する。テスト成功だけで見た目の正しさを断定しない。
- GitHub公開はVS CodeターミナルのGit / `gh` を使う。明示された変更だけをコミットする。

## Verification

プロジェクトの `.venv` を使う。

```powershell
.\.venv\Scripts\python.exe -m py_compile game.py conversation_editor.py object_editor.py tests\test_tagged_conversations.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
$env:SDL_VIDEODRIVER="dummy"; $env:SDL_AUDIODRIVER="dummy"; .\.venv\Scripts\python.exe game.py --test-frames 900 --seed 12345
```

UIや描画を変えた場合は、最後に `run_game.bat` と該当エディタを実画面で確認する。
