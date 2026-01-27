import React, { useState, useRef, useEffect } from 'react';
import './App.css';
import { 
  searchProcedures, 
  uploadDocument, 
  getProcessingStatus, 
  listSchemas, 
  createSchema,
  listDocuments
} from './api';
import { 
  SearchResult, 
  UploadResponse, 
  ProcessingStatus, 
  ExcelSchema, 
  FieldDefinition,
  IndexedDocument
} from './types';
import SchemaSelector from './components/SchemaSelector';
import SchemaCreator from './components/SchemaCreator';
import DocumentSelector from './components/DocumentSelector';

function App() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [totalResults, setTotalResults] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [processingStatus, setProcessingStatus] = useState<ProcessingStatus | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const statusIntervalRef = useRef<number | null>(null);
  
  // Schema management states
  const [schemas, setSchemas] = useState<ExcelSchema[]>([]);
  const [selectedSchemaId, setSelectedSchemaId] = useState<string | null>(null);
  const [showSchemaCreator, setShowSchemaCreator] = useState(false);

  // Document management states
  const [documents, setDocuments] = useState<IndexedDocument[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [selectedDocumentSchemaId, setSelectedDocumentSchemaId] = useState<string | null>(null);
  const [loadingDocuments, setLoadingDocuments] = useState(false);

  // Load schemas and documents on mount
  useEffect(() => {
    loadSchemas();
    loadDocuments();
  }, []);

  const loadSchemas = async () => {
    try {
      const schemasList = await listSchemas();
      setSchemas(schemasList);
    } catch (err) {
      console.error('Error loading schemas:', err);
    }
  };

  const loadDocuments = async () => {
    try {
      setLoadingDocuments(true);
      const documentsList = await listDocuments();
      setDocuments(documentsList);
      console.log('[App] Loaded documents:', documentsList);
    } catch (err) {
      console.error('Error loading documents:', err);
    } finally {
      setLoadingDocuments(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!query.trim()) {
      setError('検索クエリを入力してください');
      return;
    }

    setLoading(true);
    setError(null);
    setMessage(null);
    setSuccess(null);

    try {
      console.log('[Search] Starting search...');
      console.log('[Search] Query:', query.trim());
      console.log('[Search] Selected Document ID:', selectedDocumentId);
      console.log('[Search] Selected Document Schema ID:', selectedDocumentSchemaId);
      console.log('[Search] Top K: 5');
      console.log('[Search] Include Images: true');
      
      const response = await searchProcedures({
        query: query.trim(),
        top_k: 5,
        include_images: true,
        schema_id: selectedDocumentSchemaId || undefined,
      });

      console.log('[Search] Response received:', response);
      console.log('[Search] Total results:', response.total_results);
      console.log('[Search] Results count:', response.results.length);
      console.log('[Search] Message:', response.message);

      setResults(response.results);
      setTotalResults(response.total_results);
      setMessage(response.message || null);
    } catch (err) {
      setError('検索中にエラーが発生しました。もう一度お試しください。');
      console.error('[Search] Search error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.xls')) {
        setError('Excelファイル (.xlsx, .xls) のみアップロード可能です');
        setSelectedFile(null);
        return;
      }
      setSelectedFile(file);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('ファイルを選択してください');
      return;
    }

    console.log('[Upload] Starting upload for file:', selectedFile.name, 'with schema:', selectedSchemaId);
    setUploading(true);
    setError(null);
    setSuccess(null);
    setProcessingStatus(null);

    try {
      const response: UploadResponse = await uploadDocument(selectedFile, selectedSchemaId || undefined);
      console.log('[Upload] Upload response:', response);
      console.log('[Upload] Response job_id:', response.job_id);
      console.log('[Upload] Response type:', typeof response.job_id);
      
      if (response.job_id) {
        console.log('[Upload] Job ID found, starting status polling for job:', response.job_id);
        
        // Initialize processing status immediately to show progress bar
        const initialStatus: ProcessingStatus = {
          job_id: response.job_id,
          status: 'pending',
          filename: selectedFile.name,
          progress: 0,
          total_images: 0,
          processed_images: 0,
          current_step: '処理を開始しています...',
          message: '',
          error: ''
        };
        console.log('[Upload] Setting initial processing status:', initialStatus);
        setProcessingStatus(initialStatus);
        
        // Start polling for status
        startStatusPolling(response.job_id);
      } else {
        console.log('[Upload] No job_id in response, using old synchronous behavior');
        console.log('[Upload] Full response object:', JSON.stringify(response));
        // Old behavior (synchronous processing)
        setSuccess(`${response.filename} をアップロードしました。${response.steps_extracted}件の手順を抽出しました。`);
        setSelectedFile(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        setUploading(false);
      }
    } catch (err) {
      setError('アップロード中にエラーが発生しました。もう一度お試しください。');
      console.error('[Upload] Upload error:', err);
      setUploading(false);
    }
  };

  const startStatusPolling = (jobId: string) => {
    console.log('[Polling] Starting status polling for job:', jobId);
    const pollStatus = async () => {
      try {
        console.log('[Polling] Fetching status...');
        const status = await getProcessingStatus(jobId);
        console.log('[Polling] Processing status update:', status);
        console.log('[Polling] Status:', status.status, 'Progress:', status.progress + '%', 'Step:', status.current_step);
        setProcessingStatus(status);

        if (status.status === 'completed') {
          console.log('[Polling] Processing completed');
          setSuccess(`${status.filename} の処理が完了しました！`);
          setUploading(false);
          setSelectedFile(null);
          if (fileInputRef.current) {
            fileInputRef.current.value = '';
          }
          if (statusIntervalRef.current) {
            console.log('[Polling] Clearing polling interval');
            clearInterval(statusIntervalRef.current);
            statusIntervalRef.current = null;
          }
          // Reload documents list after successful upload
          loadDocuments();
        } else if (status.status === 'failed') {
          console.log('[Polling] Processing failed:', status.error);
          setError(`処理中にエラーが発生しました: ${status.error || '不明なエラー'}`);
          setUploading(false);
          if (statusIntervalRef.current) {
            console.log('[Polling] Clearing polling interval');
            clearInterval(statusIntervalRef.current);
            statusIntervalRef.current = null;
          }
        }
      } catch (err) {
        console.error('[Polling] Status polling error:', err);
      }
    };

    // Poll every 1 second
    console.log('[Polling] Starting polling interval (every 1000ms)');
    pollStatus();
    statusIntervalRef.current = window.setInterval(pollStatus, 1000);
  };

  const handleCreateSchema = async (name: string, description: string, fields: FieldDefinition[]) => {
    try {
      const newSchema = await createSchema({ name, description, fields });
      setSchemas([...schemas, newSchema]);
      setSelectedSchemaId(newSchema.id);
      setShowSchemaCreator(false);
      setSuccess(`スキーマ「${name}」を作成しました`);
    } catch (err) {
      setError('スキーマの作成中にエラーが発生しました');
      console.error('Error creating schema:', err);
    }
  };

  const handleCancelSchemaCreator = () => {
    setShowSchemaCreator(false);
  };

  useEffect(() => {
    return () => {
      if (statusIntervalRef.current) {
        clearInterval(statusIntervalRef.current);
      }
    };
  }, []);

  return (
    <div className="app">
      <header className="header">
        <h1>Excel 作業標準書検索システム</h1>
        <p>画像付きマルチモーダル検索で作業手順を簡単に見つけます</p>
      </header>

      <main className="main-content">
        {/* Upload Section */}
        <section className="upload-section">
          <h2>📤 Excel ファイルのアップロード</h2>
          
          {/* Schema Selector */}
          {!showSchemaCreator && (
            <SchemaSelector
              schemas={schemas}
              selectedSchemaId={selectedSchemaId}
              onSelect={setSelectedSchemaId}
              onCreateNew={() => setShowSchemaCreator(true)}
            />
          )}
          
          {/* Schema Creator */}
          {showSchemaCreator && (
            <SchemaCreator
              onSave={handleCreateSchema}
              onCancel={handleCancelSchemaCreator}
            />
          )}
          
          <div className="file-input-wrapper">
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls"
              onChange={handleFileSelect}
              className="file-input"
            />
            <button
              onClick={handleUpload}
              disabled={!selectedFile || uploading || showSchemaCreator}
              className="upload-button"
            >
              {uploading ? 'アップロード中...' : 'アップロード'}
            </button>
          </div>
          {selectedFile && (
            <p style={{ color: '#667eea', marginTop: '0.5rem' }}>
              選択されたファイル: {selectedFile.name}
            </p>
          )}
        </section>

        {/* Processing Status Bar */}
        {processingStatus && (processingStatus.status === 'pending' || processingStatus.status === 'processing') && (
          <section className="status-section">
            <h3>処理状況</h3>
            <div className="status-bar-container">
              <div className="status-info">
                <span className="status-filename">{processingStatus.filename}</span>
                <span className="status-step">{processingStatus.current_step}</span>
                {processingStatus.total_images > 0 && (
                  <span className="status-images">
                    画像: {processingStatus.processed_images} / {processingStatus.total_images}
                  </span>
                )}
              </div>
              <div className="progress-bar">
                <div 
                  className="progress-bar-fill" 
                  style={{ width: `${processingStatus.progress}%` }}
                >
                  <span className="progress-text">{processingStatus.progress}%</span>
                </div>
              </div>
            </div>
          </section>
        )}

        {/* Error and Success Messages */}
        {error && <div className="error">{error}</div>}
        {success && <div className="success">{success}</div>}

        {/* Search Section */}
        <section className="search-section">
          <h2>🔍 作業手順の検索</h2>
          
          {/* Document Selector */}
          <DocumentSelector
            documents={documents}
            selectedDocumentId={selectedDocumentId}
            onSelect={(docId, schemaId) => {
              setSelectedDocumentId(docId);
              setSelectedDocumentSchemaId(schemaId);
              console.log('[App] Document selected:', docId, 'Schema ID:', schemaId);
            }}
            loading={loadingDocuments}
          />
          
          <form onSubmit={handleSearch} className="search-form">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="検索キーワードを入力してください（例：組み立て手順、品質チェック）"
              className="search-input"
            />
            <button
              type="submit"
              disabled={loading}
              className="search-button"
            >
              {loading ? '検索中...' : '検索'}
            </button>
          </form>
        </section>

        {/* Results Section */}
        {(results.length > 0 || message) && (
          <section className="results-section">
            <div className="results-header">
              <h2>検索結果</h2>
              {totalResults > 0 && (
                <span className="results-count">
                  {totalResults}件の結果が見つかりました
                </span>
              )}
            </div>

            {message && (
              <div className="no-results">
                <p>{message}</p>
              </div>
            )}

            {results.map((result, index) => (
              <div key={index} className="result-card">
                <div className="result-content">
                  <p className="result-answer">{result.answer}</p>
                </div>

                {result.images && result.images.length > 0 && (
                  <div className="result-images">
                    {result.images.map((imageUrl, imgIndex) => (
                      <img
                        key={imgIndex}
                        src={imageUrl}
                        alt={`関連画像 ${imgIndex + 1}`}
                        className="result-image"
                      />
                    ))}
                  </div>
                )}

                <div className="result-footer">
                  <div>
                    <strong>出典：</strong>
                    <a
                      href={result.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="source-link"
                    >
                      {result.source_document}
                    </a>
                  </div>
                  <span className="score">
                    スコア: {result.score.toFixed(2)}
                  </span>
                </div>
              </div>
            ))}
          </section>
        )}

        {loading && (
          <div className="loading">
            <p>検索中...</p>
          </div>
        )}
      </main>

      <footer className="footer">
        <p>© 2026 Multi-Modal Excel Search System | Powered by Azure AI</p>
      </footer>
    </div>
  );
}

export default App;
