# Azure 環境構築ガイド

このドキュメントでは、Excel作業標準書検索システムを動作させるために必要なAzureリソースのセットアップ手順を説明します。

## 前提条件

- Azure アカウント（有効なサブスクリプション）
- Azure CLI または Azure Portal へのアクセス
- 適切な権限（リソース作成権限）

## リソース一覧

以下のAzureリソースが必要です：

1. Azure OpenAI Service
2. Azure AI Search
3. Azure Blob Storage
4. Azure Document Intelligence（オプション）

## 1. Azure OpenAI Service のセットアップ

### ポータルでの作成

1. Azure Portal にログイン
2. 「リソースの作成」→「Azure OpenAI」を検索
3. 以下の情報を入力：
   - サブスクリプション：使用するサブスクリプション
   - リソースグループ：新規作成または既存を選択
   - リージョン：East US または Japan East を推奨
   - 名前：一意の名前（例：`excel-search-openai`）
   - 価格レベル：Standard S0

### モデルのデプロイ

1. 作成したリソースに移動
2. 「モデルのデプロイ」→「デプロイの作成」
3. 以下のモデルをデプロイ：
   - **GPT-4o**
     - デプロイ名：`gpt-4o`（または任意の名前）
     - モデル：`gpt-4o`
     - バージョン：最新
   - **text-embedding-ada-002**
     - デプロイ名：`text-embedding-ada-002`
     - モデル：`text-embedding-ada-002`
     - バージョン：2

### 資格情報の取得

1. リソースの「キーとエンドポイント」に移動
2. 以下の情報をメモ：
   - エンドポイント：`https://your-resource.openai.azure.com/`
   - キー 1：API キー

## 2. Azure AI Search のセットアップ

### サービスの作成

1. Azure Portal で「リソースの作成」
2. 「Azure AI Search」を検索
3. 以下の情報を入力：
   - サブスクリプション：使用するサブスクリプション
   - リソースグループ：OpenAIと同じグループを推奨
   - サービス名：一意の名前（例：`excel-search-service`）
   - 場所：OpenAIと同じリージョンを推奨
   - 価格レベル：Basic 以上（セマンティック検索が必要）

### セマンティック検索の有効化

1. 作成したサービスに移動
2. 「設定」→「セマンティック検索」
3. 「無料」または「標準」プランを選択

### 資格情報の取得

1. 「キー」に移動
2. 以下の情報をメモ：
   - URL：`https://your-search-service.search.windows.net`
   - プライマリ管理キー：API キー

## 3. Azure Blob Storage のセットアップ

### ストレージアカウントの作成

1. Azure Portal で「リソースの作成」
2. 「ストレージアカウント」を検索
3. 以下の情報を入力：
   - サブスクリプション：使用するサブスクリプション
   - リソースグループ：既存のグループを選択
   - ストレージアカウント名：一意の名前（例：`excelsearchstorage`）
   - 地域：他のリソースと同じリージョン
   - パフォーマンス：Standard
   - 冗長性：LRS（ローカル冗長ストレージ）

### コンテナーの作成

1. 作成したストレージアカウントに移動
2. 「データストレージ」→「コンテナー」
3. 「+ コンテナー」をクリック
4. コンテナー名：`excel-files`
5. パブリックアクセスレベル：「プライベート」（推奨）

### CORS の設定（フロントエンドから直接アクセスする場合）

1. 「設定」→「リソース共有（CORS）」
2. Blob service で以下を設定：
   - 許可されるオリジン：`http://localhost:5173,http://localhost:3000`
   - 許可されるメソッド：GET, POST, PUT
   - 許可されるヘッダー：*
   - 公開されるヘッダー：*
   - 最大期間：200

### 資格情報の取得

1. 「アクセスキー」に移動
2. 「接続文字列」をコピー

## 4. Azure Document Intelligence のセットアップ（オプション）

### サービスの作成

