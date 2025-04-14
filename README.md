# Web Archive

個人用Webアーカイブシステム  
- 任意のURLを完全保存（HTML, CSS, JS, 画像はWebP変換）
- ランダムURLで公開・閲覧
- プレビュー画像自動生成・リアルタイムUI反映
- アーカイブ一覧のリスト/グリッド切替・削除機能
- テスト・運用・開発が容易な構成

---

## セットアップ手順

### 1. uvのインストール（Python仮想環境＆依存管理）

[uv公式インストール手順](https://github.com/astral-sh/uv)  
（例: Linuxの場合）

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. 依存関係のインストール

```sh
uv venv
uv add -r requirements.txt
```

### 3. Playwrightのブラウザバイナリインストール

```sh
uv run playwright install
```

---

## 開発・テスト・運用

### テスト実行

```sh
make test
```
- テスト用DB・プレビュー画像は本番用と完全分離されます
- すべてのテストがパスすることを確認してください

### サーバー起動

```sh
make run
```
- ブラウザで [http://localhost:8000](http://localhost:8000) にアクセス
- URLを入力してアーカイブ、プレビュー生成、削除、リアルタイムUIを体験できます

---

## ライセンス

MIT
