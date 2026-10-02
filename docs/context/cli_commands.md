# LLM向けCUIコマンドシート

PowerShellでリポジトリのルートから実行する。Pythonはこのプロジェクトの `.\.venv\Scripts\python.exe` を使う。下記のコマンドは対話UIの起動を除き、終了コード `0` が成功、非 `0` が失敗を表す。

## まず構成を調べる（GUI不要）

```powershell
.\.venv\Scripts\python.exe engine_app.py --describe
.\.venv\Scripts\python.exe engine_app.py --validate
.\.venv\Scripts\python.exe engine_app.py --project projects/obakeno_sumika_special/engine_project.json --describe
.\.venv\Scripts\python.exe engine_app.py --project projects/obakeno_sumika_special/engine_project.json --validate
```

`--describe` は名前、project_type、ゲーム入口、利用可能なエディターIDとスクリプト、コンテンツ名とパスをJSONで返す。パスは指定したプロジェクトのルートからの相対パス。`--validate` はマニフェストと参照パスの検証であり、全コンテンツの意味検証ではない。`--project` には対象の `engine_project.json` を渡す。

## 必要なキャラクター設定だけ取得する

```powershell
.\.venv\Scripts\python.exe tools/context/script/character_info.py --list
.\.venv\Scripts\python.exe tools/context/script/character_info.py --id maru --field personality --field behavior_weights
```

`--list` はIDと表示名だけ、`--id` は指定した1匹の設定をJSONで返す。`--field` を繰り返すとその項目とIDだけを返す。省略時は1匹の全設定。項目は `display_name`、`image`、`start_position`、`display_height`、`personality`、`native_facing`、`bubble_y_offset`、`behavior_weights`。`personality` は速度倍率で、`behavior_weights` は設定済みの重み（AI側の未指定行動の既定値は含まない）。`--project` で別マニフェストを指定でき、共通リポジトリで設定を検証する。キャラクター設定のないプロジェクトはエラーになる。

## 変更箇所を絞り、確認する

```powershell
.\.venv\Scripts\python.exe tools/context/script/select_files.py --json game.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/evaluate_project.py
```

選択ツールには変更したリポジトリ相対パスを複数渡せる。未登録パスは `unmapped_files` に出る。全体評価は構文、単体テスト、エンジン、通常版の短い起動、実行ログ、special版を確認し、`tmp/evaluation/runtime.jsonl` を更新する。フレーム数を変える場合は `scripts/evaluate_project.py --frames 60`。

## ゲームの短い起動・記録（GUI不要）

```powershell
$env:SDL_VIDEODRIVER="dummy"
$env:SDL_AUDIODRIVER="dummy"
.\.venv\Scripts\python.exe game.py --test-frames 60 --seed 12345
.\.venv\Scripts\python.exe game.py --test-frames 60 --seed 12345 --screenshot tmp/evaluation/scene.png
.\.venv\Scripts\python.exe projects/obakeno_sumika_special/game.py --validate
```

`--test-frames` で自動終了する。`--screenshot` は最後のフレームを保存するが、ダミー画面での確認は人間の実画面確認の代わりにならない。実際に遊ぶ時はダミー画面の環境変数を外す。

## 対話UI（実画面が必要）

```powershell
Remove-Item Env:SDL_VIDEODRIVER -ErrorAction SilentlyContinue
Remove-Item Env:SDL_AUDIODRIVER -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe engine_app.py
.\.venv\Scripts\python.exe game.py
.\.venv\Scripts\python.exe character_editor.py
.\.venv\Scripts\python.exe conversation_editor.py
.\.venv\Scripts\python.exe object_editor.py
```

統合エンジンのUIからはゲーム、マニフェスト登録済みエディター、別プロジェクトの選択、新規プロジェクトの作成ができる。現時点でCUIにあるのは構成表示・検証・通常版の実行と自動評価であり、GUIでの新規作成や編集をCUIで実行するコマンドはまだない。JSONを直接変更する場合は各リポジトリの検証条件と編集可能性を守る。
