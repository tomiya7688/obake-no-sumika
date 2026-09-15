# Runtime Performance Checker

`check_runtime.py` は、エンジン側とゲーム側の実行速度を CI で常時確認するためのチェッカーです。アプリ本体へ計測処理を常駐させません。

## Engine

以下を1つのプロジェクト読込パイプラインとして反復計測します。

- Room / Event / Placement / Character / Conversation の読込と検証
- Event と Placement tag の整合確認
- `RoomRenderer` による背景生成

ウォームアップ後の中央値と最悪 run の両方を判定します。

## Game

`game.py --test-frames` を SDL dummy driver で実行します。

`--test-frames` では通常プレイ時の `clock.tick(FPS)` 待機を行わないため、更新・描画・display flip を含むフレーム処理を可能な限り高速に回して計測できます。表示される FPS は実画面のFPSではなく、無制限実行時の処理能力換算値です。

## Thresholds

閾値は `thresholds.json` に置きます。

初回 Windows GitHub-hosted runner の実測:

- Engine: median 8.31 ms / worst 11.18 ms
- Game: median 1.589 ms/frame / worst 2.029 ms/frame

初期ゲート:

- Engine: median <= 25 ms / worst <= 60 ms
- Game: median <= 4 ms/frame / worst <= 8 ms/frame

CI環境の揺れを許容しつつ、数倍級の明確な性能劣化を検出するための値です。ゲーム規模の増加など正当な理由で基準を変更する場合は、新しい実測値を確認して更新します。単にCIを通すためだけに閾値を緩めないでください。

## Local run

```bash
python tools/performance/check_runtime.py
python tools/performance/check_runtime.py --only engine
python tools/performance/check_runtime.py --only game
```

結果は標準出力と `tmp/performance/latest.json` に出力されます。
