# システムアーキテクチャ

## 概要

Excel 作業標準書検索システムは、マルチモーダル RAG（Retrieval-Augmented Generation）を活用した検索システムです。Azure の各種 AI サービスを統合し、Excel ファイルから手順を抽出し、テキストと画像を組み合わせた検索を提供します。

## アーキテクチャ図

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend Layer                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  React Application (TypeScript + Vite)                    │  │
│  │  - Search UI                                              │  │
│  │  - Upload UI                                              │  │
│  │  - Results Display with Images                           │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP/REST API
                         │ (CORS enabled)
┌────────────────────────┴────────────────────────────────────────┐
│                        Backend Layer (FastAPI)                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  API Endpoints                                           │   │
│  │  - POST /upload   : Document upload & processing        │   │
│  │  - POST /search   : Hybrid search                       │   │
│  │  - GET  /health   : Health check                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Business Logic                                          │   │
│  │  ┌────────────────┐  ┌─────────────────┐               │   │
│  │  │ Excel          │  │ LLM Service     │               │   │
│  │  │ Processor      │  │ (GPT-4.1)        │               │   │
│  │  └────────────────┘  └─────────────────┘               │   │
│  │  ┌────────────────┐  ┌─────────────────┐               │   │
│  │  │ Blob Storage   │  │ Search Service  │               │   │
│  │  │ Service        │  │ (Hybrid RAG)    │               │   │
│  │  └────────────────┘  └─────────────────┘               │   │
│  └─────────────────────────────────────────────────────────┘   │
└────────────────────────┬────────────────────────────────────────┘
                         │ Azure SDK
┌────────────────────────┴────────────────────────────────────────┐
│                       Azure Services Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │ Azure OpenAI │  │  Azure AI    │  │  Azure Blob Storage  │ │
│  │              │  │   Search     │  │                      │ │
│  │ - GPT-4.1     │  │              │  │ - Excel Files        │ │
│  │ - Embeddings │  │ - Vector DB  │  │ - Images             │ │
│  │              │  │ - Hybrid     │  │                      │ │
│  │              │  │   Search     │  │                      │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## レイヤー構成

### 1. Frontend Layer (プレゼンテーション層)

**技術スタック**
- React 18.2 (TypeScript)
- Vite (開発サーバー & ビルドツール)
- Axios (HTTP クライアント)

**責務**
- ユーザーインターフェースの提供
- ファイルアップロード機能
- 検索クエリの入力
- 検索結果の表示（テキスト + 画像）
- エラーハンドリングとフィードバック

**主要コンポーネント**
- `App.tsx`: メインアプリケーションコンポーネント
- `api.ts`: バックエンド API 呼び出し
- `types.ts`: TypeScript 型定義

### 2. Backend Layer (アプリケーション層)

**技術スタック**
- FastAPI (Python Web フレームワーク)
- Uvicorn (ASGI サーバー)
- Pydantic (データバリデーション)

**責務**
- API エンドポイントの提供
- ビジネスロジックの実行
- Azure サービスとの統合
- データ処理とバリデーション
- エラーハンドリング

**主要モジュール**

#### main.py
- FastAPI アプリケーションの初期化
- エンドポイントの定義
- CORS ミドルウェアの設定
- サービスの初期化

#### excel_processor.py
- Excel ファイルからテキスト抽出
- Excel ファイルから画像抽出
- レイアウト情報の保持

#### llm_service.py
- GPT-4.1 による手順の構造化
- マルチモーダル LLM 処理
- JSON スキーマ定義

#### blob_service.py
- Azure Blob Storage へのアップロード
- ファイル・画像の保存
- URL の生成

#### search_service.py
- Azure AI Search インデックス管理
- ベクトル検索
- キーワード検索
- セマンティックランキング
- 埋め込みベクトルの生成

### 3. Azure Services Layer (インフラストラクチャ層)

**Azure OpenAI Service**
- **GPT-4.1**: 手順の構造化、要約生成
- **text-embedding-3-small**: テキストの埋め込みベクトル生成

**Azure AI Search**
- ベクトル検索 (HNSW アルゴリズム)
- キーワード検索 (全文検索)
- セマンティックランキング
- インデックス管理

**Azure Blob Storage**
- Excel ファイルの保存
- 抽出した画像の保存
- 公開 URL の提供

**Azure Document Intelligence** (オプション)
- PDF レイアウト解析
- 表構造の認識
- OCR 処理

## データフロー

### ドキュメント処理パイプライン

```
1. Excel Upload
   ↓
2. Extract Text & Images (openpyxl)
   - テキスト: シート、行、セルの内容
   - 画像: 埋め込み画像の抽出、位置情報の保持
   ↓
3. Upload to Blob Storage
   - Excel ファイルのアップロード
   - 画像のアップロード (PNG 形式)
   ↓
4. Structure with GPT-4.1
   - 手順番号の抽出
   - タイトルと説明の生成
   - 画像との関連付け
   ↓
5. Generate Embeddings
   - text-embedding-3-small による埋め込み生成
   - 1536 次元ベクトル
   ↓
6. Index to Azure AI Search
   - ドキュメントのインデックス化
   - ベクトル、テキスト、メタデータの保存
   ↓
7. Complete
```

