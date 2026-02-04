import React from 'react';
import { IndexedDocument } from '../types';
import './DocumentSelector.css';

interface DocumentSelectorProps {
  documents: IndexedDocument[];
  selectedDocumentId: string | null;
  onSelect: (documentId: string | null, schemaId: string | null, indexName: string | null) => void;
  loading?: boolean;
}

const DocumentSelector: React.FC<DocumentSelectorProps> = ({
  documents,
  selectedDocumentId,
  onSelect,
  loading = false
}) => {
  const handleSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const documentId = e.target.value;
    
    if (!documentId) {
      onSelect(null, null, null);
      return;
    }
    
    // Find the selected document to get its schema_id and index_name
    const selectedDoc = documents.find(doc => doc.id === documentId);
    const schemaId = selectedDoc?.schema_id || null;
    const indexName = selectedDoc?.index_name || null;
    
    onSelect(documentId, schemaId, indexName);
  };

  const formatDocumentDisplay = (doc: IndexedDocument): string => {
    if (doc.schema_name) {
      return `${doc.filename} [${doc.schema_name}]`;
    }
    return `${doc.filename} [デフォルト]`;
  };

  if (loading) {
    return (
      <div className="document-selector">
        <label>検索対象ドキュメント</label>
        <div className="document-selector-loading">読み込み中...</div>
      </div>
    );
  }

  return (
    <div className="document-selector">
      <label htmlFor="document-select">
        🔍 検索対象ドキュメント
      </label>
      <select
        id="document-select"
        value={selectedDocumentId || ''}
        onChange={handleSelectChange}
        className="document-select"
      >
        <option value="">すべてのドキュメント</option>
        {documents.map((doc) => (
          <option key={doc.id} value={doc.id}>
            {formatDocumentDisplay(doc)}
          </option>
        ))}
      </select>
      {selectedDocumentId && (
        <div className="document-info">
          {(() => {
            const doc = documents.find(d => d.id === selectedDocumentId);
            return doc ? (
              <div className="document-details">
                <span className="document-filename">📄 {doc.filename}</span>
                {doc.schema_name && (
                  <span className="document-schema">📋 スキーマ: {doc.schema_name}</span>
                )}
              </div>
            ) : null;
          })()}
        </div>
      )}
    </div>
  );
};

export default DocumentSelector;
