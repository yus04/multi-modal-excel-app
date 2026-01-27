# Excel 作業標準書の画像付き検索システム

製造業向けマルチモーダル RAG デモアプリケーション - Excel ファイルから作業手順を抽出し、画像付きで検索できるシステム

## 🎯 概要

このシステムは、Excel 形式の作業標準書から手順を自動抽出し、テキストと画像を組み合わせた高度な検索機能を提供します。Azure AI サービスを活用したマルチモーダル検索により、現場作業者が必要な情報を素早く正確に見つけることができます。

### 主な特徴

- **📊 Excel ファイル処理**: Excel ファイルからテキストと画像を自動抽出
- **🤖 マルチモーダル AI**: Azure OpenAI (GPT-4o) による画像の自動説明生成とコンテンツ統合
- **🔍 ハイブリッド検索**: ベクトル検索 + キーワード検索 + セマンティック検索
- **🖼️ 画像同時表示**: 検索結果に関連画像を自動で表示
- **📎 出典リンク**: 元の Excel ファイルへのリンクを提供
- **🚫 推測禁止**: 標準書に記載された内容のみを返答

## 🏗️ システム構成

### アーキテクチャ

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   React     │────▶│    FastAPI       │────▶│  Azure Services │
│  Frontend   │     │    Backend       │     │                 │
└─────────────┘     └──────────────────┘     │  - AI Search    │
                                               │  - Blob Storage │
                                               │  - OpenAI       │
                                               │  - Document AI  │
                                               └─────────────────┘
```

### 技術スタック

**フロントエンド**
- React 18.2 with TypeScript
- Vite (ビルドツール)
- Axios (HTTP クライアント)

**バックエンド**
- FastAPI (Python Web フレームワーク)
- Uvicorn (ASGI サーバー)
- Pydantic (データバリデーション)

**Azure サービス**
- Azure OpenAI Service (GPT-4o with Vision, text-embedding-3-small)
- Azure AI Search (ハイブリッド + セマンティック検索)
- Azure Blob Storage (ファイル保存)
- Azure Document Intelligence (文書解析)

## 📋 機能要件

### 1. ドキュメント処理パイプライン
- Excel ファイルのアップロード (.xlsx, .xls)
- テキストと画像の自動抽出（位置情報を含む）
- GPT-4o による画像の説明文生成
- テキストと画像説明を位置情報に基づいて統合
- 統合コンテンツのベクトル化
- Azure Blob Storage へのアップロード
- Azure AI Search へのインデックス作成（1ファイル = 1ドキュメント）

### 2. 検索機能
- **ハイブリッド検索**
  - ベクトル検索 (セマンティック類似性)
  - キーワード検索 (全文検索)
  - セマンティックランキング (結果の再ランク)
- **AI回答生成**
  - LLMによる質問への回答生成
  - 必要な情報のみを抽出
  - 関連画像の自動選択
- **検索結果表示**
  - 質問に対する回答テキスト
  - 関連画像のみ表示
  - 出典ファイルへのリンク
  - 関連度スコア

### 3. ユーザーインターフェース
- ファイルアップロード UI
- 検索ボックス
- 検索結果カード表示
- 画像ギャラリー
- レスポンシブデザイン

## 🚀 セットアップ

### 前提条件

- Python 3.9+
- Node.js 18+
- Azure アカウント
- 以下の Azure リソース:
  - Azure OpenAI Service
  - Azure AI Search
  - Azure Blob Storage
  - Azure AI Content Understanding

### 1. リポジトリのクローン

```bash
git clone https://github.com/yus04/multi-modal-excel-app.git
cd multi-modal-excel-app
```

### 2. バックエンドのセットアップ

```bash
cd backend

# 仮想環境の作成
python -m venv .venv
source .venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係のインストール
pip install -r requirements.txt

# 環境変数の設定
cp .env.template .env
# .env ファイルを編集して Azure の資格情報を設定
```

#### .env ファイルの設定

```env
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
# Deployment name should support vision API (e.g., gpt-4o, gpt-4-vision-preview)
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

# Azure AI Search Configuration
AZURE_SEARCH_ENDPOINT=https://your-search-service.search.windows.net
AZURE_SEARCH_API_KEY=your-search-api-key
AZURE_SEARCH_INDEX_NAME=excel-procedures-index

# Azure Blob Storage Configuration
AZURE_STORAGE_CONNECTION_STRING=your-connection-string
AZURE_STORAGE_CONTAINER_NAME=excel-files

# Azure AI Content Understanding Configuration
AZURE_CONTENT_UNDERSTANDING_ENDPOINT=https://your-openai-resource.openai.azure.com/
AZURE_CONTENT_UNDERSTANDING_API_KEY=your-content-understanding-api-key

# Application Configuration
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

### 3. フロントエンドのセットアップ

```bash
cd ../frontend

# 依存関係のインストール
npm install

# 開発サーバーの起動
npm run dev
```

### 4. アプリケーションの起動

