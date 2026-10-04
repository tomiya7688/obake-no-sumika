# おばけの住処: GDScript移行版

Godot 4の通常版ソースランタイム。個別移動、通常会話、タグ付きオブジェクト操作、水浴び・ゲーム機イベント、名前ホバー、床の影、背景の周辺減光、環境粒子を移植済み。統合エディター・完全な共有入力検証・配布は後続対応。既存JSONとPNGをリポジトリの親から直接読むため、`godot/` 単体では起動できない。

## 起動

Godot 4の標準版で `godot/project.godot` を開き、F6ではなくF5（プロジェクト実行）で起動する。検証したバージョンは4.7.2。Mono/.NET版は不要。

Windowsではリポジトリ直下の `run_godot.bat` に実行ファイルのフルパスを渡せる。`GODOT_BIN` 環境変数またはPATH上の `godot.exe` があれば引数なしで起動できる。

```powershell
.\run_godot.bat "C:\path\Godot_win64.exe"
```

左クリックで集合、F11 / Alt+Enterで全画面切替、Escで終了。おばけにマウスを重ねると、`characters.json` の表示名を下に小さく表示する。離れると消え、回転中・全画面・余白付きのウィンドウでも追従する。停止/前進/高速前進/進路変更/一周の移動宙返り/水場停止に加え、相手へ話しかける行動を実装している。会話時は横並びで向き合って止まり、既存JSONの台詞を吹き出しに順番に表示する。

会話は `conversations.json` を共用し、重み付きで抽選する。say、タグ付きmove/take/put、専用eventを順番に実行する。移動中は台詞を出さず、次の発話前に横並びで向き合い直す。カタログにある未実装イベントのカードや配置タグが欠落するカードは**全体を抽選から除外**する。カタログにないIDやterminalイベントの後に手順が続くカードは入力エラー。会話中にクリックすると会話を中断して集合する。共有ファイルをGodot用に書き換える必要はない。

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

`events.json` の既存water_bath/game_deviceを使う会話も実行する。水浴びは水場で横並びに向き合って5秒停止。ゲーム機はまるが取り出し→発光→2匹の反応を順番に表示→収納→左右の端へ高速で逃走する。イベント中も回転中には話さない。イベント終了・クリック中断・タイムアウトではゲーム機と光を画面から消す。通常のtakeで出した物は、これまで通りputまで残る。

水浴びはタグ付き水場の配置位置を使い、水場配置がなければ `room.json` のwater_rest中心を使う。ゲーム機イベントはカタログのrequired_tagを必要とし、標準はgame_device。既存会話エディターのevent手順をそのまま編集できる。現在のデッキは25カードすべて対応する。これはエンジンGUIへのGodot起動統合や入力検証の完全互換を意味しない。

おばけの下には薄いドット状の影を表示する。影は宙返りの移動軌道に追従し、終了時も滑らかに前進へつながる。細かな上下浮遊で影自体は揺れず、体の回転・振り返りにも影は変形しない。水面より前、岩やおばけより後ろの床レイヤーに描画する。

背景の端には `room.json` の `background.vignette` に従った薄い角丸の減光をかける。中央は透明に保ち、おばけ・水面・配置物・吹き出し・名前には重ねない。`max_inset: 0` で無効にできる。色や寸法・alphaの不正値、設定の欠落は起動時にエラーにする。設定を変えた時はゲームを再起動する。

住処には同じ部屋JSONの `motes` に従った小さな四角い粒子がゆっくり上昇し、少し左右に揺れる。上端を越えたら設定された下側範囲へ再出現する。数・色・透明度・半径候補・速度・範囲・揺れを編集でき、`count: 0` で無効化する。半径候補の重複は抽選の重みになる。環境用乱数は二匹や会話と独立している。水面より前、岩・おばけ・吹き出し・名前より後ろに描く。設定変更は再起動後に反映し、実行中にJSONへ書き戻さない。

## 検証

