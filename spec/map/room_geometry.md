# 部屋JSONの基本幾何契約

例えば960x540の部屋で `water_rest: [900, 500, 61, 41]` とすると水場が右・下へ1pxはみ出すため、起動時に拒否する。幅や高さが0の水場も拒否する。黙って座標を修正せず、元のJSONをエディターで直して再起動できる。

この契約はPythonの `RoomRepository.load()` とGodotの `RoomGeometry.parse()` を、同じ [49ケース](room_geometry_cases.json) で比較する基本範囲。画像・Node・乱数を使わず、元データを書き換えない。背景や環境粒子の全検証を完了したという意味ではない。

## 基本範囲

トップレベルはオブジェクトで `schema_version: 1` を持つ。基本検証と通常版ランタイムの制約を分ける。

| フィールド | 基本検証 | 現在のGodotランタイム |
| --- | --- | --- |
| `size.width` / `size.height` | 320〜3840 / 180〜2160の整数値。幅×9=高さ×16 | 960x540のみ |
| `fps` | 1〜240の整数値 | 設定の検証だけ。固定deltaやフレーム制限への反映は今回変更しない |
| `movement_bounds` | `[x,y,width,height]` の整数値。原点は非負、幅/高さは正、全体が部屋内 | 同じ |
| `zones.water_rest` | 移動範囲と同じ条件。右端/下端が部屋と一致することは許可 | 同じ |
| `conversation_distance` | 有限な数値、1〜部屋幅 | 引き続き80〜300 |

真偽値・文字列・欠落・整数項目の小数部を拒否する。矩形の成分は変換前に部屋寸法以内へ限定し、巨大数の整数オーバーフローを避ける。エラー時は部分結果を返さず、次の呼び出しでエラーをリセットする。

成功時は部屋Dictionaryを深く複製し、対象の整数値を整数へ、会話距離を実数へ正規化する。未知の追加フィールド・追加zone・未検証の背景/粒子設定は保持する。返却値の変更で入力が変わらないことも確認する。

ContentLoaderはこの基本検証と現在のランタイム制約を画像読込前に実行する。背景・粒子の既存検証は引き続き各処理が担当する。正規化済みの部屋定義をモデルと描画へ渡し、通常版JSON/PNG・AI・描画処理は変えない。

## ケースの作り方と実行

`base_definition` を複製し、`changes` をトップレベルへ上書き、`remove` のフィールドを削除する。`document` があれば全体を置き換える。`expected.status` が受理/拒否の正本。受理時の幾何値は編集後の入力値を期待値とする。Python側の完全な部屋読込に必要な背景/粒子は、全寸法で有効な最小設定を基準定義へ含める。

```powershell
$env:GODOT_BIN="C:\path\Godot_win64_console.exe"
.\.venv\Scripts\python.exe -m unittest tests.test_portable_room_contract -v
.\.venv\Scripts\python.exe tests/test_portable_room_contract.py -v
```

Python側は一時フォルダーへJSONを保存して参照実装を呼ぶ。Godot側は実体のGDScriptをバッチ起動し、結果をUTF-8のJSONで比較する。両方とも入力ファイル不変を確認する。Godot不在時はGodot検証だけskipする。起動経路とランタイム制約は `tests/test_godot_runtime.py` で別に実行確認する。

## 未対応・互換境界

Pythonは整数項目の `60.0` を拒否する。Godot JSONは `60` と `60.0` の表記を区別せず、どちらも整数値60として受理する。この違いをGodot専用テストとPythonの拒否で明示し、完全な型互換とは扱わない。Godotは非有限値と真偽値のschema_versionも拒否するが、Pythonの既存の受理問題を模倣しない。

背景グラデーション/ポリゴン・環境粒子を含む全部屋入力、配置物・会話の全入力互換、任意寸法のゲーム起動・fps反映・GUI・配布はこの単位の範囲外。Issue #54で継続する。
