import os
import logging
import base64
import uuid
import asyncio
from datetime import datetime
from typing import Optional, Dict, List
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import (
    SearchRequest, SearchResponse, UploadResponse, SearchResult, ProcessingStatus,
    ExcelSchema, SchemaCreateRequest, FieldDefinition, IndexedDocument
)
from app.blob_service import BlobStorageService
from app.excel_processor import ExcelProcessor
from app.llm_service import MultiModalLLMService
from app.content_understanding_service import ContentUnderstandingService
from app.search_service import SearchService
from app.schema_service import SchemaService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Multi-Modal Excel Search API",
    description="画像付き作業標準書検索システム",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
blob_service: Optional[BlobStorageService] = None
llm_service: Optional[MultiModalLLMService] = None
content_understanding_service: Optional[ContentUnderstandingService] = None
search_service: Optional[SearchService] = None
schema_service: Optional[SchemaService] = None

# In-memory job status storage (for production, use Redis or database)
job_status_store: Dict[str, ProcessingStatus] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global blob_service, llm_service, content_understanding_service, search_service, schema_service
    
    try:
        logger.info("Initializing services...")
        
        blob_service = BlobStorageService(
            connection_string=settings.azure_storage_connection_string,
            container_name=settings.azure_storage_container_name
        )
        
        llm_service = MultiModalLLMService(
            endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            deployment_name=settings.azure_openai_deployment_name,
            api_version=settings.azure_openai_api_version
        )
        
        # Initialize Content Understanding Service (uses same Azure OpenAI endpoint)
        content_understanding_service = ContentUnderstandingService(
            endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            deployment_name=settings.azure_openai_deployment_name,
            api_version=settings.azure_openai_api_version
        )
        
        search_service = SearchService(
            search_endpoint=settings.azure_search_endpoint,
            search_api_key=settings.azure_search_api_key,
            index_name=settings.azure_search_index_name,
            openai_endpoint=settings.azure_openai_endpoint,
            openai_api_key=settings.azure_openai_api_key,
            openai_deployment=settings.azure_openai_deployment_name,
            openai_embedding_deployment=settings.azure_openai_embedding_deployment,
            openai_api_version=settings.azure_openai_api_version
        )
        
        schema_service = SchemaService()
        
        logger.info("All services initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing services: {str(e)}")
        raise


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Multi-Modal Excel Search API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    logger.info("Health check requested")
    return {
        "status": "healthy",
        "services": {
            "blob_storage": blob_service is not None,
            "llm_service": llm_service is not None,
            "content_understanding_service": content_understanding_service is not None,
            "search_service": search_service is not None,
            "schema_service": schema_service is not None
        },
        "job_store_size": len(job_status_store)
    }


@app.get("/schemas", response_model=List[ExcelSchema])
async def list_schemas():
    """List all available schemas"""
    logger.info("Listing schemas")
    return schema_service.list_schemas()


@app.post("/schemas", response_model=ExcelSchema)
async def create_schema(request: SchemaCreateRequest):
    """Create a new schema"""
    logger.info(f"Creating schema: {request.name}")
    return schema_service.create_schema(request)


@app.get("/schemas/{schema_id}", response_model=ExcelSchema)
async def get_schema(schema_id: str):
    """Get a specific schema by ID"""
    logger.info(f"Getting schema: {schema_id}")
    schema = schema_service.get_schema(schema_id)
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    return schema


@app.put("/schemas/{schema_id}", response_model=ExcelSchema)
async def update_schema(schema_id: str, request: SchemaCreateRequest):
    """Update an existing schema"""
    logger.info(f"Updating schema: {schema_id}")
    schema = schema_service.update_schema(schema_id, request)
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    return schema


@app.delete("/schemas/{schema_id}")
async def delete_schema(schema_id: str):
    """Delete a schema"""
    logger.info(f"Deleting schema: {schema_id}")
    success = schema_service.delete_schema(schema_id)
    if not success:
        raise HTTPException(status_code=404, detail="Schema not found")
    return {"success": True, "message": "Schema deleted successfully"}


@app.get("/status/{job_id}", response_model=ProcessingStatus)
async def get_processing_status(job_id: str):
    """Get the status of a document processing job"""
    logger.debug(f"Status request for job_id: {job_id}")
    if job_id not in job_status_store:
        logger.warning(f"Job not found: {job_id}. Available jobs: {list(job_status_store.keys())}")
        raise HTTPException(status_code=404, detail="Job not found")
    status = job_status_store[job_id]
    logger.debug(f"Returning status: {status.status}, progress: {status.progress}%")
    return status


