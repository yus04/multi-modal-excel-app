import React from 'react';
import { ExcelSchema } from '../types';
import './SchemaSelector.css';

interface SchemaSelectorProps {
  schemas: ExcelSchema[];
  selectedSchemaId: string | null;
  onSelect: (schemaId: string | null) => void;
  onCreateNew: () => void;
}

const SchemaSelector: React.FC<SchemaSelectorProps> = ({
  schemas,
  selectedSchemaId,
  onSelect,
  onCreateNew,
}) => {
  const selectedSchema = selectedSchemaId ? schemas.find(s => s.id === selectedSchemaId) : null;
  
  return (
    <div className="schema-selector">
      <label>スキーマを選択</label>
      <div className="selector-container">
        <select
          value={selectedSchemaId || ''}
          onChange={(e) => onSelect(e.target.value || null)}
          className="schema-select"
        >
          <option value="">スキーマなし（デフォルト処理）</option>
          {schemas.map((schema) => (
            <option key={schema.id} value={schema.id}>
              {schema.name} ({schema.fields.length}個のフィールド)
            </option>
          ))}
        </select>
        <button onClick={onCreateNew} className="new-schema-btn">
          + 新規作成
        </button>
      </div>
      
      {selectedSchema && (
        <div className="schema-info">
          <h4>{selectedSchema.name}</h4>
          {selectedSchema.description && (
            <p className="schema-description">
              {selectedSchema.description}
            </p>
          )}
          <div className="fields-preview">
            <strong>フィールド:</strong>
            <ul>
              {selectedSchema.fields.map((field, idx) => (
                <li key={idx}>
                  {field.name} 
                  <span className="field-type">
                    ({field.data_type === 'text' ? 'テキスト' : '画像'})
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

export default SchemaSelector;
