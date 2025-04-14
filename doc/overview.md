# Web Archive Project Overview

このドキュメントは、Web Archiveプロジェクトの全体的なファイル構成と仕様書との対応関係を整理するためのものです。プロジェクトの構造を把握し、開発の整合性を維持するために使用します。

## ファイル構成

以下は、プロジェクトのファイル構成を`tree`形式で示したものです。globパターンを使用して情報を圧縮し、必要に応じて詳細を追加します。

```
web-archive/
├── doc/
│   ├── System-spec.md              # システム全体の仕様書
│   ├── Module-spec.md              # モジュール全体の仕様概要
│   ├── module/
│   │   ├── web-interface-spec.md   # Webインターフェースモジュールの仕様
│   │   ├── content-fetch-spec.md     # コンテンツ取得モジュールの仕様
│   │   ├── db-manager-spec.md        # データベース管理モジュールの仕様
│   │   ├── content-publish-spec.md   # コンテンツ公開モジュールの仕様
│   │   └── preview-generator-spec.md # プレビュー生成モジュールの仕様
│   └── overview.md                   # このファイル。ファイル構成と対応関係の概要
├── src/
│   ├── main.py                       # アプリケーションのエントリーポイント
│   ├── modules/
│   │   ├── web_interface.py        # Webインターフェースモジュールの実装
│   │   ├── content_fetch.py          # コンテンツ取得モジュールの実装
│   │   ├── db_manager.py             # データベース管理モジュールの実装
│   │   ├── content_publish.py        # コンテンツ公開モジュールの実装
│   │   └── preview_generator.py      # プレビュー生成モジュールの実装
│   └── tests/
│       ├── test_web_interface.py     # Webインターフェースの単体テスト
│       ├── test_content_fetch.py     # コンテンツ取得の単体テスト
│       ├── test_db_manager.py        # データベース管理の単体テスト
│       ├── test_content_publish.py   # コンテンツ公開の単体テスト
│       └── test_preview_generator.py # プレビュー生成の単体テスト
├── requirements.txt                  # プロジェクトの依存関係
├── pyproject.toml                    # プロジェクト設定 (uv用)
└── previews/                         # 生成されたプレビュー画像保存ディレクトリ
```

## 仕様書とモジュールの対応関係

- `doc/System-spec.md`: システム全体の要件と設計を記述。すべてのモジュールのインターフェースと連携を概説。
- `doc/Module-spec.md`: 各モジュールの概要と役割を記述。
- `doc/module/web-interface-spec.md`: `src/modules/web_interface.py` の仕様。
- `doc/module/content-fetch-spec.md`: `src/modules/content_fetch.py` の仕様。
- `doc/module/db-manager-spec.md`: `src/modules/db_manager.py` の仕様。
- `doc/module/content-publish-spec.md`: `src/modules/content_publish.py` の仕様。
- `doc/module/preview-generator-spec.md`: `src/modules/preview_generator.py` の仕様。

## 更新ルール

- ソースファイルの作成・修正前後にこのファイルを確認し、必要に応じて更新する。
- 仕様書（`*-spec.md`）を参照しながら開発を行い、仕様に変更があれば同時に更新する。

このドキュメントは、プロジェクトの構造と仕様の整合性を保つために重要です。
