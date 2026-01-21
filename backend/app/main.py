import os
import logging
import base64
import uuid
import asyncio
from datetime import datetime
from typing import Optional, Dict
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import SearchRequest, SearchResponse, UploadResponse, SearchResult, ProcessingStatus
from app.blob_service import BlobStorageService
from app.excel_processor import ExcelProcessor
from app.llm_service import MultiModalLLMService
from app.search_service import SearchService

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
search_service: Optional[SearchService] = None

# In-memory job status storage (for production, use Redis or database)
job_status_store: Dict[str, ProcessingStatus] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global blob_service, llm_service, search_service
    
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
            "search_service": search_service is not None
        },
        "job_store_size": len(job_status_store)
    }


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


def process_document_background(job_id: str, file_content: bytes, filename: str):
    """Background task to process document with progress tracking"""
    logger.info(f"[{job_id}] Background processing started for {filename}")
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
        search_service.index_document(document, filename, file_url)
        
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
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """
    Upload and process an Excel document
    
    - Extracts text and images from Excel
    - Structures content using multimodal LLM
    - Uploads to blob storage
    - Indexes in Azure AI Search
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) are supported")
    
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
            file.filename
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


@app.post("/search", response_model=SearchResponse)
async def search(request: SearchRequest):
    """
    Search for procedures using hybrid search
    
    - Performs vector + keyword + semantic search
    - Returns results with images and references
    - No results message if nothing found
    """
    try:
        logger.info(f"Searching for: {request.query}")
        
        # Perform hybrid search
        results = search_service.hybrid_search(
            query=request.query,
            top_k=request.top_k,
            include_images=request.include_images
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