1. Azure Portal で「リソースの作成」
2. 「Document Intelligence」を検索
3. 以下の情報を入力：
   - サブスクリプション：使用するサブスクリプション
   - リソースグループ：既存のグループを選択
   - 地域：他のリソースと同じリージョン
   - 名前：一意の名前（例：`excel-search-di`）
   - 価格レベル：Free F0 または Standard S0

### 資格情報の取得

1. リソースの「キーとエンドポイント」に移動
2. 以下の情報をメモ：
   - エンドポイント：`https://your-di-resource.cognitiveservices.azure.com/`
   - キー 1：API キー

## 5. 環境変数の設定

取得した資格情報を `.env` ファイルに設定します：

```bash
cd backend
cp .env.template .env
```

`.env` ファイルを編集：

```env
# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-openai-api-key
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
AZURE_OPENAI_API_VERSION=2024-02-15-preview

# Azure AI Search Configuration
AZURE_SEARCH_ENDPOINT=https://your-search-service.search.windows.net
AZURE_SEARCH_API_KEY=your-search-api-key
AZURE_SEARCH_INDEX_NAME=excel-procedures-index

# Azure Blob Storage Configuration
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_STORAGE_CONTAINER_NAME=excel-files

# Azure Document Intelligence Configuration (Optional)
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://your-di-resource.cognitiveservices.azure.com/
AZURE_DOCUMENT_INTELLIGENCE_API_KEY=your-di-api-key

# Application Configuration
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
```

## 6. 動作確認

### バックエンドの起動

```bash
cd backend
source venv/bin/activate  # Windows: venv\Scripts\activate
python -m uvicorn app.main:app --reload
```

### ヘルスチェック

ブラウザまたはcurlで以下にアクセス：

```bash
curl http://localhost:8000/health
```

正常な応答：

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

## セキュリティのベストプラクティス

### 1. Azure Key Vault の使用（推奨）

本番環境では、Azure Key Vaultを使用して資格情報を管理することを強く推奨します。

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://your-keyvault.vault.azure.net/", credential=credential)

openai_key = client.get_secret("openai-api-key").value
```

### 2. マネージドIDの使用

可能な限り、マネージドIDを使用してAzureサービス間の認証を行います。

### 3. ネットワークセキュリティ

- Virtual Networkを使用してリソースを分離
- Private Endpointを使用して公開エンドポイントへのアクセスを制限
- Network Security Groupsでトラフィックを制御

### 4. アクセス制御

- RBACを使用して最小権限の原則を適用
- Azure AD認証を有効化
- 定期的にアクセスキーをローテーション

## コスト最適化

### 推奨設定

1. **開発環境**
   - Azure OpenAI：従量課金
   - AI Search：Basic
   - Blob Storage：Standard LRS
   - Document Intelligence：Free F0

2. **本番環境**
   - Azure OpenAI：予約容量の検討
   - AI Search：Standard（自動スケーリング有効）
   - Blob Storage：Standard GRS（冗長性向上）
   - Document Intelligence：Standard S0

### コスト監視

1. Azure Cost Management を使用して支出を追跡
2. アラートを設定して予算超過を防止
3. 使用していないリソースを定期的に削除

## トラブルシューティング

### OpenAI接続エラー

- エンドポイントURLが正しいか確認
- APIキーが有効か確認
- デプロイメント名が正しいか確認
- クォータ制限を確認

### AI Search接続エラー

- サービスURLが正しいか確認
- 管理キーが有効か確認
- セマンティック検索が有効か確認

### Blob Storage接続エラー

- 接続文字列が正しいか確認
- コンテナーが存在するか確認
- CORS設定を確認

## サポート

問題が解決しない場合は、以下をご確認ください：

1. Azureステータスページで障害がないか確認
2. Azure Portalのリソース診断を実行
3. アプリケーションログを確認
4. GitHub Issuesで質問を投稿

---

**次のステップ**: [README.md](../README.md) に従ってアプリケーションをセットアップしてください。
