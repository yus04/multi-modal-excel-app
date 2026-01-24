from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class FieldDataType(str, Enum):
    """Field data types"""
    TEXT = "text"
    IMAGE = "image"
    TABLE = "table"


class FieldDefinition(BaseModel):
    """Definition of a field in Excel schema"""
    name: str
    data_type: FieldDataType
    description: Optional[str] = None
    sub_fields: Optional[List['FieldDefinition']] = None  # For table type

# Enable forward reference for recursive model
FieldDefinition.model_rebuild()


class ExcelSchema(BaseModel):
    """Schema definition for Excel file structure"""
    id: str
    name: str
    description: Optional[str] = None
    fields: List[FieldDefinition]
    created_at: str
    updated_at: Optional[str] = None


class SchemaCreateRequest(BaseModel):
    """Request to create a new schema"""
    name: str
    description: Optional[str] = None
    fields: List[FieldDefinition]


class ProcedureStep(BaseModel):
    step_number: str
    title: str
    description: str
    images: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentMetadata(BaseModel):
    filename: str
    upload_date: str
    file_url: str
    total_steps: int


class SearchResult(BaseModel):
    answer: str  # LLMが生成した回答テキスト
    images: List[str] = Field(default_factory=list)  # 回答に関連する画像のみ
    source_document: str
    source_url: str
    score: float


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    include_images: bool = True
    schema_id: Optional[str] = None  # If provided, searches in schema-specific index


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total_results: int
    message: Optional[str] = None


class UploadResponse(BaseModel):
    success: bool
    message: str
    filename: str
    document_id: Optional[str] = None
    steps_extracted: int = 0
    job_id: Optional[str] = None


class ProcessingStatus(BaseModel):
    job_id: str
    status: str  # "pending", "processing", "completed", "failed"
    filename: str
    progress: int = 0  # 0-100
    total_images: int = 0
    processed_images: int = 0
    current_step: str = ""
    message: str = ""
    error: str = ""
