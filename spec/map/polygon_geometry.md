# 背景ポリゴン座標の基本契約

例えば `points: [[0.5,0],[50,0],[0,50]]` はXに小数部があるため、Godotの画像読込前に拒否する。元の部屋JSONは修正せず、エディターで整数座標へ直して再起動できる。

Pythonの `RoomRepository.load()` とGodotの `PolygonGeometry.parse()` を同じ [35ケース](polygon_geometry_cases.json) で比較する。対象は `background.polygons` の形と点のXY。RGBは [パレット契約](background_palette.md)、部屋の寸法や移動範囲は [幾何契約](room_geometry.md) で別に検証する。

## 条件と結果

| フィールド | 条件 | 成功時 |
| --- | --- | --- |
| `background.polygons` | 配列。空も有効 | 層の順序を保持 |
| 各層 | オブジェクト | 色・追加設定も深く複製して保持。この検証器は色を検証しない |
| 各層の `points` | 3点以上の配列 | 点の順序を保持 |
| 各点 | 長さ2の配列 `[x,y]` | XYを整数値に正規化 |
| XYの共有範囲 | 真偽値でない有限な整数値、絶対値 `9007199254740991`（2^53-1）以下 | オーバーフローや精度低下を避け、整数変換 |

負座標や部屋の外側、重複点、共線の点はPythonと同じく許可する。凸形・面積・自己交差・描画可能性を検証する契約ではない。不正型・欠落・点数不足・小数部・真偽値・非有限値は拒否する。Godotでは範囲外の巨大数も整数変換前に拒否する。

Godotは配列全体を深く複製し、追加メタデータや色も入力と共有しない。失敗は空配列と非空 `error` を返し、処理済みの層を部分結果として返さない。空の層配列は有効なので、空かどうかではなく `error` で成否を判断する。次のparseでエラー状態をリセットする。PythonのRoomDefinitionは既知の色と点だけを保持し、未知設定の保持はGodot検証器の契約。

ContentLoaderは背景パレット・減光の検証後、全ポリゴンをこの検証器へ通してからキャラクター画像を読む。どの層の不正値もPNG読込前に拒否する。通常版のJSON/PNG、描画処理、AIは変更しない。

## 共有ケースの編集・実行

ケースは `base_definition` の層配列を複製し、`set` のドット区切りパスを上書きする。例: `0.points.2.1` は最初の層の3点目のY。`remove` は同じパスのフィールドを削除し、`document` があれば配列全体を置換する。`expected.status` が受理/拒否の正本。受理時の層と座標の期待値は編集後の入力。

Pythonの他の必須設定は `base_room_fixture` の [部屋幾何ケース](room_geometry_cases.json) の `base_definition` を使い、polygonsだけ置き換える。拒否ケースのフィールドは補完しない。Godotは層配列だけを読み、元リクエストを書き換えずUTF-8レポートへ結果を出す。

```powershell
$env:GODOT_BIN="C:\path\Godot_win64_console.exe"
.\.venv\Scripts\python.exe -m unittest tests.test_portable_polygon_contract -v
.\.venv\Scripts\python.exe tests/test_portable_polygon_contract.py -v
```

Godot未設定・PATHにもない時だけGodot検証をskipする。実体を使ったContentLoaderの画像前拒否・編集済み座標の起動は `tests/test_godot_runtime.py` で確認する。ヘッドレス起動は目視/画素一致の検証ではない。

## 精度・型の互換境界

GodotのJSONは整数トークンと整数値の小数表記を区別できないため `0.0` も受理する。Pythonの整数項目は `0.0` を拒否する。Godot JSONのfloat精度を越えるXYは保守的に拒否する一方、Pythonの任意精度整数はそのまま読める。これらは共有35ケースに混ぜず、専用テストで相違を確認する。Godotのプログラムからintを直接渡す時も同じ共有範囲に限定する。

2^53-1の正負端、範囲外の2^53・符号付き64bit端・10^100、NAN/INF、整数値の小数表記と失敗後の再読込を別途確認する。精度境界を含む完全なPython互換、減光/粒子・会話/配置物を含む全入力共有、評価ログ比較・配布はIssue #54の後続範囲。