```powershell
$env:GODOT_BIN="C:\path\Godot_win64_console.exe"
& $env:GODOT_BIN --headless --path godot --script res://tests/test_runtime.gd
& $env:GODOT_BIN --headless --path godot --script res://tests/test_conversations.gd
& $env:GODOT_BIN --headless --path godot --script res://tests/test_objects.gd
& $env:GODOT_BIN --headless --path godot --script res://tests/test_events.gd
& $env:GODOT_BIN --headless --path godot --script res://tests/test_hover.gd
& $env:GODOT_BIN --headless --path godot --script res://tests/test_shadows.gd
& $env:GODOT_BIN --headless --path godot --script res://tests/test_vignette.gd
& $env:GODOT_BIN --headless --path godot --script res://tests/test_motes.gd
& $env:GODOT_BIN --headless --path godot -- --test-frames 900 --seed 12345
.\.venv\Scripts\python.exe -m unittest tests.test_godot_runtime -v
.\.venv\Scripts\python.exe scripts/evaluate_project.py
```

環境変数未指定でPATHにもGodotがない場合、Python側のGodotテストは**skip**する。Pythonのテスト成功だけでGDScript検証済みとは扱わない。

影の実描画チェックは非headlessで `--script res://tests/test_shadows.gd -- --screenshot-prefix <出力フォルダー/名前>`。通常時、左右の宙返り、水面上の4枚を保存し、影の表示あり/なしの描画ピクセル比較で水面より前・岩より後ろの描画順も確認する。

周辺減光は同様に `--script res://tests/test_vignette.gd -- --screenshot-prefix <出力フォルダー/名前>`。設定どおりの表示あり/なし・余白付きウィンドウ・全画面の4枚を保存する。描画順の比較にはテスト内だけで濃いマスクを使い、端の背景だけが変わり前景は変わらないことを確認する。画像のピクセル座標には [Viewportのstretch変換](https://docs.godotengine.org/en/stable/classes/class_viewport.html#class-viewport-method-get-stretch-transform) を使う。保存テクスチャは黒帯を含まないため、黒帯付きのウィンドウ座標で比較しない。

粒子は `--script res://tests/test_motes.gd -- --screenshot-prefix <出力フォルダー/名前>`。共有設定の開始時・4秒後・余白付きウィンドウ・全画面を保存する。描画順のテストだけは明るい固定粒子を使い、水面上で見えることと前景を隠さないことをピクセル比較する。リサイズ時のマウス入力で名札がサンプル間に変わらないよう、描画前にテスト側のホバーを固定する。全画面・クリックの検証は入力注入であり、手動入力とは区別する。

`--test-frames` は固定delta 1/60秒で終了する。Godotのエンジンオプションとゲーム側のオプションは `--` で分離する。描画を保存したい場合は非headlessで `--screenshot <PNGのパス>` を追加できる。`--evaluation-log <JSONLのパス>` で状態を保存できる。出力先の親フォルダーは先に作る。

会話の描画チェックは非headlessで `--script res://tests/test_conversations.gd -- --screenshot <PNGのパス>`。タグ操作後の描画は `--script res://tests/test_objects.gd -- --screenshot <PNGのパス>`。専用イベントは `--script res://tests/test_events.gd -- --screenshot-prefix <出力フォルダー/名前>` で水浴びと発光時の2枚を保存する。名前ホバーは `--script res://tests/test_hover.gd -- --screenshot-prefix <出力フォルダー/名前>` で2匹・会話併用・余白付きウィンドウ・全画面の5枚を保存する（入力イベントを自動注入した実描画テストで、手動マウス操作ではない）。100秒相当の通常AIは `--headless --fixed-fps 60 --path godot -- --test-frames 6000 --seed 12345 --evaluation-log <JSONLのパス>` で高速に確認できる。状態ログには発話、会話フェーズ、イベント段階、移動担当者、配置物の位置・表示・発光状態も含まれる。

構造と移行境界は [機能説明書](../docs/GDScript移行機能説明書.md)、次回の読込範囲は [Godotコンテキスト](../docs/context/godot.md)。

実行方式はGodot公式の [コマンドライン](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)、[実行時ファイル読込](https://docs.godotengine.org/en/stable/tutorials/io/runtime_file_loading_and_saving.html) を参照。
