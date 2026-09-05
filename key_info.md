# key_info

## 今できること

- かどかとまるが、16:9の暗い住処の中を自律的にふわふわ移動する。
- 2匹は停止、前進、高速前進、進路変更、ゆっくりした宙返り、会話しに行く、水場で休む行動を選ぶ。
- 壁に当たると反射し、進行方向に合わせて向きを変えてから前へ進む。
- 左クリックした場所へ2匹が寄っていき、到着後に通常行動へ戻る。
- マウスカーソルをおばけに重ねると名前が表示される。
- F11またはAlt+Enterで全画面表示を切り替えられる。

## 編集できること

- `characters.json`: かどか・まるの表示名、画像、開始位置、身長、速度傾向、元画像の向き、吹き出し位置。
- `conversations.json`: 会話のセリフ、手順、重み、イベント。
- `events.json`: 会話から呼び出せるイベントと必要タグ。
- `game_content.json`: ゲーム固有のデータファイル一覧。
- `placed_objects.json`: 住処内のオブジェクト配置、タグ、表示状態、ゲーム内サイズ。
- `room.json`: 住処の16:9寸法、移動範囲、水場、背景、ほこり粒。
- `objects/*.source.json`: ドット絵オブジェクトの再編集用データ。

## 起動

```powershell
.\run_game.bat
.\run_engine.bat
.\run_editor.bat
.\run_object_editor.bat
```

## エンジンでできること

- 現在の `engine_project.json` を読み込み、ゲームと各エディターを起動できる。
- 新規プロジェクトを作成できる。
- 別の `engine_project.json` を選択して、開いているプロジェクトを切り替えられる。
- 通常版は `project_type: "standard"`、special版は `project_type: "obakeno_sumika_special"` として分離されている。

## 開発者向け

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_project.py
```

この自動評価では、構文チェック、単体テスト、通常版マニフェスト検証、通常版ゲームの900フレーム起動、評価ログ生成、special版検証をまとめて実行する。

挙動ログだけ出す場合:

```powershell
.\.venv\Scripts\python.exe game.py --test-frames 600 --seed 12345 --evaluation-log tmp\evaluation\runtime.jsonl --evaluation-interval 10
```

ログには、2匹の座標、速度、向き、現在行動、会話テキスト、移動目標と、配置オブジェクトの座標・表示状態・発光状態が入る。
