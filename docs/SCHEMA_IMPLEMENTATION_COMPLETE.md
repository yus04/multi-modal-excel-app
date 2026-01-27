# スキーマベースインデックス構築機能 - 実装完了

## 実装日
2026年1月24日

## 実装内容

ユーザーが定義したスキーマに基づいて、Excelファイルの各フィールドごとに検索可能なインデックスを構築する機能を実装しました。

## 変更ファイル

### 1. `/backend/app/search_service.py`

#### 追加メソッド:

- **`_get_schema_index_name(schema_id: str)`**
  - スキーマIDからインデックス名を生成

- **`create_schema_based_index(schema)`**
  - スキーマ定義に基づいて動的にAzure AI Searchインデックスを作成
  - 各フィールドに対して以下を生成:
    - テキスト検索可能フィールド
    - ベクトル検索フィールド (_vector サフィックス)
  - セマンティック検索設定を自動構成

- **`index_document_with_schema(document, filename, file_url, schema)`** (完全書き換え)
  - スキーマベースのインデックスにドキュメントを登録
  - 各フィールドごとにコンテンツを抽出
  - 各フィールドに対して個別にembeddingを生成
  - スキーマ専用インデックスに保存

- **`_extract_field_content(full_content: str, field)`**
  - フィールド名に基づいてコンテンツから関連部分を抽出
  - 将来的にAzure AI Content Understandingで高度化予定

- **`hybrid_search(query, top_k, include_images, schema_id)`** (パラメータ追加)
  - schema_idパラメータを追加
  - スキーマ指定時はスキーマ専用インデックスを検索

- **`_hybrid_search_schema_index(query, top_k, include_images, schema_id)`**
  - スキーマベースインデックスでのハイブリッド検索
  - 複数のベクトルフィールドに対して並列検索
  - フィールドごとの結果を統合

- **`_hybrid_search_default_index(query, top_k, include_images)`**
  - デフォルトインデックスでの検索 (既存ロジックを分離)

#### 変更した既存メソッド:

- **`__init__`**: `self.schema_indexes` 辞書を追加してスキーマとインデックスのマッピングを管理

### 2. `/backend/app/models.py`

#### 変更:
- **`SearchRequest`** モデルに `schema_id: Optional[str]` フィールドを追加

### 3. `/backend/app/main.py`

#### 変更:

- **`upload_document`** エンドポイント:
  - `schema_id` パラメータを `Form` として受け取り
  - スキーマの検証を追加
  - バックグラウンド処理にスキーマを渡す

- **`search`** エンドポイント:
  - `request.schema_id` を `hybrid_search` に渡す
  - ログにスキーマIDを記録

### 4. 新規ドキュメント

- `/docs/SCHEMA_BASED_INDEXING.md`: 実装の詳細説明とAPI使用方法

## アーキテクチャ

### インデックス構造

#### デフォルトインデックス (スキーマなし)
```
excel-search-index
├── id (key)
├── filename
├── content (全テキスト結合)
├── content_vector (1つのベクトル)
├── source_url
├── image_urls
└── metadata
```

#### スキーマベースインデックス (例: 12フィールド)
```
excel-search-index-schema-abc123def456
├── id (key)
├── filename
├── source_url
├── schema_id
├── schema_name
├── metadata
├── [ユーザー定義フィールド1]
├── [ユーザー定義フィールド1_vector]
├── [ユーザー定義フィールド2]
├── [ユーザー定義フィールド2_vector]
└── ... (12フィールド × 2 = 24個のユーザーフィールド)
```

## 動作フロー

### 1. スキーマ作成
```
POST /schemas
→ SchemaService.create_schema()
→ スキーマ定義をメモリに保存
```

### 2. ファイルアップロード (スキーマあり)
```
POST /upload (with schema_id)
→ バックグラウンド処理開始
→ Excel処理 (テキスト・画像抽出)
→ LLMで画像を説明文に変換
→ SearchService.index_document_with_schema()
  → SearchService.create_schema_based_index() (初回のみ)
  → 各フィールドのコンテンツ抽出
  → 各フィールドのembedding生成
  → スキーマ専用インデックスに登録
```

### 3. 検索 (スキーマ指定)
```
POST /search (with schema_id)
→ SearchService.hybrid_search(schema_id=xxx)
→ SearchService._hybrid_search_schema_index()
  → 複数ベクトルフィールドで検索
  → セマンティック + キーワード検索
  → 結果を統合して返す
```

## 主な特徴

### 1. フィールドごとのベクトル化
- 各フィールドが独立したembeddingを持つ
- フィールド特化型の検索が可能

### 2. 動的インデックス生成
- スキーマ定義に基づいて自動的にインデックスを作成
- フィールド数や型に応じて柔軟に対応

### 3. マルチベクトル検索
- クエリに対して複数のベクトルフィールドを並列検索
- 関連度の高いフィールドを自動判定

