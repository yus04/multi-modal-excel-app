# API ドキュメント

Excel 作業標準書検索システム API リファレンス

## ベース URL

開発環境: `http://localhost:8000`

## 認証

現在、認証は実装されていません。本番環境では Azure AD または他の認証メカニズムの実装を推奨します。

## エンドポイント一覧

### 1. ヘルスチェック

システムの稼働状態を確認します。

```
GET /health
```

**レスポンス**

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

**ステータスコード**
- `200 OK`: システムが正常に動作している
- `500 Internal Server Error`: サービスの一部が利用できない

---

### 2. ルートエンドポイント

API の基本情報を返します。

```
GET /
```

**レスポンス**

```json
{
  "message": "Multi-Modal Excel Search API",
  "version": "1.0.0",
  "status": "running"
}
```

---

### 3. ドキュメントのアップロード

Excel ファイルをアップロードして処理します。

```
POST /upload
```

**リクエスト**

Content-Type: `multipart/form-data`

| パラメータ | 型 | 必須 | 説明 |
|----------|-----|------|------|
| file | File | Yes | Excel ファイル (.xlsx, .xls) |

**レスポンス**

```json
{
  "success": true,
  "message": "Document uploaded and processed successfully",
  "filename": "work_procedure.xlsx",
  "document_id": "work_procedure.xlsx",
  "steps_extracted": 5
}
```

**レスポンスフィールド**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| success | boolean | 処理の成否 |
| message | string | 処理結果のメッセージ |
| filename | string | アップロードされたファイル名 |
| document_id | string | ドキュメントの一意識別子 |
| steps_extracted | integer | 抽出された手順の数 |

**ステータスコード**
- `200 OK`: ファイルが正常に処理された
- `400 Bad Request`: 無効なファイル形式
- `500 Internal Server Error`: 処理中にエラーが発生

**エラーレスポンス例**

```json
{
  "detail": "Only Excel files (.xlsx, .xls) are supported"
}
```

**処理フロー**

1. Excel ファイルを受信
2. Azure Blob Storage にアップロード
3. テキストと画像を抽出
4. GPT-4o で手順を構造化
5. 画像を Blob Storage にアップロード
6. Azure AI Search にインデックス化

---

### 4. 検索

作業手順を検索します。

```
POST /search
```

**リクエスト**

Content-Type: `application/json`

```json
{
  "query": "組み立て手順",
  "top_k": 5,
  "include_images": true
}
```

**リクエストパラメータ**

| パラメータ | 型 | 必須 | デフォルト | 説明 |
|----------|-----|------|----------|------|
| query | string | Yes | - | 検索クエリ |
| top_k | integer | No | 5 | 返す結果の最大数 (1-20) |
| include_images | boolean | No | true | 画像を含めるかどうか |

**レスポンス**

```json
{
  "query": "組み立て手順",
  "results": [
    {
      "step_number": "1",
      "title": "部品の準備",
      "summary": "必要な部品を準備します。部品Aと部品Bを取り出し、作業台に配置してください。",
      "images": [
        "https://storage.blob.core.windows.net/excel-files/images/work_procedure_sheet0_img0.png"
      ],
      "source_document": "work_procedure.xlsx",
      "source_url": "https://storage.blob.core.windows.net/excel-files/work_procedure.xlsx",
      "score": 0.95,
      "page_number": 1
    }
  ],
  "total_results": 1,
  "message": null
}
```

**レスポンスフィールド**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| query | string | 検索クエリ |
| results | array | 検索結果のリスト |
| total_results | integer | 結果の総数 |
| message | string\|null | 追加メッセージ（結果がない場合など） |

**検索結果オブジェクト**

| フィールド | 型 | 説明 |
|-----------|-----|------|
| step_number | string | 手順番号 |
| title | string | 手順のタイトル |
| summary | string | 手順の要約（最大500文字） |
| images | array[string] | 関連画像の URL リスト |
| source_document | string | 元のドキュメント名 |
| source_url | string | 元のドキュメントの URL |
| score | float | 関連度スコア (0.0-1.0) |
| page_number | integer\|null | ページ番号 |

