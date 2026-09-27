# 差分要約ツール

Gitの2時点を比較し、全文パッチを表示せずに、コミット件名、変更ファイル、増減行数、責務表で選んだ文書・関連テスト、変更されたPythonの `def` / `class` 宣言を表示する。作業ツリーやリモートには変更を加えない。リモートの新しい状態を対象にする前に、通常のワークフローどおり `git fetch origin` を済ませる。

リポジトリのルートで実行する例:

```powershell
.\.venv\Scripts\python.exe tools/diff_summary/script/summarize.py --base HEAD~1 --head HEAD
.\.venv\Scripts\python.exe tools/diff_summary/script/summarize.py --base HEAD~5 --head origin/work --json
```

`--base` は必須で、`--head` の既定値は `HEAD`。`--max-files` の既定値は50で、超過分は `omitted_files` に示す。`--repo` で別のローカルGitリポジトリを指定できるが、責務表はこのプロジェクトのものを使用する。未登録パスには `unmapped: true` を付ける。未コミット変更と未追跡ファイルは対象外。削除・追加行数が `-` の場合はバイナリファイルを表す。変更された宣言だけを列挙するため、既存関数の本体だけを変更した場合は `changed_definitions` にその関数名は出ない。
