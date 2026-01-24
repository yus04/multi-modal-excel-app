# Excel Schema-Based Indexing and Search Implementation

## 概要 (Overview)

このドキュメントでは、Azure AI Search、Azure AI Content Understanding、Azure OpenAI Service を使用した、Excelファイルのスキーマベースのインデックス作成と検索機能の実装について説明します。

## 実装された機能 (Implemented Features)

### 1. スキーマ管理 (Schema Management)

#### バックエンド (Backend)
- **データモデル**: `FieldDefinition`, `ExcelSchema`, `SchemaCreateRequest`
- **サービス**: `SchemaService` - インメモリストレージでスキーマのCRUD操作を提供
- **APIエンドポイント**:
  - `GET /schemas` - 全スキーマのリスト取得
  - `POST /schemas` - 新規スキーマ作成
  - `GET /schemas/{id}` - 特定スキーマの取得
  - `PUT /schemas/{id}` - スキーマの更新
  - `DELETE /schemas/{id}` - スキーマの削除

#### フロントエンド (Frontend)
- **SchemaSelector**: 既存スキーマの選択コンポーネント
  - スキーマの一覧表示
  - スキーマなし（デフォルト処理）オプション
  - 選択したスキーマの詳細表示
- **SchemaCreator**: 新規スキーマ作成コンポーネント
  - フィールドの動的追加・削除（+ボタン、🗑️ボタン）
  - フィールド名、データ型（テキスト/画像）、説明の設定
  - バリデーション機能

### 2. アップロードフロー (Upload Flow)

#### 変更点
- `POST /upload` エンドポイントが `schema_id` パラメータを受け付けるように拡張
- スキーマ選択UIをアップロードセクションに統合
- バックグラウンド処理でスキーマを使用したインデックス作成

#### ワークフロー
1. ユーザーがスキーマを選択または新規作成
2. Excelファイルを選択
3. アップロードボタンをクリック
4. バックエンドがスキーマIDを受け取り、スキーマベースの処理を実行

### 3. フィールドベースのインデックス作成 (Field-Based Indexing)

#### `index_document_with_schema` メソッド
スキーマ定義に基づいてドキュメントをインデックス化:

```python
def index_document_with_schema(document, filename, file_url, schema):
    # 各フィールドについて:
    for field in schema.fields:
        if field.data_type == FieldDataType.TEXT:
            # テキストコンテンツを抽出
            # ベクトル化 (field_name_vector)
        elif field.data_type == FieldDataType.IMAGE:
            # 画像説明を生成 (GPT-5.2使用)
            # ベクトル化 (field_name_vector)
```

#### 処理内容
1. **テキストフィールド**: 
   - Excelからテキストを抽出
   - 将来的にAzure AI Content Understandingを使用可能
   - 埋め込みベクトルを生成

2. **画像フィールド**:
   - 画像を抽出
   - GPT-5.2で画像を文章化
   - テキスト化した内容のベクトルを生成

3. **メタデータ**:
   - スキーマID、スキーマ名
   - フィールドデータ
   - `has_schema` フラグ

### 4. AI駆動のフィールドフィルタリング検索 (AI-Powered Field Filtering Search)

#### `_determine_relevant_fields` メソッド
生成AIを使用してユーザーの質問に関連するフィールドを判断:

```python
def _determine_relevant_fields(query, schema):
    # AIに質問を送信
    # スキーマの全フィールドから関連するものを選択
    # 関連フィールド名のリストを返す
```

#### 検索の拡張
- スキーマベースのドキュメントを検出
- メタデータからスキーマ情報を取得
- 関連フィールドのみに絞った検索（基盤実装済み）
- 検索結果にスキーマ名を含める

## ファイル構造 (File Structure)

### バックエンド
```
backend/app/
├── models.py              # データモデル（FieldDefinition, ExcelSchemaなど）
├── schema_service.py      # スキーマ管理サービス
├── search_service.py      # 検索サービス（スキーマベースインデックス作成を含む）
├── main.py               # FastAPI エンドポイント
└── ...
```

