import axios from 'axios';
import { 
  SearchRequest, 
  SearchResponse, 
  UploadResponse, 
  ProcessingStatus,
  ExcelSchema,
  SchemaCreateRequest
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const searchProcedures = async (request: SearchRequest): Promise<SearchResponse> => {
  const response = await api.post<SearchResponse>('/search', request);
  return response.data;
};

export const uploadDocument = async (file: File, schemaId?: string): Promise<UploadResponse> => {
  console.log('[API] Uploading document:', file.name, 'with schema:', schemaId);
  const formData = new FormData();
  formData.append('file', file);
  if (schemaId) {
    formData.append('schema_id', schemaId);
  }

  try {
    const response = await api.post<UploadResponse>('/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });

    console.log('[API] Upload response status:', response.status);
    console.log('[API] Upload response data:', response.data);
    return response.data;
  } catch (error: any) {
    console.error('[API] Upload request failed:', error);
    console.error('[API] Error response:', error.response);
    console.error('[API] Error message:', error.message);
    throw error;
  }
};

export const getProcessingStatus = async (jobId: string): Promise<ProcessingStatus> => {
  console.log('[API] Fetching status for job:', jobId);
  const response = await api.get<ProcessingStatus>(`/status/${jobId}`);
  console.log('[API] Status response:', response.data);
  return response.data;
};

export const healthCheck = async (): Promise<{ status: string }> => {
  const response = await api.get('/health');
  return response.data;
};

// Schema management APIs
export const listSchemas = async (): Promise<ExcelSchema[]> => {
  const response = await api.get<ExcelSchema[]>('/schemas');
  return response.data;
};

export const createSchema = async (request: SchemaCreateRequest): Promise<ExcelSchema> => {
  const response = await api.post<ExcelSchema>('/schemas', request);
  return response.data;
};

export const getSchema = async (schemaId: string): Promise<ExcelSchema> => {
  const response = await api.get<ExcelSchema>(`/schemas/${schemaId}`);
  return response.data;
};

export const updateSchema = async (schemaId: string, request: SchemaCreateRequest): Promise<ExcelSchema> => {
  const response = await api.put<ExcelSchema>(`/schemas/${schemaId}`, request);
  return response.data;
};

export const deleteSchema = async (schemaId: string): Promise<{ success: boolean; message: string }> => {
  const response = await api.delete(`/schemas/${schemaId}`);
  return response.data;
};
