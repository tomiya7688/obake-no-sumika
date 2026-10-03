# おばけの住処: GDScript移行版

Godot 4の通常版ソースランタイム。個別移動、通常会話とタグ付きオブジェクト操作まで移植中で、専用イベント・エディターはまだ未移植。既存JSONとPNGをリポジトリの親から直接読むため、`godot/` 単体では起動できない。

## 起動

Godot 4の標準版で `godot/project.godot` を開き、F6ではなくF5（プロジェクト実行）で起動する。検証したバージョンは4.7.2。Mono/.NET版は不要。

Windowsではリポジトリ直下の `run_godot.bat` に実行ファイルのフルパスを渡せる。`GODOT_BIN` 環境変数またはPATH上の `godot.exe` があれば引数なしで起動できる。

```powershell
.\run_godot.bat "C:\path\Godot_win64.exe"
```

左クリックで集合、F11 / Alt+Enterで全画面切替、Escで終了。停止/前進/高速前進/進路変更/一周の移動宙返り/水場停止に加え、相手へ話しかける行動を実装している。会話時は横並びで向き合って止まり、既存JSONの台詞を吹き出しに順番に表示する。

会話は `conversations.json` を共用し、重み付きで抽選する。sayとタグ付きmove/take/putを順番に実行する。移動中は台詞を出さず、次の発話前に横並びで向き合い直す。未移植のeventを含むカードや配置タグが欠落するカードは**全体を抽選から除外**する。会話中にクリックすると会話を中断して集合する。共有ファイルをGodot用に書き換える必要はない。

タグ操作は既存の会話エディターで編集できる。例えば次の会話はまるだけが拾い物へ移動し、取り出して話し、しまう。取り出し位置・表示状態は実行中だけ変化し、PNGや配置JSONは変更しない。`take` はその位置に置く操作で、持ったまま追従する機能ではない。中断時も実行済みの操作は巻き戻さない（しまう時はputを使う）。

```json
{"weight":1,"steps":[
  {"type":"move","actor":"maru","tag":"found_item"},
  {"type":"take","actor":"maru","tag":"found_item"},
  {"type":"say","speaker":"maru","text":"これ拾ったのだ"},
  {"type":"say","speaker":"kadoka","text":"なに、これ"},
  {"type":"put","actor":"maru","tag":"found_item"}
]}
```

既存の水浴び・ゲーム機イベントカードはまだ除外対象。タグ操作だけでは発光や逃走を再生しない。

## 検証

```powershell
$env:GODOT_BIN="C:\path\Godot_win64_console.exe"
& $env:GODOT_BIN --headless --path godot --script res://tests/test_runtime.gd
& $env:GODOT_BIN --headless --path godot --script res://tests/test_conversations.gd
& $env:GODOT_BIN --headless --path godot --script res://tests/test_objects.gd
& $env:GODOT_BIN --headless --path godot -- --test-frames 900 --seed 12345
.\.venv\Scripts\python.exe -m unittest tests.test_godot_runtime -v
.\.venv\Scripts\python.exe scripts/evaluate_project.py
```

環境変数未指定でPATHにもGodotがない場合、Python側のGodotテストは**skip**する。Pythonのテスト成功だけでGDScript検証済みとは扱わない。

`--test-frames` は固定delta 1/60秒で終了する。Godotのエンジンオプションとゲーム側のオプションは `--` で分離する。描画を保存したい場合は非headlessで `--screenshot <PNGのパス>` を追加できる。`--evaluation-log <JSONLのパス>` で状態を保存できる。出力先の親フォルダーは先に作る。

会話の描画チェックは非headlessで `--script res://tests/test_conversations.gd -- --screenshot <PNGのパス>`。タグ操作後の描画は `--script res://tests/test_objects.gd -- --screenshot <PNGのパス>`。100秒相当の通常AIは `--headless --fixed-fps 60 --path godot -- --test-frames 6000 --seed 12345 --evaluation-log <JSONLのパス>` で高速に確認できる。状態ログには発話、会話フェーズ、移動担当者、配置物の位置・表示状態も含まれる。

構造と移行境界は [機能説明書](../docs/GDScript移行機能説明書.md)、次回の読込範囲は [Godotコンテキスト](../docs/context/godot.md)。

実行方式はGodot公式の [コマンドライン](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)、[実行時ファイル読込](https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html) を参照。
