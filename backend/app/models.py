from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


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
    step_number: str
    title: str
    summary: str
    images: List[str] = Field(default_factory=list)
    source_document: str
    source_url: str
    score: float
    page_number: Optional[int] = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    include_images: bool = True


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
