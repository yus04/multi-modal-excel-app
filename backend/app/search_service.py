import json
import base64
from typing import List, Dict, Any, Optional
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch
)
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
import logging

logger = logging.getLogger(__name__)


class SearchService:
    """Azure AI Search service for hybrid search"""
    
    def __init__(
        self,
        search_endpoint: str,
        search_api_key: str,
        index_name: str,
        openai_endpoint: str,
        openai_api_key: str,
        openai_deployment: str,
        openai_embedding_deployment: str,
        openai_api_version: str
    ):
        self.credential = AzureKeyCredential(search_api_key)
        self.index_name = index_name
        self.search_client = SearchClient(
            endpoint=search_endpoint,
            index_name=index_name,
            credential=self.credential
        )
        self.index_client = SearchIndexClient(
            endpoint=search_endpoint,
            credential=self.credential
        )
        
        # OpenAI client for embeddings
        self.openai_client = AzureOpenAI(
            azure_endpoint=openai_endpoint,
            api_key=openai_api_key,
            api_version=openai_api_version
        )
        self.embedding_model = openai_embedding_deployment
        
        self._ensure_index_exists()
    
    def _ensure_index_exists(self):
        """Create search index if it doesn't exist"""
        try:
            self.index_client.get_index(self.index_name)
            logger.info(f"Index {self.index_name} already exists")
        except Exception:
            logger.info(f"Creating index {self.index_name}")
            self._create_index()
    
    def _create_index(self):
        """Create Azure AI Search index with vector and semantic search"""
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchableField(name="filename", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="content", type=SearchFieldDataType.String, searchable=True),
            SimpleField(name="source_url", type=SearchFieldDataType.String),
            SimpleField(name="image_urls", type=SearchFieldDataType.Collection(SearchFieldDataType.String)),
            SimpleField(name="metadata", type=SearchFieldDataType.String),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=1536,
                vector_search_profile_name="myHnswProfile"
            )
        ]
        
        # Configure vector search
        vector_search = VectorSearch(
            profiles=[
                VectorSearchProfile(
                    name="myHnswProfile",
                    algorithm_configuration_name="myHnsw"
                )
            ],
            algorithms=[
                HnswAlgorithmConfiguration(name="myHnsw")
            ]
        )
        
        # Configure semantic search
        semantic_config = SemanticConfiguration(
            name="my-semantic-config",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="filename"),
                content_fields=[
                    SemanticField(field_name="content")
                ]
            )
        )
        
        semantic_search = SemanticSearch(configurations=[semantic_config])
        
        index = SearchIndex(
            name=self.index_name,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search
        )
        
        self.index_client.create_index(index)
        logger.info(f"Created index {self.index_name}")
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Azure OpenAI"""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise
    
    def index_document(self, document: Dict[str, Any], filename: str, file_url: str):
        """Index a single document (entire Excel file) into Azure AI Search"""
        
        # Prepare content for embedding
        content = document.get('content', '')
        
        # Generate embedding for the combined content
        try:
            content_vector = self.generate_embedding(content)
        except Exception as e:
            logger.error(f"Failed to generate embedding for document {filename}: {str(e)}")
            content_vector = [0.0] * 1536  # Fallback empty vector
        
        # Extract image URLs
        image_urls = []
        for img in document.get('images', []):
            if 'url' in img:
                image_urls.append(img['url'])
        
        # Generate URL-safe Base64 encoded ID
        doc_id = filename
        safe_id = base64.urlsafe_b64encode(doc_id.encode('utf-8')).decode('ascii').rstrip('=')
        
        doc = {
            "id": safe_id,
            "filename": filename,
            "content": content,
            "source_url": file_url,
            "image_urls": image_urls,
            "metadata": json.dumps(document.get('metadata', {})),
            "content_vector": content_vector
        }
        
        try:
            result = self.search_client.upload_documents(documents=[doc])
            logger.info(f"Indexed document: {filename}")
            return result
        except Exception as e:
            logger.error(f"Error indexing document: {str(e)}")
            raise
    
    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        include_images: bool = True
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search (vector + keyword + semantic)"""
        try:
            # Generate query embedding
            query_vector = self.generate_embedding(query)
            
            # Perform hybrid search with semantic ranking
            results = self.search_client.search(
                search_text=query,
                vector_queries=[{
                    "kind": "vector",
                    "vector": query_vector,
                    "fields": "content_vector",
                    "k": top_k * 2  # Get more candidates for semantic reranking
                }],
                select=["id", "filename", "content", "source_url", "image_urls", "metadata"],
                query_type="semantic",
                semantic_configuration_name="my-semantic-config",
                top=top_k
            )
            
            search_results = []
            for result in results:
                # Extract content and create summary
                content = result.get("content", "")
                # Create a summary (first 500 characters)
                summary = content[:500] if content else ""
                
                # Parse metadata
                metadata = {}
                try:
                    metadata = json.loads(result.get("metadata", "{}"))
                except:
                    pass
                
                search_result = {
                    "step_number": "1",  # Single document per file
                    "title": result.get("filename", ""),
                    "summary": summary,
                    "images": result.get("image_urls", []) if include_images else [],
                    "source_document": result.get("filename", ""),
                    "source_url": result.get("source_url", ""),
                    "score": result.get("@search.score", 0.0),
                    "page_number": metadata.get("sheet_count", 1)
                }
                search_results.append(search_result)
            
            return search_results
            
        except Exception as e:
            logger.error(f"Error performing hybrid search: {str(e)}")
            raise
