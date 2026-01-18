import React, { useState, useRef } from 'react';
import './App.css';
import { searchProcedures, uploadDocument } from './api';
import { SearchResult, UploadResponse } from './types';

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
  const fileInputRef = useRef<HTMLInputElement>(null);

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
      const response = await searchProcedures({
        query: query.trim(),
        top_k: 5,
        include_images: true,
      });

      setResults(response.results);
      setTotalResults(response.total_results);
      setMessage(response.message || null);
    } catch (err) {
      setError('検索中にエラーが発生しました。もう一度お試しください。');
      console.error('Search error:', err);
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

    setUploading(true);
    setError(null);
    setSuccess(null);

    try {
      const response: UploadResponse = await uploadDocument(selectedFile);
      setSuccess(`${response.filename} をアップロードしました。${response.steps_extracted}件の手順を抽出しました。`);
      setSelectedFile(null);
      // Reset file input using ref
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    } catch (err) {
      setError('アップロード中にエラーが発生しました。もう一度お試しください。');
      console.error('Upload error:', err);
    } finally {
      setUploading(false);
    }
  };

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
              disabled={!selectedFile || uploading}
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

        {/* Error and Success Messages */}
        {error && <div className="error">{error}</div>}
        {success && <div className="success">{success}</div>}

        {/* Search Section */}
        <section className="search-section">
          <h2>🔍 作業手順の検索</h2>
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
                <div className="result-header">
                  <div className="result-title">
                    <span className="step-number">手順 {result.step_number}</span>
                    <h3>{result.title}</h3>
                  </div>
                </div>

                <p className="result-summary">{result.summary}</p>

                {result.images && result.images.length > 0 && (
                  <div className="result-images">
                    {result.images.map((imageUrl, imgIndex) => (
                      <img
                        key={imgIndex}
                        src={imageUrl}
                        alt={`手順 ${result.step_number} - 画像 ${imgIndex + 1}`}
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
                    {result.page_number && ` (ページ ${result.page_number})`}
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
        <p>© 2024 Multi-Modal Excel Search System | Powered by Azure AI</p>
      </footer>
    </div>
  );
}

export default App;