### 4. スキーマの分離
- スキーマごとにインデックスが分離
- 異なるフォーマットのExcelファイルを最適に扱える

## 使用例

### 12フィールドスキーマでの実際の使用

```json
{
  "name": "作業標準書フォーマットA",
  "fields": [
    {"name": "作業名", "data_type": "text"},
    {"name": "目的", "data_type": "text"},
    {"name": "準備物", "data_type": "text"},
    {"name": "手順1", "data_type": "text"},
    {"name": "手順1の画像", "data_type": "image"},
    {"name": "手順2", "data_type": "text"},
    {"name": "手順2の画像", "data_type": "image"},
    {"name": "手順3", "data_type": "text"},
    {"name": "手順3の画像", "data_type": "image"},
    {"name": "注意事項", "data_type": "text"},
    {"name": "完了確認", "data_type": "text"},
    {"name": "備考", "data_type": "text"}
  ]
}
```

このスキーマでインデックスを作成すると:
- **12個のテキスト/画像説明フィールド**
- **12個のベクトルフィールド** (各フィールドに対応)
- **合計24個のユーザー定義フィールド** + 6個のメタデータフィールド

## 検索精度の向上

### フィールド単位の精度向上

従来:
```
content: "作業名: 配線作業\n目的: 安全な配線\n準備物: ドライバー、ニッパー..."
content_vector: [0.1, 0.2, ..., 0.9]  # 全体の平均ベクトル
```

クエリ: "準備物は何ですか?"
→ 全コンテンツから検索 (精度低)

スキーマベース:
```
作業名: "配線作業"
作業名_vector: [0.1, 0.3, ...]

準備物: "ドライバー、ニッパー、絶縁テープ"
準備物_vector: [0.5, 0.8, ...]  # 準備物に特化したベクトル

手順1: "まず電源を切ります"
手順1_vector: [0.2, 0.1, ...]
```

クエリ: "準備物は何ですか?"
→ 準備物フィールドのベクトルで検索 (精度高)

## 今後の拡張

1. **Azure AI Content Understanding統合**
   - Excelの構造を自動認識
   - カラムヘッダーとフィールドの自動マッチング

2. **スキーマテンプレート**
   - よく使うスキーマをテンプレート化
   - ワンクリックでスキーマ適用

3. **マルチスキーマ検索**
   - 複数のスキーマにまたがる横断検索
   - スキーマ間の関連性を考慮

4. **フィールド単位の重み付け**
   - 検索時に特定フィールドを優先
   - フィールドごとのブースト設定

## テスト方法

### 1. スキーマ作成のテスト
```bash
curl -X POST http://localhost:8000/schemas \
  -H "Content-Type: application/json" \
  -d @test_schema.json
```

### 2. アップロードのテスト
```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@test.xlsx" \
  -F "schema_id=<作成したスキーマID>"
```

### 3. 検索のテスト
```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "テストクエリ",
    "schema_id": "<スキーマID>",
    "top_k": 5
  }'
```

### 4. Azure Portalでインデックス確認

1. Azure Portal > Azure AI Search
2. インデックスタブ
3. `excel-search-index-schema-*` で始まるインデックスを確認
4. フィールド一覧で24個のユーザー定義フィールドを確認

## 制限事項

### 現在の実装

1. **フィールド抽出**: キーワードベースの簡易実装
   - フィールド名をキーワードとしてコンテンツを検索
   - プロダクションではAI-based抽出が必要

2. **画像フィールド**: 画像URL管理が未完成
   - 画像フィールドの説明文はインデックス化
   - 画像URLの保存・返却ロジックは要改善

3. **スキーマ永続化**: メモリ内のみ
   - サーバー再起動でスキーマ情報が消失
   - プロダクションではDBへの保存が必要

4. **ベクトル検索の制限**: 最初の5フィールドのみ
   - Azure AI Searchのクエリ制限を考慮
   - 重要フィールドの優先順位付けが必要

## パフォーマンス考慮事項

### インデックス作成
- 初回のみ実行 (2回目以降はスキップ)
- フィールド数に比例して時間がかかる

### Embedding生成
- 各フィールドごとに実行
- 12フィールド → 12回のAzure OpenAI呼び出し
- 並列化で高速化可能

### 検索
- 最大5つのベクトルフィールドを並列検索
- セマンティックランキングで結果を統合

## まとめ

この実装により、ユーザーが定義したスキーマに基づいて、Excelファイルの各フィールドごとに最適化されたインデックスを構築できるようになりました。従来の単一`content`フィールドへの結合とは異なり、フィールド単位での精密な検索が可能になり、検索精度が大幅に向上することが期待されます。

**12フィールドのスキーマ例では、24個のユーザー定義フィールド(12テキスト + 12ベクトル)がインデックスに作成されます。**