### フロントエンド
```
frontend/src/
├── components/
│   ├── SchemaSelector.tsx     # スキーマ選択コンポーネント
│   ├── SchemaSelector.css
│   ├── SchemaCreator.tsx      # スキーマ作成コンポーネント
│   └── SchemaCreator.css
├── types.ts                   # TypeScript型定義
├── api.ts                    # API クライアント関数
├── App.tsx                   # メインアプリケーション
└── ...
```

## 使用方法 (Usage)

### 1. スキーマの作成

1. アップロードセクションで「+ 新規作成」ボタンをクリック
2. スキーマ名と説明を入力
3. フィールドを追加:
   - フィールド名を入力
   - データ型を選択（テキスト/画像）
   - 説明を入力（任意）
4. 「+ フィールドを追加」で追加フィールドを作成
5. 「保存」をクリック

### 2. スキーマを使用したアップロード

1. ドロップダウンからスキーマを選択
2. Excelファイルを選択
3. 「アップロード」をクリック
4. 処理状況を確認

### 3. 検索

- 通常通り検索を実行
- スキーマベースのドキュメントは、検索結果にスキーマ名が表示されます
- AIが自動的に関連フィールドを判断して検索を最適化

## 技術的詳細 (Technical Details)

### スキーマストレージ
- 現在: インメモリ辞書
- 本番環境: データベース（PostgreSQL, MongoDB等）への移行を推奨

### ベクトル化
- 各フィールドごとに個別のベクトルを生成
- フィールド名に `_vector` サフィックスを付与
- 次元数: 1536 (text-embedding-3-small)

### インデックス構造
現在の実装では、既存のインデックス構造を使用し、スキーマ情報をメタデータに格納:

```json
{
  "id": "base64_encoded_id",
  "filename": "example.xlsx",
  "content": "[フィールド1]\n内容1\n\n[フィールド2]\n内容2",
  "content_vector": [0.1, 0.2, ...],
  "metadata": {
    "schema_id": "uuid",
    "schema_name": "製品検査記録",
    "has_schema": true,
    "field_data": {
      "フィールド1": "内容1",
      "フィールド2": "内容2"
    }
  }
}
```

### 将来の拡張 (Future Enhancements)

1. **動的インデックススキーマ**:
   - スキーマごとに専用のフィールドを持つ動的インデックスの作成
   - 各フィールド専用のベクトルフィールド

2. **高度なフィールド抽出**:
   - Azure AI Content Understandingの統合
   - Excelのセル位置に基づく正確なフィールドマッピング
   - カスタムフィールド抽出ロジック

3. **フィールド固有の検索**:
   - 選択されたフィールドのみでのベクトル検索
   - フィールドベースのフィルタリング
   - 重み付けによる検索精度の向上

4. **スキーマバージョニング**:
   - スキーマの履歴管理
   - 異なるバージョンのスキーマのサポート

## セキュリティ考慮事項 (Security Considerations)

- スキーマの作成・編集権限の管理
- アップロード時のスキーマ検証
- 不正なフィールド定義の防止
- APIエンドポイントの認証・認可

## パフォーマンス (Performance)

### 現在の実装
- スキーマ情報: インメモリ（高速）
- フィールド抽出: 同期処理
- ベクトル生成: OpenAI API呼び出し

### 最適化案
- スキーマキャッシング
- 並列フィールド処理
- バッチベクトル生成
- 結果キャッシング

## トラブルシューティング (Troubleshooting)

### スキーマが保存されない
- サーバー再起動後、インメモリストレージがリセットされます
- 永続化のためにデータベースを使用してください

### フィールドが正しく抽出されない
- 現在の実装は簡易版です
- Azure AI Content Understandingを統合してください
- カスタム抽出ロジックを実装してください

### 検索結果にスキーマ情報が表示されない
- スキーマを使用してアップロードされたドキュメントのみ
- メタデータに `has_schema: true` が設定されているか確認

## まとめ (Conclusion)

この実装は、Excelファイルのスキーマベースのインデックス作成と検索の基盤を提供します。ユーザー定義のスキーマに基づいて、テキストと画像の両方を処理し、AIを活用した高精度な検索を実現します。

本番環境への展開前に、永続化ストレージの実装、Azure AI Content Understandingの統合、および詳細なフィールド抽出ロジックの実装を推奨します。
