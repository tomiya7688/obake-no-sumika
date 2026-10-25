# Python取得基盤の緊急bootstrap（Issue #99 / #105）

リポジトリ直下から、対象venvのPythonを明示する。既定は読取専用の版・CAファイル確認で、旧版/欠落は終了1、判定/更新失敗は終了2。`--apply` だけが更新を許可する。Python 3.10以上と既存pipが必要。

```powershell
.\.venv\Scripts\python.exe -I -B tools/security/script/bootstrap.py
.\.venv\Scripts\python.exe -I -B tools/security/script/bootstrap.py --apply
```

最低版はpip 26.2.2 / certifi 2026.10.19。旧版/欠落だけを公式SHA256付きwheelで更新し、pipを先に処理する。満たしている新しい版は降格しない。未知の版表記（pre/dev/local版を含む）は自動更新せず非0で止め、手動で確認する。

pip自体が欠落した場合は自動導入せず終了2にする。対象Pythonの `ensurepip` でpipを準備してから再実行する。Work CIは依存導入前に更新し、導入後にも読取専用checkで下限を再確認する。

base Pythonは暗黙に変更しない。CIの管理済みruntimeだけは明示した `--managed-runtime` で更新を許可する。別のvenv・OS証明書・global Pythonを走査/更新する機能はない。TLS検証の無効化やtrusted-hostは使わない。

出力の `bundles` は実際の `certifi.where()` とpip内蔵certifiのファイルパス/内容SHA256。**版とCAファイルの点検であり、全証明書チェーンの拒否やOS信頼ストアの更新確認ではない**（`chains_verified: false`）。uv/sigstore、起動bat、配布物、main側CIなどの全環境対応は親Issue #99に残る。

根拠と固定wheelの出典:

- [Python公式のセキュリティ告知とpipのURL/SHA256](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576)
- [certifi公式アドバイザリ](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2)
- [certifi 2026.10.19のPyPI公式wheelメタデータ](https://pypi.org/pypi/certifi/2026.10.19/json)

Ruffの整形/checkは今回変更したPythonファイルを引数で明示し、[品質手順](../quality/README.md)に従う。関連テストは `python -m unittest tests.test_python_security tests.test_context_selection tests.test_ruff_baseline -v`。
