# 会話デッキ読込契約

目的: 言語実装が `conversations.json` を同じ規則で正規化するための共通契約です。状態: Python版（`engine/conversation_repository.py`）が参照実装で、共有ケースの検証はPythonのみです。Godot版との照合は未実装です。関連: [共通ケース](conversations_cases.json)、[移植・配布時の共有契約](../../docs/context/portability.md)。

## 入力と文脈

ファイルの最上位は会話の配列です。各会話は `weight`（数値）と `steps`（段階の配列）を持つオブジェクトです。検証には3つの許可IDの集合が必要で、プロジェクト側が与えます。

| 集合 | 使う段階 |
| --- | --- |
| `speaker_ids` | `say` の `speaker` |
| `actor_ids` | `move` / `take` / `put` の `actor` |
| `event_ids` | `event` の `event` |

## 段階の正規化

| `type` | 必須 | 正規化結果 |
| --- | --- | --- |
| `say`（省略時） | `speaker` が許可ID、`text` が空白除去後に非空 | `text` の連続空白を1つにまとめる。`speaker` 省略時は先頭の許可ID |
| `move` / `take` / `put` | `actor` が許可ID、`tag` が前後空白除去後に非空 | `tag` は前後空白を除去。`actor` 省略時は先頭の許可ID |
| `event` | `event` が許可ID | そのまま |

上記以外の `type`、非オブジェクト、必須を満たさない段階は不正です。

## 会話の正規化

1. `steps` が配列ならそれを使う。配列でなければ旧形式として、`speaker_ids` の順に「キー=話者ID、値=台詞」を `say` 段階にし、最後に有効な `event` キーがあれば `event` 段階を加える。
2. `weight` は省略時1。数値（真偽値は不可）で、1以上999以下に丸める。整数値の浮動小数は整数として保存する。
3. 正規化後の段階が0件の会話は不正です。

## 寛容読込と厳密検証

| 場面 | 不正な段階・会話の扱い |
| --- | --- |
| 読込（ゲーム実行時） | 不正な段階は捨てる。段階が残らない会話は捨てる。`weight` が数値でなければ1。ファイルが読めない・JSONでない・最上位が配列でないなら会話0件 |
| 厳密検証（エディター保存） | 不正な段階・会話・非数値の `weight` はすべて拒否する。会話が0件でも拒否する |

## 言語非依存のテストケース

[conversations_cases.json](conversations_cases.json) に、許可ID、入力、期待する正規化結果（寛容読込）と厳密検証の可否を置きます。Pythonは `tests/test_portable_conversation_contract.py` で検証します。数値表記の差（巨大数・NaN等）はまだ対象外です。
