# 公開CA回帰fixture

公開X.509証明書のみ。秘密鍵は含まない。外部接続・OSへのインストールに使わず、隔離した解析の回帰専用。

- `emsign-ecc-g3.pem`: [certifi修正前69494a7](https://github.com/certifi/python-certifi/blob/69494a764d0a08f90838d53d4b0fefd3e84045d6/certifi/cacert.pem)。DER SHA256 `86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b`。
- `unaffected-emsign-c1.pem`: [影響のないrootの復元662df63](https://github.com/certifi/python-certifi/commit/662df63d7906df66f1f07c0751a3dfe9da14d914)。DER SHA256 `125609aa301da0a249b97a8239cb6a34216f44dcac9f3954b14292f2e8c8608f`。emSignという名前だけで拒否しないことを確認する。

元のcertifi CA bundleのライセンス: [MPL-2.0](https://github.com/certifi/python-certifi/blob/662df63d7906df66f1f07c0751a3dfe9da14d914/LICENSE)。除去と復元のnet差分ではG3だけが除去対象。全チェーンの検証用fixtureではない。
