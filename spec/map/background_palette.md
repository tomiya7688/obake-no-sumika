# 背景パレットとグラデーション間隔の契約

例えば `gradient.top: [8, 256, 20]` はRGBの緑が上限255を越えるので起動時に拒否する。960x540の部屋で `gradient.step: 541` も拒否する。画面へ黙ってクランプせず、元のJSONをエディターで直して再起動できる。

Pythonの `RoomRepository.load()` とGodotの `BackgroundPalette.parse()` を同じ [39ケース](background_palette_cases.json) で比較する。対象は背景のRGBと描画間隔で、ポリゴンの幾何や減光・粒子、描画ピクセルの完全一致はこの契約の範囲外。

## 検証するフィールド

| フィールド | 条件 |
| --- | --- |
| `gradient` | オブジェクト |
| `gradient.top` / `gradient.bottom` | `[red,green,blue]`、0〜255の整数値 |
| `gradient.step` | 1〜検証済み部屋高さの整数値 |
| `polygons` | 配列。空の配列も有効 |
| `polygons[].color` | 各要素はオブジェクト、RGBは0〜255の整数値 |

欠落、不正型、文字列、真偽値、小数部、非有限値、範囲外を拒否する。渡される部屋高も1〜2160に限定し、整数変換前に範囲検証を行うため、巨大数を整数オーバーフローへ変換しない。エラー時は部分結果を返さず、次の呼び出しでエラー状態をリセットする。

成功時は背景Dictionary全体を深く複製し、RGBとstepを整数値に正規化する。追加設定・ポリゴン座標・vignetteは保持するが、この処理で検証したとは扱わない。返却値の変更が入力へ影響しないことも確認する。

ContentLoaderはこれを画像読込前に呼ぶ。ポリゴン座標の配列形状・有限な整数値は [別の契約](polygon_geometry.md) で、その後に検証する。減光の検証も別処理。通常版JSON/PNGと描画処理は変更しない。

## ケースの編集と実行

`base_definition` を複製し、`set` のドット区切りパスを上書きする。例えば `polygons.0.color` は最初の層のRGB。`remove` は同じ形式のフィールドを削除し、`document` があれば全体を置き換える。`expected.status` が受理/拒否の正本で、受理時の値は編集後の入力を期待値とする。

Python用の有効な部屋の基準は `base_room_fixture` の [部屋幾何ケース](room_geometry_cases.json) の `base_definition`。背景は今回の入力に置き換え、無関係な必須vignetteだけ補う。欠落したgradient/polygonsを補完しない。Godotは背景Dictionaryだけを読み、元JSONを書き換えずUTF-8の結果を返す。

```powershell
$env:GODOT_BIN="C:\path\Godot_win64_console.exe"
.\.venv\Scripts\python.exe -m unittest tests.test_portable_palette_contract -v
.\.venv\Scripts\python.exe tests/test_portable_palette_contract.py -v
```

Godot不在時はGodot検証だけskipする。起動経路と有効な編集済み背景での起動は `tests/test_godot_runtime.py` で別に確認する。ヘッドレス起動成功だけで見た目を検証済みとは報告しない。

## 互換境界と残作業

Godot JSONは `8` と `8.0` の表記を区別できず整数値として受理する。Pythonは整数項目の `8.0` を拒否するため、専用テストで差を明記する。部屋高さ180に対するstep180/181も実Godotで確認し、540固定の検証にしない。

ポリゴン座標の完全な整数・大数互換、減光・粒子を含む全部屋入力、会話・配置物の入力互換、GUI・配布はIssue #54の後続範囲。