### 検索フロー

```
1. User Query Input
   ↓
2. Generate Query Embedding
   - text-embedding-3-small でクエリをベクトル化
   ↓
3. Hybrid Search
   - ベクトル検索: セマンティック類似性
   - キーワード検索: 全文検索
   - 両者のスコアを統合
   ↓
4. Semantic Re-ranking
   - Azure AI Search のセマンティックランキング
   - より関連性の高い結果を上位に
   ↓
5. Fetch Images from Blob Storage
   - 検索結果に関連する画像 URL を取得
   ↓
6. Return Results
   - 手順情報
   - 画像 URL
   - 出典リンク
   - 関連度スコア
```

## データモデル

### データベーススキーマ (Azure AI Search Index)

```json
{
  "name": "excel-procedures-index",
  "fields": [
    {
      "name": "id",
      "type": "Edm.String",
      "key": true,
      "searchable": false
    },
    {
      "name": "step_number",
      "type": "Edm.String",
      "searchable": true,
      "filterable": true
    },
    {
      "name": "title",
      "type": "Edm.String",
      "searchable": true
    },
    {
      "name": "description",
      "type": "Edm.String",
      "searchable": true
    },
    {
      "name": "source_document",
      "type": "Edm.String",
      "filterable": true
    },
    {
      "name": "source_url",
      "type": "Edm.String",
      "searchable": false
    },
    {
      "name": "page_number",
      "type": "Edm.Int32",
      "filterable": true
    },
    {
      "name": "image_urls",
      "type": "Collection(Edm.String)",
      "searchable": false
    },
    {
      "name": "metadata",
      "type": "Edm.String",
      "searchable": false
    },
    {
      "name": "content_vector",
      "type": "Collection(Edm.Single)",
      "dimensions": 1536,
      "vectorSearchProfile": "myHnswProfile"
    }
  ]
}
```

## セキュリティアーキテクチャ

### 認証・認可 (将来実装)

```
User → Azure AD → JWT Token → API Gateway → Backend
```

### データ保護

- **転送時の暗号化**: HTTPS/TLS
- **保存時の暗号化**: Azure Storage Service Encryption
- **キー管理**: Azure Key Vault (推奨)

### アクセス制御

- **CORS**: 許可されたオリジンからのみアクセス
- **RBAC**: Azure リソースへのロールベースアクセス
- **Network Security**: Virtual Network、Private Endpoint

## スケーラビリティ

### 水平スケーリング

- **Frontend**: CDN (Azure Front Door)
- **Backend**: Azure App Service (複数インスタンス)
- **Search**: Azure AI Search (自動スケーリング)
- **Storage**: Azure Blob Storage (自動スケーリング)

### パフォーマンス最適化

1. **キャッシング**
   - Redis Cache for検索結果
   - CDN for静的コンテンツ
   - Blob Storage CDN for画像

2. **非同期処理**
   - ファイルアップロード: バックグラウンドジョブ
   - インデックス作成: キューベース処理

3. **接続プーリング**
   - データベース接続
   - HTTP クライアント接続

## モニタリングとロギング

### Azure Monitor 統合

```
Application Insights
  ↓
- Request/Response ログ
- エラーログ
- パフォーマンスメトリクス
- カスタムイベント
```

### ログレベル

- **INFO**: 正常な処理フロー
- **WARNING**: 非致命的な問題
- **ERROR**: エラー発生
- **CRITICAL**: システム停止レベルのエラー

## 災害復旧

### バックアップ戦略

- **Blob Storage**: GRS (Geo-redundant storage)
- **AI Search**: レプリカの作成
- **設定**: Infrastructure as Code (Terraform/ARM)

### 復旧手順

1. リソースの再作成
2. バックアップからのデータ復元
3. インデックスの再構築
4. 動作確認

## 今後の拡張

### フェーズ 2
- Azure Document Intelligence の統合
- PDF サポート
- より高度なレイアウト解析

### フェーズ 3
- ユーザー認証・認可
- マルチテナント対応
- 高度な権限管理

### フェーズ 4
- リアルタイム更新通知
- 協調フィルタリング
- レコメンデーション機能

### フェーズ 5
- モバイルアプリ
- オフライン機能
- AR による作業支援

## パフォーマンス目標

| 指標 | 目標値 |
|------|--------|
| 検索レスポンスタイム | < 3秒 |
| ファイルアップロード処理 | < 5分 |
| 同時接続ユーザー数 | 50人 |
| 可用性 | 99.9% |
| エラー率 | < 0.1% |

## コスト見積もり (月額)

### 開発環境
- Azure OpenAI: ~$50
- Azure AI Search (Basic): ~$75
- Azure Blob Storage: ~$5
- Azure App Service: ~$0 (Free Tier)
- **合計**: ~$130/月

### 本番環境
- Azure OpenAI: ~$500
- Azure AI Search (Standard): ~$250
- Azure Blob Storage: ~$50
- Azure App Service: ~$200
- **合計**: ~$1,000/月

---

**注意**: コストは使用量により変動します。正確な見積もりは Azure Pricing Calculator をご利用ください。
