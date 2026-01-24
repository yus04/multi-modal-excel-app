# AI自動翻訳によるフィールド名の英語化

## 概要

日本語などの非ASCII文字を含むフィールド名を、生成AIを使って意味のある英語フィールド名に自動変換する機能を実装しました。

## 主な機能

### 1. AI翻訳 (`_translate_field_name_to_english`)

日本語フィールド名を生成AI (GPT) を使って意味のある英語フィールド名に変換します。

**変換例:**
```
"作業名" → "work_name"
"管理番号" → "management_number"
"準備物" → "preparation_items"
"手順1" → "step_1"
"手順1の画像" → "step_1_image"
"注意事項" → "precautions"
"完了確認" → "completion_check"
"備考" → "remarks"
```

### 2. キャッシュ機能

同じフィールド名の再変換を避けるため、翻訳結果をメモリにキャッシュします。

```python
self.field_name_cache = {}  # Maps original field name to English field name
```

これにより：
- 同じフィールド名が複数のスキーマで使われている場合、AI呼び出しは1回のみ
- インデックス作成とドキュメントインデックス時で一貫性を保証
- APIコストの削減

### 3. ASCII名前はそのまま使用

既にASCII文字のみのフィールド名は翻訳せず、サニタイゼーションのみ実行します。

```
"Item_Name" → "item_name" (翻訳なし、小文字化のみ)
"user_id" → "user_id" (そのまま)
```

## 実装詳細

### AI翻訳プロンプト

```python
prompt = """Convert the following field name to a valid English field name for a database.

Field name: {field_name} (Description: {field_description})

Requirements:
1. Use English only (ASCII characters)
2. Use snake_case format (lowercase with underscores)
3. Start with a letter (a-z)
4. Use only letters, numbers, and underscores
5. Be descriptive and concise (max 50 characters)
6. If it's a numbered field (like "手順1"), include the number (e.g., "step_1")

Examples:
- "作業名" -> "work_name"
- "管理番号" -> "management_number"
- "準備物" -> "preparation_items"
- "手順1" -> "step_1"
- "手順1の画像" -> "step_1_image"
- "注意事項" -> "precautions"

Respond with ONLY the English field name, nothing else."""
```

### サニタイゼーション処理 (`_sanitize_ascii_field_name`)

AI翻訳後、Azure AI Searchの要件に完全準拠するための追加処理：

1. 小文字に変換
2. 非英数字をアンダースコアに変換
3. 連続するアンダースコアを1つに統合
4. 先頭・末尾のアンダースコアを削除
5. 英字で始まらない場合は `field_` プレフィックスを追加
6. 100文字に制限

## 使用例

### スキーマ作成

```bash
curl -X POST http://localhost:8000/schemas \
  -H "Content-Type: application/json" \
  -d '{
    "name": "作業標準書フォーマット",
    "description": "製造現場の作業手順書",
    "fields": [
      {"name": "管理番号", "data_type": "text", "description": "ドキュメントの識別番号"},
      {"name": "作業名", "data_type": "text", "description": "作業の名称"},
      {"name": "目的", "data_type": "text", "description": "作業の目的と目標"},
      {"name": "準備物", "data_type": "text", "description": "必要な道具や材料"},
      {"name": "手順1", "data_type": "text", "description": "最初の手順"},
      {"name": "手順1の画像", "data_type": "image", "description": "手順1の説明画像"},
      {"name": "手順2", "data_type": "text", "description": "2番目の手順"},
      {"name": "手順2の画像", "data_type": "image", "description": "手順2の説明画像"},
      {"name": "注意事項", "data_type": "text", "description": "安全上の注意点"},
      {"name": "完了確認", "data_type": "text", "description": "作業完了の確認項目"},
      {"name": "備考", "data_type": "text", "description": "その他の補足情報"}
    ]
  }'
```

### 自動生成されるインデックスフィールド

上記のスキーマから以下のフィールドが自動生成されます：

```
インデックス: excel-search-index-schema-abc123

メタデータフィールド:
- id (key)
- filename
- source_url
- schema_id
- schema_name
- metadata

ユーザー定義フィールド (AIが自動翻訳):
- management_number (テキスト) ← "管理番号"
- management_number_vector (ベクトル)
- work_name (テキスト) ← "作業名"
- work_name_vector (ベクトル)
- purpose (テキスト) ← "目的"
- purpose_vector (ベクトル)
- preparation_items (テキスト) ← "準備物"
- preparation_items_vector (ベクトル)
- step_1 (テキスト) ← "手順1"
- step_1_vector (ベクトル)
- step_1_image (テキスト) ← "手順1の画像"
- step_1_image_vector (ベクトル)
- step_2 (テキスト) ← "手順2"
- step_2_vector (ベクトル)
- step_2_image (テキスト) ← "手順2の画像"
- step_2_image_vector (ベクトル)
- precautions (テキスト) ← "注意事項"
- precautions_vector (ベクトル)
- completion_check (テキスト) ← "完了確認"
- completion_check_vector (ベクトル)
- remarks (テキスト) ← "備考"
- remarks_vector (ベクトル)

合計: 6 メタデータ + 22 ユーザー定義 = 28 フィールド
```

## ログ出力例

