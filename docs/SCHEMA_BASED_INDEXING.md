# スキーマベースのインデックス構築機能

## 概要

このアプリケーションは、ユーザーが定義したスキーマに基づいて、Excelファイルを各フィールドごとに分割してインデックスを構築する機能を実装しています。

## 主な変更点

### 1. 動的インデックス作成 (`SearchService.create_schema_based_index`)

- ユーザーが定義したスキーマごとに専用のAzure AI Searchインデックスを作成
- 各フィールドに対して以下を自動生成：
  - テキスト検索可能なフィールド (`field_name`)
  - ベクトル検索用のフィールド (`field_name_vector`)

**例**: 12個のフィールドを持つスキーマの場合
- 12個のテキストフィールド
- 12個のベクトルフィールド
- 合計24個のユーザー定義フィールド + 6個のメタデータフィールド = 30フィールド

### 2. スキーマベースのドキュメントインデックス (`SearchService.index_document_with_schema`)

- 各フィールドごとにコンテンツを抽出
- 各フィールドの内容に対して個別にembeddingを生成
- フィールドごとに検索可能な状態でインデックスに保存

### 3. スキーマベースの検索 (`SearchService.hybrid_search`)

- `schema_id`パラメータを指定すると、そのスキーマ専用インデックスを検索
- 複数のベクトルフィールドに対してハイブリッド検索を実行
- セマンティック検索とキーワード検索を併用

## API使用方法

### スキーマの作成

```bash
curl -X POST http://localhost:8000/schemas \
  -H "Content-Type: application/json" \
  -d '{
    "name": "作業標準書フォーマットA",
    "description": "作業手順書用のスキーマ",
    "fields": [
      {"name": "作業名", "data_type": "text", "description": "作業の名称"},
      {"name": "目的", "data_type": "text", "description": "作業の目的"},
      {"name": "準備物", "data_type": "text", "description": "必要な道具や材料"},
      {"name": "手順1", "data_type": "text", "description": "最初の手順"},
      {"name": "手順1の画像", "data_type": "image", "description": "手順1の説明画像"},
      {"name": "手順2", "data_type": "text", "description": "2番目の手順"},
      {"name": "手順2の画像", "data_type": "image", "description": "手順2の説明画像"},
      {"name": "手順3", "data_type": "text", "description": "3番目の手順"},
      {"name": "手順3の画像", "data_type": "image", "description": "手順3の説明画像"},
      {"name": "注意事項", "data_type": "text", "description": "作業時の注意点"},
      {"name": "完了確認", "data_type": "text", "description": "作業完了の確認項目"},
      {"name": "備考", "data_type": "text", "description": "その他の補足情報"}
    ]
  }'
```

**レスポンス例**:
```json
{
  "id": "abc123-def456-ghi789",
  "name": "作業標準書フォーマットA",
  "description": "作業手順書用のスキーマ",
  "fields": [...],
  "created_at": "2026-01-24T10:00:00",
  "updated_at": "2026-01-24T10:00:00"
}
```

### スキーマベースのファイルアップロード

```bash
curl -X POST http://localhost:8000/upload \
  -F "file=@作業標準書.xlsx" \
  -F "schema_id=abc123-def456-ghi789"
```

このアップロード時に、以下が自動的に実行されます：

1. スキーマ専用のインデックスが存在しない場合は自動作成
2. Excelファイルから各フィールドに該当するコンテンツを抽出
3. 各フィールドごとにembeddingを生成
4. スキーマベースのインデックスにドキュメントを登録

### スキーマベースの検索

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "準備物は何ですか？",
    "schema_id": "abc123-def456-ghi789",
    "top_k": 5,
    "include_images": true
  }'
```

`schema_id`を指定すると：
- そのスキーマ専用のインデックスを検索
- 各フィールドのベクトル検索を実行
- 関連する複数フィールドの内容を統合して回答を生成

## インデックスの構造

### デフォルトインデックス (スキーマなし)
```
- id (key)
- filename
- content (全テキストが結合)
- content_vector (1つのベクトル)
- source_url
- image_urls
- metadata
```

### スキーマベースインデックス (12フィールドの例)
```
- id (key)
- filename
- source_url
- schema_id
- schema_name
- metadata

# ユーザー定義フィールド (12個)
- 作業名 (テキスト)
- 作業名_vector (ベクトル)
- 目的 (テキスト)
- 目的_vector (ベクトル)
- 準備物 (テキスト)
- 準備物_vector (ベクトル)
- 手順1 (テキスト)
- 手順1_vector (ベクトル)
- 手順1の画像 (テキスト)
- 手順1の画像_vector (ベクトル)
... (以下同様に12フィールド × 2 = 24フィールド)
```

## 技術的な詳細

### フィールド名のサニタイゼーション

Azure AI Searchのフィールド名は英数字とアンダースコアのみ許可されるため、日本語のフィールド名は自動的に変換されます：

```python
safe_field_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in field_name)
```

### フィールド抽出ロジック

現在の実装では、`_extract_field_content`メソッドがフィールド名をキーワードとしてコンテンツ内を検索し、関連する部分を抽出します。

**プロダクション環境での改善点**:
- Azure AI Content Understandingを使用してExcelの構造を理解
- カラムヘッダーやセクション見出しとフィールド定義をマッチング
- より正確なフィールドごとのコンテンツ抽出

### ベクトル検索の最適化

スキーマベースの検索では、複数のベクトルフィールドに対して並列で検索を実行：

```python
vector_queries = []
for vector_field in vector_fields[:5]:  # 最初の5フィールドに制限
    vector_queries.append({
        "kind": "vector",
        "vector": query_vector,
        "fields": vector_field,
        "k": top_k * 2
    })
```

## 利点

1. **フィールド単位の検索精度向上**
   - 各フィールドごとにベクトル化されるため、特定の情報タイプに対する検索精度が向上

2. **スキーマごとの最適化**
   - 異なるExcelフォーマットごとに最適なインデックス構造を構築

3. **スケーラビリティ**
   - 新しいスキーマを追加してもインデックスが分離されているため影響なし

4. **柔軟性**
   - ユーザーが自由にフィールドを定義可能
   - TEXT型とIMAGE型をサポート

## 今後の改善予定

1. **Azure AI Content Understanding統合**
   - Excelの構造を自動認識
   - フィールド抽出精度の向上

2. **画像フィールドの改善**
   - 画像とフィールドの対応付けの最適化
   - 画像URLの保存と検索結果への含め方

3. **マルチスキーマ検索**
   - 複数のスキーマにまたがる検索をサポート

4. **スキーマの更新・削除**
   - スキーマ変更時のインデックス再構築
   - スキーマ削除時のインデックスクリーンアップ

## トラブルシューティング

### インデックスが作成されない

ログを確認してください：
```
logger.info(f"Created schema-based index {schema_index_name} with {len(schema.fields)} user-defined fields")
```

### フィールドが抽出されない

`_extract_field_content`のログレベルをDEBUGに設定：
```python
logger.setLevel(logging.DEBUG)
```

### 検索結果が返ってこない

- `schema_id`が正しいか確認
- インデックスにドキュメントが登録されているか確認
- Azure Portal > Azure AI Search > インデックスを確認
