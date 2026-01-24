import React, { useState } from 'react';
import { FieldDefinition, FieldDataType } from '../types';
import './SchemaCreator.css';

interface SchemaCreatorProps {
  onSave: (name: string, description: string, fields: FieldDefinition[]) => void;
  onCancel: () => void;
}

const SchemaCreator: React.FC<SchemaCreatorProps> = ({ onSave, onCancel }) => {
  const [schemaName, setSchemaName] = useState('');
  const [schemaDescription, setSchemaDescription] = useState('');
  const [fields, setFields] = useState<FieldDefinition[]>([
    { name: '', data_type: 'text', description: '' }
  ]);
  const [error, setError] = useState<string | null>(null);

  const addField = () => {
    setFields([...fields, { name: '', data_type: 'text', description: '' }]);
  };

  const removeField = (index: number) => {
    if (fields.length > 1) {
      setFields(fields.filter((_, i) => i !== index));
    }
  };

  const updateField = (index: number, key: keyof FieldDefinition, value: string) => {
    const newFields = [...fields];
    if (key === 'data_type') {
      newFields[index][key] = value as FieldDataType;
    } else {
      newFields[index][key] = value;
    }
    setFields(newFields);
  };

  const handleSave = () => {
    // Validate
    if (!schemaName.trim()) {
      setError('スキーマ名を入力してください');
      return;
    }

    const validFields = fields.filter(f => f.name.trim());
    if (validFields.length === 0) {
      setError('少なくとも1つのフィールドを定義してください');
      return;
    }

    setError(null);
    onSave(schemaName, schemaDescription, validFields);
  };

  return (
    <div className="schema-creator">
      <h3>新しいスキーマを作成</h3>
      
      {error && (
        <div className="error-message">
          {error}
        </div>
      )}
      
      <div className="form-group">
        <label>スキーマ名 *</label>
        <input
          type="text"
          value={schemaName}
          onChange={(e) => setSchemaName(e.target.value)}
          placeholder="例: 製品検査記録"
          className="form-input"
        />
      </div>

      <div className="form-group">
        <label>説明</label>
        <textarea
          value={schemaDescription}
          onChange={(e) => setSchemaDescription(e.target.value)}
          placeholder="スキーマの説明を入力"
          className="form-textarea"
          rows={2}
        />
      </div>

      <div className="form-group">
        <label>フィールド定義</label>
        <div className="fields-container">
          {fields.map((field, index) => (
            <div key={index} className="field-row">
              <input
                type="text"
                value={field.name}
                onChange={(e) => updateField(index, 'name', e.target.value)}
                placeholder="フィールド名"
                className="field-name-input"
              />
              <select
                value={field.data_type}
                onChange={(e) => updateField(index, 'data_type', e.target.value)}
                className="field-type-select"
              >
                <option value="text">テキスト</option>
                <option value="image">画像</option>
              </select>
              <input
                type="text"
                value={field.description || ''}
                onChange={(e) => updateField(index, 'description', e.target.value)}
                placeholder="説明（任意）"
                className="field-desc-input"
              />
              <button
                type="button"
                onClick={() => removeField(index)}
                className="remove-field-btn"
                disabled={fields.length === 1}
                title="フィールドを削除"
              >
                🗑️
              </button>
            </div>
          ))}
        </div>
        <button
          type="button"
          onClick={addField}
          className="add-field-btn"
        >
          + フィールドを追加
        </button>
      </div>

      <div className="button-group">
        <button onClick={handleSave} className="save-btn">
          保存
        </button>
        <button onClick={onCancel} className="cancel-btn">
          キャンセル
        </button>
      </div>
    </div>
  );
};

export default SchemaCreator;
