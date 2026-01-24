# UI Component Guide - Schema Management

## Overview
This guide describes the new UI components added for schema-based Excel indexing.

## Component Layout

```
┌─────────────────────────────────────────────────────────────┐
│                  Excel 作業標準書検索システム                      │
│             画像付きマルチモーダル検索で作業手順を簡単に見つけます         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  📤 Excel ファイルのアップロード                                  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ スキーマを選択                                            │  │
│  │ ┌─────────────────────────────────┬────────────────┐  │  │
│  │ │ [スキーマなし（デフォルト処理）▼]      │ [+ 新規作成] │  │  │
│  │ └─────────────────────────────────┴────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ [ファイルを選択]          [アップロード]                   │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  🔍 作業手順の検索                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ [検索キーワードを入力...                    ] [検索]     │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 1. Schema Selector Component

### When No Schema Selected
```
┌──────────────────────────────────────────────────────────┐
│ スキーマを選択                                              │
│ ┌──────────────────────────────────────┬──────────────┐ │
│ │ スキーマなし（デフォルト処理）▼          │ [+ 新規作成] │ │
│ └──────────────────────────────────────┴──────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### When Schema Selected
```
┌──────────────────────────────────────────────────────────┐
│ スキーマを選択                                              │
│ ┌──────────────────────────────────────┬──────────────┐ │
│ │ 製品検査記録 (3個のフィールド) ▼      │ [+ 新規作成] │ │
│ └──────────────────────────────────────┴──────────────┘ │
│                                                          │
│ ┌────────────────────────────────────────────────────┐ │
│ │ 製品検査記録                                         │ │
│ │ 製品の品質検査に関する記録                           │ │
│ │                                                     │ │
│ │ フィールド:                                          │ │
│ │ • 検査項目 (テキスト)                                │ │
│ │ • 検査結果 (テキスト)                                │ │
│ │ • 参考画像 (画像)                                    │ │
│ └────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### Dropdown Options
```
┌──────────────────────────────────────┐
│ スキーマなし（デフォルト処理）          │ <- Default option
├──────────────────────────────────────┤
│ 製品検査記録 (3個のフィールド)         │
│ 作業手順書 (3個のフィールド)           │
│ 製品仕様書 (4個のフィールド)           │
└──────────────────────────────────────┘
```

## 2. Schema Creator Component

### Main Form
```
┌──────────────────────────────────────────────────────────┐
│ 新しいスキーマを作成                                         │
│                                                          │
│ スキーマ名 *                                              │
│ ┌────────────────────────────────────────────────────┐ │
│ │ 例: 製品検査記録                                      │ │
│ └────────────────────────────────────────────────────┘ │
│                                                          │
│ 説明                                                     │
│ ┌────────────────────────────────────────────────────┐ │
│ │ スキーマの説明を入力                                  │ │
│ └────────────────────────────────────────────────────┘ │
│                                                          │
│ フィールド定義                                            │
│ ┌─────────────────────────────────────────────┬─────┐ │
│ │ [フィールド名] [テキスト▼] [説明（任意）]    │ 🗑️ │ │
│ ├─────────────────────────────────────────────┼─────┤ │
│ │ [フィールド名] [画像▼] [説明（任意）]        │ 🗑️ │ │
│ └─────────────────────────────────────────────┴─────┘ │
│ [+ フィールドを追加]                                      │
│                                                          │
│ [保存]  [キャンセル]                                      │
└──────────────────────────────────────────────────────────┘
```

### Filled Example
```
┌──────────────────────────────────────────────────────────┐
│ 新しいスキーマを作成                                         │
│                                                          │
│ スキーマ名 *                                              │
│ ┌────────────────────────────────────────────────────┐ │
│ │ 製品検査記録                                          │ │
│ └────────────────────────────────────────────────────┘ │
│                                                          │
│ 説明                                                     │
│ ┌────────────────────────────────────────────────────┐ │
│ │ 製品の品質検査に関する記録                             │ │
│ └────────────────────────────────────────────────────┘ │
│                                                          │
│ フィールド定義                                            │
│ ┌─────────────────────────────────────────────┬─────┐ │
│ │ [検査項目] [テキスト▼] [検査する項目の名称]  │ 🗑️ │ │
│ ├─────────────────────────────────────────────┼─────┤ │
│ │ [検査結果] [テキスト▼] [実際の検査結果]      │ 🗑️ │ │
│ ├─────────────────────────────────────────────┼─────┤ │
│ │ [参考画像] [画像▼] [検査時の写真]            │ 🗑️ │ │
│ └─────────────────────────────────────────────┴─────┘ │
│ [+ フィールドを追加]                                      │
│                                                          │
│ [保存]  [キャンセル]                                      │
└──────────────────────────────────────────────────────────┘
```

### Error State
```
┌──────────────────────────────────────────────────────────┐
│ 新しいスキーマを作成                                         │
│                                                          │
│ ┌────────────────────────────────────────────────────┐ │
│ │ ⚠️ スキーマ名を入力してください                         │ │
│ └────────────────────────────────────────────────────┘ │
│                                                          │
│ スキーマ名 *                                              │
│ ┌────────────────────────────────────────────────────┐ │
│ │                                                     │ │
│ └────────────────────────────────────────────────────┘ │
│ ...                                                      │
└──────────────────────────────────────────────────────────┘
```

## 3. Field Data Types

### Text Field
- **Icon**: 📝
- **Use Case**: Textual content, descriptions, procedures
- **Processing**: Direct text extraction
- **Example**: "検査項目", "手順説明", "注意事項"

### Image Field
- **Icon**: 🖼️
- **Use Case**: Photos, diagrams, illustrations
- **Processing**: GPT-5.2 generates text description
- **Example**: "参考画像", "図解", "製品写真"

## 4. Upload Flow

### Step 1: Select Schema
```
User clicks dropdown → Sees list of schemas → Selects one
```

### Step 2: View Schema Details
```
Selected schema info is displayed below dropdown
Shows: name, description, and list of fields
```

### Step 3: Create New Schema (Optional)
```
User clicks "+ 新規作成" → Schema creator appears
User fills in schema details → Clicks "保存"
New schema is added to list and auto-selected
```

### Step 4: Upload File
```
User selects Excel file → Clicks "アップロード"
File is processed using selected schema
Progress bar shows processing status
```

## 5. Search Results with Schema

### Without Schema
```
┌──────────────────────────────────────────────────────────┐
│ 質問に対する回答テキスト...                                  │
│ [Image1] [Image2]                                        │
│ 出典: document.xlsx | スコア: 0.95                        │
└──────────────────────────────────────────────────────────┘
```

### With Schema
```
┌──────────────────────────────────────────────────────────┐
│ 質問に対する回答テキスト...                                  │
│ [Image1] [Image2]                                        │
│ 出典: document.xlsx | スキーマ: 製品検査記録 | スコア: 0.95 │
└──────────────────────────────────────────────────────────┘
```

## 6. Color Scheme

### Primary Colors
- **Purple Gradient**: `#667eea` → `#764ba2` (buttons, accents)
- **White**: `#ffffff` (backgrounds)
- **Light Gray**: `#f7fafc` (secondary backgrounds)

