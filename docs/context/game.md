# ゲーム本体のコンテキスト

`game.py` がpygameの実行入口。内部画面は960×540。かどかとまるは独立した乱数系列で動き、会話とイベントはJSONデータを読む。行動・描画の制約は `AGENTS.md` の Project contract を参照する。

| 対象 | 責務 | 関連テスト |
| --- | --- | --- |
| `game.py` | おばけの移動、会話手順、イベント実行、描画、入力 | `tests/test_tagged_conversations.py` |
| `characters.json` | 見た目、開始位置、速度倍率、行動重み | `tests/test_character_repository.py` |
| `room.json` | 16:9の部屋、移動範囲、水場、背景 | `tests/test_room_repository.py` |
| `conversations.json`, `events.json` | 会話デッキとイベント定義 | `tests/test_tagged_conversations.py`, `tests/test_content_repositories.py` |
| `placed_objects.json`, `objects/`, `assets/` | 配置、編集用ドット絵、固定画像 | `tests/test_content_repositories.py` |
| `projects/obakeno_sumika_special/` | 別プロジェクトの高機能版。通常版データを直接参照しない | `tests/test_special_project_isolation.py` |

JSONの検証仕様を変える場合は [engine.md](engine.md) の該当リポジトリも読む。画像や配置の見た目を変えた場合は実画面で確認する。ゲームの短い機械確認には `.\.venv\Scripts\python.exe game.py --test-frames 60 --seed 12345` を使う。
