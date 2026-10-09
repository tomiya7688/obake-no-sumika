# キャラクターJSONの基本読込契約

例えば `start_position: [961, 340]` は960x540の部屋の外なので、起動時に拒否する。画面内へ黙って移動させたり、画像を読み込んだ後で気づいたりしない。編集済みのJSONへ書き戻さず、同じファイルをエディターで直して再起動できる。

この契約はPythonの `CharacterRepository.load()` とGodotの `CharacterSchema.parse()` を、同じ [42ケース](characters_cases.json) で比較するための基本範囲。Godotのゲーム入口はこの検証・正規化を全件へ適用してからPNGを読む。検証成功後の正規化済みDictionaryをモデルと描画へ渡す。

## 基本範囲

トップレベルは `schema_version: 1` と空でない `characters` 配列。各要素はオブジェクトで、ID・表示名・画像パスは空でない文字列とする。IDと表示名の前後の通常の空白を除き、正規化後の重複IDを拒否する。IDの種類やキャラクター数は基本検証では限定しない。ただし現在の通常版ランタイムは、引き続き `kadoka` と `maru` の2匹だけを受け付ける。

| フィールド | 数値と範囲 | 正規化・省略時 |
| --- | --- | --- |
| `start_position` | X/Yの2要素。0〜部屋幅 / 0〜部屋高さ、端を含む | 各値を0方向へ整数化してから範囲検証 |
| `display_height` | 16〜256 | 0方向へ整数化 |
| `personality` | 0.25〜3.0 | 実数へ変換 |
| `native_facing` | 整数化後 -1〜1 | 負値は-1、0以上は1 |
| `bubble_y_offset` | -200〜200 | 0方向へ整数化。省略は0 |
| `behavior_weights` | オブジェクト。各重み0〜100 | 省略は空。行動名をtrimし、空・重複を拒否 |

有限なJSON数値を対象とし、真偽値を数値として扱わない。整数化は参照実装の `int()` と同じ0方向への切り捨てで、例えば -0.9は0、64.9は64。巨大な有限数は変換前に拒否し、整数オーバーフローを起こさない。未知の非空行動名はデータとして保持するが、行動を実装したことにはならない。0の重みも保持する。

処理は入力を変更しない。途中の1匹が不正でも部分結果を返さず、エラーを返す。次の呼び出しではエラー状態をリセットする。画像の存在、透過領域、リンク・相対パスの安全性は `ContentLoader` 側の読込で別途確認する。

## ケースの作り方と実行

`base_definition` を複製し、各ケースの `changes` を上書き、`remove` のフィールドを削除する。`extra_characters` は基準定義へ上書きして追加する。`document` がある時はトップレベルごと置き換える。受理結果は基準定義へ省略値（吹き出し0、重み空）と `expected.changes` を加えたもの、拒否は `expected.status: rejected` を正とする。エラー文の完全一致は要求しない。

```powershell
$env:GODOT_BIN="C:\path\Godot_win64_console.exe"
.\.venv\Scripts\python.exe -m unittest tests.test_portable_character_contract -v
.\.venv\Scripts\python.exe tests/test_portable_character_contract.py -v
```

Python側は一時フォルダーの存在する画像ファイルとJSONを読んで比較する。Godot側は実体のGDScript基本検証を呼び、結果をUTF-8のJSONへ保存して比較する。ゲーム入口の検証順・正規化後の起動は `tests/test_godot_runtime.py` で別に確認する。Godotがない時はGodot検証のみskipする。

## 未対応・互換境界

Pythonの数値文字列や非文字列メタデータへの互換変換、全Unicode空白の同等性、絶対画像パス・リンクの互換性、画像のファイル検証の完全一致はこの共有ケースに含めない。Godotは引き続き数値文字列・非文字列メタデータ・非有限値を拒否する。Pythonの非有限値に関する既知の問題まで模倣しない。未知の追加フィールドはGodot側で保持するが、JSONへ保存しない。

部屋・会話・配置物を含む全入力の互換性、汎用キャラクターのゲーム起動はIssue #54の後続範囲。
