# エンジンCLI契約（`--describe` / `--validate`）

目的: 言語実装（Python・Godot・Unity）が、GUIなしでプロジェクト構成を照会する共通の出力形式を持つための契約です。状態: Python版が実装済み。他言語は未実装です。関連: [project_manifest.md](../engine/project_manifest.md)、[CUIコマンドシート](../../docs/context/cli_commands.md)。

## 対象コマンド

| コマンド | 成功時の標準出力 | 終了コード |
| --- | --- | --- |
| `--describe` | 下記のJSON（UTF-8、非ASCIIは `\uXXXX` 可） | 0 |
| `--validate` | 1行 `OK: <name> / editors=<件数> / content=<件数>`（行末の改行1つのみ） | 0 |

マニフェストが不正な場合は、どちらも受理結果を標準出力に出さず、非0で終了します。エラー文言は言語固有で、一致を要求しません。どちらのコマンドも**プロジェクトのファイル**を書き換えず、プロジェクトのスクリプトを実行しません（言語処理系が作るバイトコードキャッシュ等は対象外）。

## 前提と対象外

- `name` に改行を含むマニフェストは契約の対象外です（`--validate` が複数行になり得る）。共有ケースにも含めません。
- `--validate` の `<name>` は非ASCIIを含み得ます。標準出力の文字コードが UTF-8 でない環境（Windowsのリダイレクト等）では、実装が出力できない場合があります。呼び出し側は UTF-8（例: `PYTHONIOENCODING=utf-8`）を指定してください。`--describe` は ASCII のみで出力されるため影響を受けません。

## `--describe` の出力

キーは `name`, `project_type`, `entrypoint`, `editors`, `content`。`schema_version` と `content_manifest` は含めません。パスはすべてプロジェクトルートからの相対パスで `/` 区切りです。`editors` は宣言順（比較対象）、`content` のキー順は比較対象外です。

## テストケース

[engine_cli_cases.json](engine_cli_cases.json) に、入力マニフェストと期待結果を置きます。Pythonは `tests/test_portable_cli_contract.py` で検証します。
