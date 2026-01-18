import os
import logging
import base64
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import SearchRequest, SearchResponse, UploadResponse, SearchResult
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
    return {
        "status": "healthy",
        "services": {
            "blob_storage": blob_service is not None,
            "llm_service": llm_service is not None,
            "search_service": search_service is not None
        }
    }


@app.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
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
        
        # Read file content
        file_content = await file.read()
        
        # Upload original file to blob storage
        file_url = blob_service.upload_file(
            file_content,
            file.filename,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        logger.info(f"Uploaded file to: {file_url}")
        
        # Extract text and images
        logger.info("Extracting text from Excel...")
        text_content = ExcelProcessor.extract_text_from_excel(file_content)
        
        logger.info("Extracting images from Excel...")
        images = ExcelProcessor.extract_images_from_excel(file_content, file.filename)
        logger.info(f"Extracted {len(images)} images")
        
        # Upload images to blob storage
        for img in images:
            img_bytes = base64.b64decode(img['data'])
            img_filename = f"images/{img['filename']}"
            img_url = blob_service.upload_image(img_bytes, img_filename)
            img['url'] = img_url
        
        # Structure document using multimodal LLM
        logger.info("Structuring document with LLM...")
        steps = llm_service.structure_document(text_content, images, file.filename)
        logger.info(f"Extracted {len(steps)} procedure steps")
        
        # Index in Azure AI Search
        logger.info("Indexing document in Azure AI Search...")
        search_service.index_document(steps, file.filename, file_url)
        
        return UploadResponse(
            success=True,
            message="Document uploaded and processed successfully",
            filename=file.filename,
            document_id=file.filename,
            steps_extracted=len(steps)
        )
        
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