**ステータスコード**
- `200 OK`: 検索が正常に完了
- `400 Bad Request`: 無効なリクエストパラメータ
- `500 Internal Server Error`: 検索中にエラーが発生

**結果がない場合のレスポンス**

```json
{
  "query": "存在しない手順",
  "results": [],
  "total_results": 0,
  "message": "検索結果が見つかりませんでした。標準書に記載されていない内容の可能性があります。"
}
```

**検索の種類**

このエンドポイントは以下の検索を組み合わせています：

1. **ベクトル検索**: クエリの意味的類似性に基づく検索
2. **キーワード検索**: 全文検索によるキーワードマッチング
3. **セマンティックランキング**: Azure AI Search による結果の再ランク

---

## データモデル

### ProcedureStep

手順を表すデータモデル

```typescript
{
  step_number: string;      // 手順番号
  title: string;            // タイトル
  description: string;      // 詳細説明
  images: string[];         // 画像 URL のリスト
  metadata: {               // メタデータ
    sheet?: string;         // シート名
    row_start?: number;     // 開始行
    row_end?: number;       // 終了行
    page_number?: number;   // ページ番号
  }
}
```

---

## エラーハンドリング

### エラーレスポンス形式

```json
{
  "detail": "エラーメッセージ"
}
```

### 共通エラーコード

| ステータスコード | 説明 |
|----------------|------|
| 400 Bad Request | リクエストパラメータが無効 |
| 404 Not Found | リソースが見つからない |
| 500 Internal Server Error | サーバー内部エラー |
| 503 Service Unavailable | Azure サービスが利用できない |

---

## レート制限

現在、レート制限は実装されていません。本番環境では以下を推奨します：

- API ゲートウェイの使用
- リクエスト数の制限（例：100リクエスト/分）
- Azure OpenAI のクォータ管理

---

## CORS 設定

以下のオリジンからのアクセスが許可されています：

- `http://localhost:3000`
- `http://localhost:5173`

本番環境では、適切なオリジンを `.env` ファイルで設定してください。

---

## 使用例

### Python (requests)

```python
import requests

# ファイルのアップロード
with open('work_procedure.xlsx', 'rb') as f:
    files = {'file': f}
    response = requests.post('http://localhost:8000/upload', files=files)
    print(response.json())

# 検索
search_data = {
    "query": "組み立て手順",
    "top_k": 5,
    "include_images": True
}
response = requests.post('http://localhost:8000/search', json=search_data)
print(response.json())
```

### JavaScript (Axios)

```javascript
import axios from 'axios';

// ファイルのアップロード
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const uploadResponse = await axios.post('http://localhost:8000/upload', formData, {
  headers: { 'Content-Type': 'multipart/form-data' }
});
console.log(uploadResponse.data);

// 検索
const searchResponse = await axios.post('http://localhost:8000/search', {
  query: '組み立て手順',
  top_k: 5,
  include_images: true
});
console.log(searchResponse.data);
```

### cURL

```bash
# ファイルのアップロード
curl -X POST http://localhost:8000/upload \
  -F "file=@work_procedure.xlsx"

# 検索
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "組み立て手順", "top_k": 5, "include_images": true}'
```

---

## セキュリティ考慮事項

### 本番環境での推奨事項

1. **認証・認可の実装**
   - Azure AD 認証
   - JWT トークンベースの認証
   - OAuth 2.0

2. **入力バリデーション**
   - ファイルサイズの制限
   - ファイル形式の厳密なチェック
   - SQL インジェクション対策

3. **暗号化**
   - HTTPS の使用
   - データの暗号化（保存時・転送時）

4. **監視とログ**
   - アクセスログの記録
   - エラーログの監視
   - Azure Monitor の活用

---

## バージョニング

現在のバージョン: `1.0.0`

将来的にはAPIバージョニングの実装を検討します（例：`/v1/search`）。

---

## サポート

API に関する質問や問題は、GitHub Issues でお知らせください。

https://github.com/yus04/multi-modal-excel-app/issues
