export interface SearchResult {
  answer: string;  // LLM-generated answer text
  images: string[];  // Only relevant images for the answer
  source_document: string;
  source_url: string;
  score: number;
  schema_name?: string;  // Schema name (for schema-based indexing)
}

export interface SearchRequest {
  query: string;
  top_k?: number;
  include_images?: boolean;
  schema_id?: string;  // Optional schema ID to search in schema-specific index
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

export type FieldDataType = 'text' | 'long_text' | 'image' | 'table';

export interface FieldDefinition {
  name: string;
  data_type: FieldDataType;
  description?: string;
  sub_fields?: FieldDefinition[];  // For table type
}

export interface ExcelSchema {
  id: string;
  name: string;
  description?: string;
  fields: FieldDefinition[];
  created_at: string;
  updated_at?: string;
}

export interface SchemaCreateRequest {
  name: string;
  description?: string;
  fields: FieldDefinition[];
}

export interface IndexedDocument {
  id: string;
  filename: string;
  source_url: string;
  schema_id?: string;
  schema_name?: string;
  index_name: string;
}
