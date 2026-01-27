# Excel Schema-Based Indexing - Usage Examples

## Example 1: Creating a Schema for Product Inspection Records

### Schema Definition
```json
{
  "name": "製品検査記録",
  "description": "製品の品質検査に関する記録",
  "fields": [
    {
      "name": "検査項目",
      "data_type": "text",
      "description": "検査する項目の名称と基準"
    },
    {
      "name": "検査結果",
      "data_type": "text",
      "description": "実際の検査結果の記録"
    },
    {
      "name": "参考画像",
      "data_type": "image",
      "description": "検査時に撮影した写真"
    }
  ]
}
```

### Using the API
```bash
# Create schema
curl -X POST http://localhost:8000/api/schemas \
  -H "Content-Type: application/json" \
  -d '{
    "name": "製品検査記録",
    "description": "製品の品質検査に関する記録",
    "fields": [
      {"name": "検査項目", "data_type": "text"},
      {"name": "検査結果", "data_type": "text"},
      {"name": "参考画像", "data_type": "image"}
    ]
  }'

# Response
{
  "id": "abc123-def456-...",
  "name": "製品検査記録",
  "description": "製品の品質検査に関する記録",
  "fields": [...],
  "created_at": "2026-01-24T05:50:00Z"
}
```

### Upload with Schema
```bash
# Upload Excel file with schema
curl -X POST http://localhost:8000/api/upload \
  -F "file=@inspection_report.xlsx" \
  -F "schema_id=abc123-def456-..."

# Response
{
  "success": true,
  "message": "Document upload started. Use job_id to check progress.",
  "filename": "inspection_report.xlsx",
  "job_id": "xyz789-..."
}
```

## Example 2: Creating a Schema for Work Instructions

### Schema Definition
```json
{
  "name": "作業手順書",
  "description": "製造現場の作業手順",
  "fields": [
    {
      "name": "手順説明",
      "data_type": "text",
      "description": "各工程の詳細な説明"
    },
    {
      "name": "図解",
      "data_type": "image",
      "description": "作業手順を示す図や写真"
    },
    {
      "name": "注意事項",
      "data_type": "text",
      "description": "安全上の注意点や品質管理のポイント"
    }
  ]
}
```

### Search Example
```bash
# Search for safety information
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "安全確認の手順を教えてください",
    "top_k": 5,
    "include_images": true
  }'

# Response (AI determines "注意事項" field is relevant)
{
  "query": "安全確認の手順を教えてください",
  "results": [
    {
      "answer": "安全確認の手順: 1. 保護具の着用確認 2. 機械の停止確認...",
      "images": ["https://...safety_check.png"],
      "source_document": "work_instruction.xlsx",
      "source_url": "https://...",
      "score": 0.95,
      "schema_name": "作業手順書"
    }
  ],
  "total_results": 1
}
```

## Example 3: Frontend Usage

### Step 1: Load Schemas
```typescript
import { listSchemas } from './api';

const schemas = await listSchemas();
console.log(schemas);
// [
//   { id: "...", name: "製品検査記録", fields: [...] },
//   { id: "...", name: "作業手順書", fields: [...] }
// ]
```

### Step 2: Create New Schema (Using Component)
In the UI:
1. Click "+ 新規作成" button
2. Enter schema details:
   - Name: "製品仕様書"
   - Description: "製品の技術仕様と詳細"
3. Add fields:
   - Field 1: "製品名" (text)
   - Field 2: "仕様詳細" (text)
   - Field 3: "製品画像" (image)
4. Click "保存"

### Step 3: Upload with Schema
```typescript
import { uploadDocument } from './api';

// User selects schema and file in UI
const schemaId = "abc123-...";
const file = document.getElementById('fileInput').files[0];

const response = await uploadDocument(file, schemaId);
console.log(response);
// {
//   success: true,
//   job_id: "xyz789-...",
//   filename: "product_spec.xlsx"
// }
```

## Example 4: Schema Management

### List All Schemas
```bash
curl http://localhost:8000/api/schemas

# Response
[
  {
    "id": "schema-1",
    "name": "製品検査記録",
    "fields": [...]
  },
  {
    "id": "schema-2",
    "name": "作業手順書",
    "fields": [...]
  }
]
```

### Get Specific Schema
```bash
curl http://localhost:8000/api/schemas/schema-1

# Response
{
  "id": "schema-1",
  "name": "製品検査記録",
  "description": "製品の品質検査に関する記録",
  "fields": [
    {"name": "検査項目", "data_type": "text"},
    {"name": "検査結果", "data_type": "text"},
    {"name": "参考画像", "data_type": "image"}
  ],
  "created_at": "2026-01-24T05:50:00Z"
}
```

### Update Schema
```bash
curl -X PUT http://localhost:8000/api/schemas/schema-1 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "製品検査記録（更新版）",
    "description": "製品の品質検査に関する詳細記録",
    "fields": [
      {"name": "検査項目", "data_type": "text"},
      {"name": "検査結果", "data_type": "text"},
      {"name": "合否判定", "data_type": "text"},
      {"name": "参考画像", "data_type": "image"}
    ]
  }'
```

### Delete Schema
```bash
curl -X DELETE http://localhost:8000/api/schemas/schema-1

# Response
{
  "success": true,
  "message": "Schema deleted successfully"
}
```

## Example 5: Advanced Search with Field Filtering

### Query about inspection items (AI detects "検査項目" field is relevant)
```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "外観検査の項目は何ですか",
    "top_k": 3
  }'

# AI determines that "検査項目" field is most relevant
# Searches primarily in that field's content
```

### Query about results (AI detects "検査結果" field is relevant)
```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "前回の検査結果を教えてください",
    "top_k": 3
  }'

# AI determines that "検査結果" field is most relevant
# Returns focused results from that field
```

## Testing the Implementation

### 1. Test Schema Creation
```bash
# Test creating multiple schemas
for schema in "製品検査記録" "作業手順書" "製品仕様書"; do
  curl -X POST http://localhost:8000/api/schemas \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$schema\", \"fields\": [{\"name\": \"test\", \"data_type\": \"text\"}]}"
done
```

### 2. Test Upload with Schema
```bash
# Upload without schema (default behavior)
curl -X POST http://localhost:8000/api/upload \
  -F "file=@test.xlsx"

# Upload with schema
curl -X POST http://localhost:8000/api/upload \
  -F "file=@test.xlsx" \
  -F "schema_id=schema-1"
```

### 3. Test Search
```bash
# Search after uploading with schema
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "top_k": 5}'

# Check if schema_name appears in results
```

## Tips and Best Practices

### 1. Schema Design
- Keep field names descriptive and consistent
- Use appropriate data types (text for textual content, image for visual content)
- Add descriptions to help AI understand field purposes

### 2. Field Organization
- Group related information in the same field
- Separate different types of content (e.g., procedures vs. warnings)
- Consider how users will search for information

### 3. Upload Strategy
- Use schemas for documents with consistent structure
- Use default processing for ad-hoc or varied documents
- Test with sample files before bulk uploads

### 4. Search Optimization
- Phrase queries clearly to help AI identify relevant fields
- Use specific keywords related to field content
- Review results to refine schema definitions if needed

### 5. Maintenance
- Regularly review and update schemas based on usage patterns
- Archive outdated schemas instead of deleting
- Document schema purposes and use cases
