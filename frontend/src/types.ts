export interface SearchResult {
  answer: string;  // LLMが生成した回答テキスト
  images: string[];  // 回答に関連する画像のみ
  source_document: string;
  source_url: string;
  score: number;
}

export interface SearchRequest {
  query: string;
  top_k?: number;
  include_images?: boolean;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total_results: number;
  message?: string;
}

export interface UploadResponse {
  success: boolean;
  message: string;
  filename: string;
  document_id?: string;
  steps_extracted: number;
  job_id?: string;
}

export interface ProcessingStatus {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  filename: string;
  progress: number;
  total_images: number;
  processed_images: number;
  current_step: string;
  message?: string;
  error?: string;
}