**バックエンド (ターミナル 1)**
```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**フロントエンド (ターミナル 2)**
```bash
cd frontend
npm run dev
```

アプリケーションは http://localhost:5173 で利用可能になります。

## 📖 使用方法

### 1. Excel ファイルのアップロード

1. 「Excel ファイルのアップロード」セクションでファイルを選択
2. 「アップロード」ボタンをクリック
3. 処理完了まで待機 (数秒〜数分)
4. 成功メッセージと抽出された手順数を確認

### 2. 作業手順の検索

1. 検索ボックスにキーワードを入力
   - 例: 「組み立て手順」「品質チェック」「安全確認」
2. 「検索」ボタンをクリック
3. 検索結果を確認:
   - 質問に対する回答テキスト
   - 関連画像のみ表示
   - 出典ファイルへのリンク

### 3. 検索結果の活用

- **画像**: クリックして拡大表示
- **出典リンク**: クリックして元の Excel ファイルにアクセス
- **関連度スコア**: 検索クエリとの関連性を数値で表示

## 🔧 API エンドポイント

### POST /upload
Excel ファイルをアップロードして処理

**Request:**
```
Content-Type: multipart/form-data
file: Excel ファイル (.xlsx, .xls)
```

**Response:**
```json
{
  "success": true,
  "message": "Document uploaded and processed successfully",
  "filename": "example.xlsx",
  "document_id": "example.xlsx",
  "steps_extracted": 5
}
```

### POST /search
作業手順を検索

**Request:**
```json
{
  "query": "組み立て手順",
  "top_k": 5,
  "include_images": true
}
```

**Response:**
```json
{
  "query": "組み立て手順",
  "results": [
    {
      "answer": "必要な部品を準備します。部品A、部品B、部品Cを用意してください...",
      "images": ["https://..."],
      "source_document": "example.xlsx",
      "source_url": "https://...",
      "score": 0.95
    }
  ],
  "total_results": 1
}
```

### GET /health
システムのヘルスチェック

**Response:**
```json
{
  "status": "healthy",
  "services": {
    "blob_storage": true,
    "llm_service": true,
    "search_service": true
  }
}
```

## 🔐 セキュリティ

- Azure Key Vault を使用した資格情報管理を推奨
- CORS 設定による不正アクセスの防止
- HTTPS 通信の使用を推奨
- 環境変数を使用した機密情報の管理

## 📊 処理フロー

### ドキュメント処理パイプライン

```
Excel File Upload
    ↓
Extract Text & Images with Position (openpyxl)
    - テキスト: シート、行番号、セルの内容
    - 画像: 埋め込み画像、位置情報（行・列）
    ↓
Upload Images to Blob Storage
    - 画像のアップロード (PNG 形式)
    ↓
Generate Image Descriptions (GPT-4o Vision API)
    - 各画像の内容を日本語で説明
    ↓
Merge Text and Image Descriptions
    - テキストと画像説明を位置情報に基づいて統合
    - 画像の位置に説明文を挿入
    ↓
Generate Embeddings (text-embedding-3-small)
    - 統合されたコンテンツをベクトル化
    - 1536 次元ベクトル
    ↓
Index to Azure AI Search (1 file = 1 document)
    - content: 統合されたテキストと画像説明
    - content_vector: ベクトル化されたコンテンツ
    - image_urls: 画像表示用の URL リスト
    ↓
Complete
```

### 検索フロー

```
User Query
    ↓
Generate Query Embedding
    ↓
Hybrid Search (Vector + Keyword)
    ↓
Semantic Re-ranking
    ↓
Extract Relevant Information with LLM
    - 質問に関連する文章を抽出
    - 関連する画像のみを選択
    - 回答テキストを生成
    ↓
Return Results with Selected Images & References
```

## 🛠️ 開発

### バックエンド開発

```bash
cd backend

# テストの実行
pytest tests/

# コードフォーマット
black app/

# リンター
flake8 app/
```

### フロントエンド開発

```bash
cd frontend

# 開発サーバー
npm run dev

# ビルド
npm run build

# プレビュー
npm run preview

# リンター
npm run lint
```

## 📈 パフォーマンス最適化

- **ベクトル検索**: HNSW アルゴリズムによる高速な近似最近傍探索
- **セマンティックランキング**: Azure AI Search の組み込み機能
- **画像最適化**: PNG 形式での保存と適切なサイズ調整
- **キャッシング**: Blob Storage の CDN 統合を推奨

## 🐛 トラブルシューティング

### アップロードエラー
- Excel ファイルのフォーマットを確認
- ファイルサイズの制限を確認
- Azure Blob Storage の接続を確認

### 検索結果が表示されない
- Azure AI Search のインデックスが作成されているか確認
- OpenAI API の quota を確認
- ログでエラーメッセージを確認

### 画像が表示されない
- Blob Storage の公開設定を確認
- CORS 設定を確認
- 画像 URL が正しく生成されているか確認

## 📄 ライセンス

MIT License

---

**注意**: このシステムは製造業の作業標準書管理を想定していますが、他の業界や用途にも適用可能です。
