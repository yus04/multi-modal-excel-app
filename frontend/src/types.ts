export interface SearchResult {
  step_number: string;
  title: string;
  summary: string;
  images: string[];
  source_document: string;
  source_url: string;
  score: number;
  page_number?: number;
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
}