```
INFO - Translated field name: '管理番号' -> 'management_number'
INFO - Translated field name: '作業名' -> 'work_name'
INFO - Translated field name: '準備物' -> 'preparation_items'
DEBUG - Using cached field name: '手順1' -> 'step_1'
INFO - Created schema-based index excel-search-index-schema-abc123 with 11 user-defined fields
```

## 利点

### 1. 意味のあるフィールド名

従来: `field_`, `field__2`, `field__3` (意味不明)
↓
新方式: `work_name`, `preparation_items`, `step_1` (意味が明確)

### 2. 重複回避

日本語フィールドが同じ汎用名に変換される問題を解決
- "手順1" → `step_1`
- "手順2" → `step_2`
- "手順3" → `step_3`

各フィールドがユニークな名前を持ちます。

### 3. 国際化対応

- データベースやAPIで標準的な英語フィールド名を使用
- 他システムとの連携が容易
- ドキュメントやコードが読みやすい

### 4. フィールド説明の活用

フィールドの`description`を翻訳のコンテキストとして使用し、より正確な翻訳を実現。

例：
```json
{
  "name": "品番",
  "description": "製品の部品番号"
}
```
→ `part_number` (より具体的)

```json
{
  "name": "品番",
  "description": "製品の品質番号"
}
```
→ `quality_number` (コンテキストに応じて変化)

## パフォーマンス

### AI呼び出し回数

- 初回インデックス作成時: フィールド数と同じ回数
- 2回目以降: 0回 (キャッシュから取得)
- ドキュメントインデックス時: 0回 (キャッシュ済み)

**例**: 11フィールドのスキーマ
- インデックス作成: 11回のAI呼び出し
- ドキュメント10件追加: 0回のAI呼び出し
- 合計: 11回のみ

### レスポンス時間

- AI翻訳: 約0.5-1秒/フィールド
- キャッシュヒット: < 0.001秒
- 11フィールドの初回作成: 約5-10秒
- 11フィールドの2回目以降: 即座

## エラーハンドリング

AI翻訳が失敗した場合のフォールバック処理:

```python
except Exception as e:
    logger.error(f"Error translating field name '{field_name}': {str(e)}")
    # Fallback: use a safe default with hash
    fallback = f"field_{hash(field_name) % 10000}"
    self.field_name_cache[cache_key] = fallback
    return fallback
```

これにより、AI呼び出しが失敗してもシステムは継続動作します。

## Azure AI Searchでの確認

インデックス作成後、Azure Portalで確認できます：

1. Azure Portal → Azure AI Search リソース
2. インデックス → `excel-search-index-schema-*`
3. フィールド一覧で英語フィールド名を確認

例:
```
Fields:
✓ id (Edm.String)
✓ filename (Edm.String)
✓ management_number (Edm.String)
✓ management_number_vector (Collection(Edm.Single))
✓ work_name (Edm.String)
✓ work_name_vector (Collection(Edm.Single))
✓ preparation_items (Edm.String)
✓ preparation_items_vector (Collection(Edm.Single))
...
```

## ベストプラクティス

### 1. フィールド説明を記載

より正確な翻訳のため、必ず`description`を指定してください。

❌ 悪い例:
```json
{"name": "品番", "data_type": "text"}
```

✅ 良い例:
```json
{"name": "品番", "data_type": "text", "description": "製品の部品番号"}
```

### 2. 一意性のあるフィールド名

同じ種類のフィールドには番号や識別子を含めてください。

❌ 悪い例:
```
"手順" → step (複数あると重複)
"手順" → step (重複!)
```

✅ 良い例:
```
"手順1" → step_1
"手順2" → step_2
"手順3" → step_3
```

### 3. 既に英語の場合

英語フィールド名を使用する場合はsnake_case形式で記載すると、AI翻訳をスキップできます。

```json
{"name": "work_name", "data_type": "text"}  // AI翻訳スキップ
```

## トラブルシューティング

### AI翻訳が遅い

**原因**: Azure OpenAIのレート制限やレイテンシ

**対策**:
- フィールド数を減らす
- 既に英語のフィールド名を使用 (翻訳スキップ)
- キャッシュが効いているか確認

### 翻訳結果が期待と異なる

**原因**: フィールド名だけではコンテキスト不足

**対策**:
- `description` を詳しく記載
- フィールド名自体をより具体的にする

例:
```json
// 曖昧
{"name": "番号", "data_type": "text"}
→ "number" (汎用的)

// 具体的
{"name": "管理番号", "data_type": "text", "description": "ドキュメントの識別番号"}
→ "management_number" or "document_id" (明確)
```

### キャッシュのクリア

サーバーを再起動するとキャッシュがクリアされます。翻訳をやり直したい場合:

```bash
# バックエンドを再起動
cd /home/yu/multi-modal-excel-app/backend
pkill -f uvicorn
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## まとめ

この実装により：

✅ 日本語フィールド名を意味のある英語名に自動変換  
✅ フィールド重複の問題を解決  
✅ Azure AI Searchの要件に完全準拠  
✅ キャッシュ機能でパフォーマンス最適化  
✅ エラーハンドリングで堅牢性を確保  

ユーザーは日本語でスキーマを定義しても、バックエンドで自動的に適切な英語フィールド名が生成され、Azure AI Searchで最適なインデックスが構築されます。
