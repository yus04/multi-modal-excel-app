# Azure AI Content Understanding 実装完了

## 概要

Azure AI Document Intelligence から Azure AI Content Understanding への移行が完了しました。
Content Understanding は Azure OpenAI のマルチモーダル機能を使用して、ユーザー定義のスキーマに基づいてExcelファイルからフィールドを抽出します。

## 変更内容

### 1. 削除されたコンポーネント

- `azure-ai-formrecognizer` パッケージ（requirements.txt から削除）
- Document Intelligence 関連の設定（config.py）
- Document Intelligence 関連のドキュメント参照

### 2. 追加されたコンポーネント

#### ContentUnderstandingService クラス
- **ファイル**: `backend/app/content_understanding_service.py`
- **機能**: 
  - スキーマベースのフィールド抽出
  - マルチモーダルAIを使用したExcel解析
  - テキストと画像の統合処理

#### 主要メソッド

```python
def extract_fields_from_excel(
    text_content: List[Dict[str, Any]],
    images: List[Dict[str, Any]],
    schema: Dict[str, Any],
    filename: str
) -> Dict[str, Any]:
    """
    スキーマに基づいてExcelファイルからフィールドを抽出
    
    Args:
        text_content: Excelシートのテキストコンテンツ
        images: 抽出された画像リスト（base64エンコード済み）
        schema: フィールド定義を含むスキーマ
        filename: ファイル名
    
    Returns:
        抽出されたフィールドを含む辞書
    """
```

### 3. 統合された処理フロー

#### スキーマなしのアップロード（従来の処理）
```
Excel アップロード
  ↓
テキスト・画像抽出 (ExcelProcessor)
  ↓
画像説明生成 (MultiModalLLMService)
  ↓
コンテンツ統合
  ↓
デフォルトインデックスに保存 (SearchService)
```

#### スキーマありのアップロード（新機能）
```
Excel アップロード + スキーマID
  ↓
テキスト・画像抽出 (ExcelProcessor)
  ↓
スキーマベースのフィールド抽出 (ContentUnderstandingService)
  ↓
抽出フィールドをインデックスに保存 (SearchService)
  ↓
スキーマ専用インデックスに保存
```

### 4. 更新されたファイル

#### バックエンド
- `backend/requirements.txt` - 依存関係の更新
- `backend/app/config.py` - Content Understanding設定の追加
- `backend/app/main.py` - Content Understanding サービスの統合
- `backend/app/search_service.py` - スキーマベースのインデックス処理の更新
- `backend/app/content_understanding_service.py` - 新規作成

#### ドキュメント
- `README.md` - Content Understanding への参照を更新
- `backend/.env.template` - 環境変数テンプレートを更新
- `docs/architecture.md` - アーキテクチャ図を更新
- `docs/azure-setup.md` - セットアップ手順を更新

## 使用方法

### 1. 環境設定

`.env` ファイルに以下を追加（Azure OpenAI と同じエンドポイント）:

```env
AZURE_CONTENT_UNDERSTANDING_ENDPOINT=https://your-openai-resource.openai.azure.com/
AZURE_CONTENT_UNDERSTANDING_API_KEY=your-openai-api-key
```

### 2. スキーマの作成

```typescript
// フロントエンドでスキーマを作成
const schema = {
  name: "作業標準書",
  description: "製造現場の作業手順書",
  fields: [
    {
      name: "作業名",
      field_type: "text",
      description: "実施する作業の名称"
    },
    {
      name: "準備物",
      field_type: "text",
      description: "作業に必要な道具や材料"
    },
    {
      name: "手順1",
      field_type: "text",
      description: "最初の作業手順"
    }
  ]
};

// API経由でスキーマを作成
const response = await fetch('/schemas', {
  method: 'POST',
  body: JSON.stringify(schema)
});
```

### 3. スキーマを使用したアップロード

```typescript
// スキーマIDを指定してファイルをアップロード
const formData = new FormData();
formData.append('file', excelFile);
formData.append('schema_id', schemaId);

const response = await fetch('/upload', {
  method: 'POST',
  body: formData
});
```

### 4. スキーマベースの検索

```typescript
// スキーマIDを指定して検索
const response = await fetch('/search', {
  method: 'POST',
  body: JSON.stringify({
    query: "準備物は何ですか？",
    schema_id: schemaId,
    top_k: 5
  })
});
```

## 技術的な詳細

### フィールド名の翻訳

Azure AI Search のフィールド名は英語（ASCII）のみサポートしているため、日本語のフィールド名を自動的に英語に翻訳します。

例:
- "作業名" → "work_name"
- "準備物" → "preparation_items"
- "手順1" → "step_1"

この翻訳は GPT を使用して意味的に適切な英語名を生成し、キャッシュして再利用します。

### ベクトル化

各フィールドに対して以下が作成されます:
- テキストフィールド（検索可能）
- ベクトルフィールド（意味検索用）

例えば、"作業名" フィールドの場合:
- `work_name`: テキスト値
- `work_name_vector`: 埋め込みベクトル（1536次元）

### マルチモーダル処理

Content Understanding Service は以下の処理を行います:

1. **テキスト解析**: Excelシートのテキストコンテンツを解析
2. **画像処理**: 含まれる画像をBase64で処理
3. **マルチモーダルリクエスト**: GPT-4o にテキストと画像を送信
4. **フィールド抽出**: スキーマに基づいて構造化データを抽出

## メリット

### Document Intelligence との比較

| 項目 | Document Intelligence | Content Understanding |
|-----|---------------------|---------------------|
| **追加コスト** | あり（別サービス） | なし（OpenAI に含まれる） |
| **スキーマ対応** | 限定的 | 完全対応 |
| **マルチモーダル** | 限定的 | 完全対応 |
| **カスタマイズ** | 難しい | 柔軟 |
| **日本語対応** | 良好 | 優れている |

### 主な利点

1. **コスト削減**: 追加のサービス不要
2. **柔軟性**: ユーザー定義のスキーマに完全対応
3. **精度向上**: GPT-4o のマルチモーダル機能を活用
4. **統合性**: 既存の Azure OpenAI インフラを再利用

## 今後の拡張

### Phase 1（完了）
✅ Content Understanding Service の実装  
✅ スキーマベースのフィールド抽出  
✅ マルチモーダル処理  
✅ 動的インデックス作成

### Phase 2（計画中）
- [ ] フィールド抽出精度の向上
- [ ] 画像とテキストの位置関係の認識
- [ ] 複数シートの自動分割
- [ ] テーブル構造の認識

### Phase 3（将来）
- [ ] PDF サポート
- [ ] リアルタイム抽出プレビュー
- [ ] フィールド抽出の学習機能
- [ ] カスタムモデルのサポート

## トラブルシューティング

### 問題: フィールドが正しく抽出されない

**解決策:**
1. スキーマの `description` フィールドを詳細に記述
2. フィールド名を明確にする
3. Excel ファイルの構造を確認

### 問題: 画像が処理されない

**解決策:**
1. 画像サイズを確認（最大20MB）
2. 画像形式を確認（PNG、JPG サポート）
3. Azure OpenAI のクォータを確認

### 問題: 処理が遅い

**解決策:**
1. 画像数を制限（最初の5枚のみ処理）
2. スキーマのフィールド数を最適化
3. Azure OpenAI のデプロイメントをスケールアップ

## サポート

質問や問題がある場合は、以下を確認してください:
- [Azure OpenAI ドキュメント](https://learn.microsoft.com/azure/ai-services/openai/)
- [Azure AI Search ドキュメント](https://learn.microsoft.com/azure/search/)
- プロジェクトの Issue トラッカー
