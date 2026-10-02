# おばけの住処: GDScript移行版

Godot 4の通常版ソースランタイム。Python版を置き換える前の第一段階で、会話・イベント・エディターはまだ未移植。既存JSONとPNGをリポジトリの親から直接読むため、`godot/` 単体では起動できない。

## 起動

Godot 4の標準版で `godot/project.godot` を開き、F6ではなくF5（プロジェクト実行）で起動する。検証したバージョンは4.7.2。Mono/.NET版は不要。

Windowsではリポジトリ直下の `run_godot.bat` に実行ファイルのフルパスを渡せる。`GODOT_BIN` 環境変数またはPATH上の `godot.exe` があれば引数なしで起動できる。

```powershell
.\run_godot.bat "C:\path\Godot_win64.exe"
```

左クリックで集合、F11 / Alt+Enterで全画面切替、Escで終了。停止/前進/高速前進/進路変更/一周の移動宙返り/水場停止を実装している。会話の抽選はまだ行わない。

## 検証

```powershell
$env:GODOT_BIN="C:\path\Godot_win64_console.exe"
& $env:GODOT_BIN --headless --path godot --script res://tests/test_runtime.gd
& $env:GODOT_BIN --headless --path godot -- --test-frames 900 --seed 12345
.\.venv\Scripts\python.exe -m unittest tests.test_godot_runtime -v
.\.venv\Scripts\python.exe scripts/evaluate_project.py
```

環境変数未指定でPATHにもGodotがない場合、Python側のGodotテストは**skip**する。Pythonのテスト成功だけでGDScript検証済みとは扱わない。

`--test-frames` は固定delta 1/60秒で終了する。Godotのエンジンオプションとゲーム側のオプションは `--` で分離する。描画を保存したい場合は非headlessで `--screenshot <PNGのパス>` を追加できる。`--evaluation-log <JSONLのパス>` で状態を保存できる。出力先の親フォルダーは先に作る。

構造と移行境界は [機能説明書](../docs/GDScript移行機能説明書.md)、次回の読込範囲は [Godotコンテキスト](../docs/context/godot.md)。

実行方式はGodot公式の [コマンドライン](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)、[実行時ファイル読込](https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html) を参照。