def process_document_background(job_id: str, file_content: bytes, filename: str, schema: Optional[ExcelSchema] = None):
    """Background task to process document with progress tracking"""
    logger.info(f"[{job_id}] Background processing started for {filename}")
    if schema:
        logger.info(f"[{job_id}] Using schema: {schema.name}")
    
    try:
        # Update status: Upload to blob storage
        job_status_store[job_id].status = "processing"
        job_status_store[job_id].current_step = "Blob Storageにアップロード中..."
        job_status_store[job_id].progress = 0
        logger.info(f"[{job_id}] Status updated to 'processing', progress: 0%")
        
        file_url = blob_service.upload_file(
            file_content,
            filename,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        logger.info(f"Uploaded file to: {file_url}")
        
        # Extract text and images
        job_status_store[job_id].current_step = "テキストと画像を抽出中..."
        job_status_store[job_id].progress = 0
        text_content = ExcelProcessor.extract_text_from_excel(file_content)
        
        images = ExcelProcessor.extract_images_from_excel(file_content, filename)
        job_status_store[job_id].total_images = len(images)
        logger.info(f"Extracted {len(images)} images")
        
        # Upload images to blob storage (keep progress at 0)
        job_status_store[job_id].current_step = "画像をアップロード中..."
        for idx, img in enumerate(images):
            img_bytes = base64.b64decode(img['data'])
            img_filename = f"images/{img['filename']}"
            img_url = blob_service.upload_image(img_bytes, img_filename)
            img['url'] = img_url
        
        # Structure document using multimodal LLM with progress callback
        def progress_callback(current: int, total: int, message: str):
            job_status_store[job_id].processed_images = current
            job_status_store[job_id].current_step = message
            # Image processing takes 0-90% of progress
            # Progress starts from 0 and updates after each image is processed
            if total > 0:
                progress_percent = int((current / total) * 90)
                job_status_store[job_id].progress = progress_percent
            logger.info(f"Progress update: {current}/{total} - {message} ({job_status_store[job_id].progress}%)")
        
        job_status_store[job_id].current_step = "画像の説明を生成中..."
        job_status_store[job_id].progress = 0
        logger.info(f"Starting document structuring with {len(images)} images")
        
        # Structure document differently based on whether schema is provided
        if schema:
            # Use Content Understanding Service for schema-based extraction
            logger.info(f"Using Content Understanding with schema: {schema.name}")
            
            # First, extract fields using Content Understanding
            extracted_fields = content_understanding_service.extract_fields_from_excel(
                text_content=text_content,
                images=images,
                schema=schema.dict(),
                filename=filename
            )
            
            # Create a document structure with extracted fields
            document = {
                'filename': filename,
                'content': '',  # Will be generated from extracted fields
                'images': images,
                'extracted_fields': extracted_fields,
                'metadata': {
                    'sheet_count': len(text_content),
                    'image_count': len(images),
                    'total_rows': sum(len(sheet.get('rows', [])) for sheet in text_content),
                    'schema_id': schema.id,
                    'schema_name': schema.name
                }
            }
            
            # Generate a combined content from extracted fields for display
            content_parts = [f"ファイル名: {filename}\n"]
            for field_name, field_value in extracted_fields.items():
                if field_value is not None:
                    content_parts.append(f"{field_name}: {field_value}\n")
            document['content'] = "\n".join(content_parts)
            
            logger.info(f"Extracted {len(extracted_fields)} fields using Content Understanding")
        else:
            # Use traditional multimodal LLM structuring
            document = llm_service.structure_document(
                text_content, 
                images, 
                filename,
                progress_callback=progress_callback
            )
        
        logger.info(f"Document structured with {document['metadata']['image_count']} images")
        
        # Index in Azure AI Search
        job_status_store[job_id].current_step = "インデックスに登録中..."
        job_status_store[job_id].progress = 95
        
        if schema:
            # Use schema-based indexing
            logger.info(f"[{job_id}] Indexing document with schema: {schema.name} (ID: {schema.id})")
            search_service.index_document_with_schema(document, filename, file_url, schema)
            logger.info(f"[{job_id}] Successfully indexed document in schema-specific index")
        else:
            # Use default indexing
            logger.info(f"[{job_id}] Indexing document in default index")
            search_service.index_document(document, filename, file_url)
            logger.info(f"[{job_id}] Successfully indexed document in default index")
        
        # Complete
        job_status_store[job_id].status = "completed"
        job_status_store[job_id].current_step = "完了"
        job_status_store[job_id].progress = 100
        job_status_store[job_id].message = "ドキュメントの処理が完了しました"
        
    except Exception as e:
        logger.error(f"Error processing document in background: {str(e)}")
        job_status_store[job_id].status = "failed"
        job_status_store[job_id].error = str(e)
        job_status_store[job_id].message = "処理中にエラーが発生しました"


@app.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...),
    schema_id: Optional[str] = Form(None)
):
    """
    Upload and process an Excel document
    
    - Extracts text and images from Excel
    - Structures content using multimodal LLM
    - Uploads to blob storage
    - Indexes in Azure AI Search
    - If schema_id provided, uses schema-based field extraction
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are supported")
    
    # Validate schema if provided
    schema = None
    if schema_id:
        schema = schema_service.get_schema(schema_id)
        if not schema:
            raise HTTPException(status_code=404, detail=f"Schema not found: {schema_id}")
        logger.info(f"Using schema: {schema.name} ({schema_id})")
    
    try:
        logger.info(f"Processing upload: {file.filename}")
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        logger.info(f"Generated job_id: {job_id}")
        
        # Read file content
        file_content = await file.read()
        logger.info(f"Read {len(file_content)} bytes from file")
        
        # Initialize job status
        job_status_store[job_id] = ProcessingStatus(
            job_id=job_id,
            status="pending",
            filename=file.filename,
            progress=0,
            total_images=0,
            processed_images=0,
            current_step="処理を開始しています...",
            message="",
            error=""
        )
        logger.info(f"Initialized job status for {job_id}")
        
        # Start background processing
        background_tasks.add_task(
            process_document_background,
            job_id,
            file_content,
            file.filename,
            schema
        )
        logger.info(f"Started background task for {job_id}")
        
        response = UploadResponse(
            success=True,
            message="Document upload started. Use job_id to check progress.",
            filename=file.filename,
            job_id=job_id,
            steps_extracted=0
        )
        logger.info(f"Returning response with job_id: {response.job_id}")
        return response
        
    except Exception as e:
        logger.error(f"Error processing upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@app.get("/documents", response_model=List[IndexedDocument])
async def list_documents():
    """List all indexed documents across all indexes"""
    logger.info("Listing all indexed documents")
    try:
        documents = search_service.get_all_documents()
        return documents
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/debug/index-status")
async def get_index_status():
    """
    Debug endpoint to check index status and document count
    """
    try:
        default_count = search_service.get_document_count()
        
        # Get counts for all schema indexes
        schema_counts = {}
        for schema_id in search_service.schema_indexes.keys():
            schema_counts[schema_id] = search_service.get_document_count(schema_id)
        
        return {
            "default_index": {
                "name": search_service.index_name,
                "document_count": default_count
            },
            "schema_indexes": schema_counts,
            "registered_schemas": list(search_service.schema_indexes.keys())
        }
    except Exception as e:
        logger.error(f"Error getting index status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Search for procedures using hybrid search
    
    - Performs vector + keyword + semantic search
    - Returns results with images and references
    - No results message if nothing found
    - If schema_id provided, searches in schema-specific index
    """
    try:
        logger.info(f"Searching for: {request.query}")
        if request.schema_id:
            logger.info(f"Using schema: {request.schema_id}")
        
        # Perform hybrid search
        results = search_service.hybrid_search(
            query=request.query,
            top_k=request.top_k,
            include_images=request.include_images,
            schema_id=request.schema_id
        )
        
        # Prepare response
        if not results:
            return SearchResponse(
                query=request.query,
                results=[],
                total_results=0,
                message="検索結果が見つかりませんでした。標準書に記載されていない内容の可能性があります。"
            )
        
        search_results = []
        for result in results:
            search_results.append(SearchResult(**result))
        
        return SearchResponse(
            query=request.query,
            results=search_results,
            total_results=len(search_results)
        )
        
    except Exception as e:
        logger.error(f"Error performing search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