### Text Colors
- **Dark**: `#1a202c` (headings)
- **Medium**: `#2d3748` (body text)
- **Light**: `#718096` (secondary text)

### Status Colors
- **Success**: `#48bb78` (green)
- **Error**: `#fc8181` (red)
- **Info**: `#667eea` (purple)

## 7. Responsive Design

### Desktop (> 768px)
- Full layout with side-by-side elements
- Field rows in grid layout
- Wide buttons and inputs

### Mobile (≤ 768px)
- Stacked layout
- Field rows become vertical
- Full-width buttons
- Compressed spacing

## 8. Interactions

### Hover Effects
- **Buttons**: Slight lift (`translateY(-1px)`) + shadow
- **Inputs**: Border color change to purple
- **Delete button**: Red background on hover

### Focus States
- **Purple border**: `#667eea`
- **Shadow**: `0 0 0 3px rgba(102, 126, 234, 0.1)`
- **Smooth transition**: `0.2s`

### Click Feedback
- Button press animation
- Color intensity change
- Immediate visual response

## 9. Accessibility

### Keyboard Navigation
- Tab through all form fields
- Enter to submit forms
- Escape to cancel dialogs

### Screen Readers
- Proper label associations
- ARIA labels on buttons
- Meaningful field names

### Visual Indicators
- Required field markers (*)
- Error messages
- Success confirmations

## 10. User Workflows

### Creating First Schema
1. Click "+ 新規作成"
2. Enter schema name
3. Add fields (+ button)
4. Configure each field
5. Click "保存"
6. Schema appears in dropdown

### Uploading with Schema
1. Select schema from dropdown
2. Review schema details
3. Choose Excel file
4. Click "アップロード"
5. Monitor progress bar
6. See success message

### Switching Schemas
1. Open dropdown
2. Select different schema
3. View updated details
4. Proceed with upload

This UI design provides an intuitive, user-friendly experience for managing schemas and uploading Excel files with structured processing.
