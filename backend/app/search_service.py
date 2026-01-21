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
        
        # OpenAI client for embeddings and chat
        self.openai_client = AzureOpenAI(
            azure_endpoint=openai_endpoint,
            api_key=openai_api_key,
            api_version=openai_api_version
        )
        self.embedding_model = openai_embedding_deployment
        self.chat_model = openai_deployment
        
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
    
    def _split_text_with_llm(self, text: str, max_chunk_size: int = 6000) -> List[str]:
        """Use LLM (GPT-5.2 with 272K token context) to split text at semantic boundaries
        
        Args:
            text: The text to split (supports up to ~200K tokens / ~600K chars)
            max_chunk_size: Target maximum characters per chunk (default 6000 ≈ 2000 tokens)
                          Must be well under embedding model's 8192 token limit
            
        Returns:
            List of text chunks split at semantic boundaries
        """
        # Calculate approximate number of chunks needed
        estimated_chunks = (len(text) // max_chunk_size) + 1
        
        # GPT-5.2 can handle up to 272K tokens input (~800K chars)
        # Conservative limit: 600K chars (~200K tokens) to leave room for prompt
        max_input_chars = 600000
        input_text = text[:max_input_chars] if len(text) > max_input_chars else text
        
        if len(text) > max_input_chars:
            logger.warning(f"Text length {len(text)} chars exceeds {max_input_chars} limit, truncating for LLM processing")
        
        prompt = f"""以下のテキストを{estimated_chunks}個程度の意味のあるセクションに分割してください。

重要な制約:
- 各セクションは**必ず{max_chunk_size}文字以下**にしてください（embeddings APIの8,192トークン制限に対応するため）
- 分割は文章の意味的な区切れ目で行ってください（例：トピックの変わり目、手順の区切り、セクションの終わり）
- セクション数は{estimated_chunks}個前後を目安にしてください

テキストを分割し、各セクションを以下のJSON配列形式で返してください：
["セクション1のテキスト", "セクション2のテキスト", ...]

元のテキスト:
{input_text}"""

        try:
            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": "あなたはテキストを意味のある単位で分割する専門家です。JSON配列形式で応答してください。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content
            logger.debug(f"LLM chunking response: {result[:200]}...")
            
            # Parse JSON response
            parsed = json.loads(result)
            
            # Handle different response formats
            if isinstance(parsed, dict):
                chunks = parsed.get('chunks', parsed.get('sections', list(parsed.values())[0] if parsed else []))
            elif isinstance(parsed, list):
                chunks = parsed
            else:
                raise ValueError("Unexpected response format from LLM")
            
            if not chunks or not isinstance(chunks, list):
                raise ValueError("No valid chunks returned from LLM")
            
            logger.info(f"LLM split text into {len(chunks)} semantic chunks")
            return chunks
            
        except Exception as e:
            logger.error(f"Error in LLM-based chunking: {str(e)}")
            # Fallback to simple chunking
            logger.info("Falling back to simple character-based chunking")
            chunks = []
            for i in range(0, len(text), max_chunk_size):
                chunks.append(text[i:i + max_chunk_size])
            return chunks
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Azure OpenAI
        
        If text exceeds token limit, uses GPT-5.2 LLM to split at semantic boundaries,
        then generates and averages embeddings.
        text-embedding-3-small max tokens: 8192 (≈24,576 chars at 3 chars/token)
        """
        try:
            # Conservative limit: 6000 chars ≈ 2000 tokens (safe margin for 8192 limit)
            max_chars = 6000
            
            if len(text) <= max_chars:
                response = self.openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=text
                )
                return response.data[0].embedding
            
            # Text too long - use GPT-5.2 LLM to chunk semantically
            logger.info(f"Text length {len(text)} chars exceeds {max_chars} limit, using GPT-5.2 for semantic chunking...")
            chunks = self._split_text_with_llm(text, max_chunk_size=max_chars)
            
            logger.info(f"Processing {len(chunks)} semantic chunks")
            
            # Generate embeddings for each chunk
            embeddings = []
            for idx, chunk in enumerate(chunks):
                logger.debug(f"Generating embedding for chunk {idx + 1}/{len(chunks)} (length: {len(chunk)})")
                
                # If a chunk is still too long, truncate it
                if len(chunk) > max_chars:
                    logger.warning(f"Chunk {idx + 1} still too long ({len(chunk)} chars), truncating")
                    chunk = chunk[:max_chars]
                
                response = self.openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=chunk
                )
                embeddings.append(response.data[0].embedding)
            
            # Average the embeddings
            avg_embedding = [sum(vals) / len(vals) for vals in zip(*embeddings)]
            logger.info(f"Averaged {len(embeddings)} chunk embeddings into single vector")
            
            return avg_embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            raise
    
    def index_document(self, document: Dict[str, Any], filename: str, file_url: str):
        """Index document by splitting into chunks and indexing each chunk separately"""
        
        # Prepare content for chunking
        content = document.get('content', '')
        
        # Build image mapping with position markers
        all_images = document.get('images', [])
        image_map = {}  # Maps image index to image URL (without markers)
        
        for idx, img in enumerate(all_images):
            if 'url' in img:
                # Store just the URL without any markers
                image_map[idx] = img['url']
        
        # Split content into chunks for indexing
        max_chunk_size = 6000  # Same as embedding limit
        
        if len(content) <= max_chunk_size:
            # Content fits in single chunk
            chunks = [content]
        else:
            # Use LLM to split into semantic chunks
            logger.info(f"Splitting document {filename} into chunks for indexing...")
            chunks = self._split_text_with_llm(content, max_chunk_size=max_chunk_size)
        
        # Index each chunk as a separate document
        indexed_docs = []
        for chunk_idx, chunk in enumerate(chunks):
            # Find which images are referenced in this chunk
            chunk_image_urls = []
            
            # Extract actual image filenames from the chunk content
            import re
            # Pattern: (filename.png) at the end of image descriptions
            image_filename_pattern = r'\(([^)]+\.png)\)'
            image_filenames_in_chunk = re.findall(image_filename_pattern, chunk)
            
            # Create a mapping from filename to URL for quick lookup
            filename_to_url = {}
            for idx, img in enumerate(all_images):
                if 'url' in img and 'filename' in img:
                    filename_to_url[img['filename']] = img['url']
            
            # Add URLs for images that are actually in this chunk
            for filename in image_filenames_in_chunk:
                if filename in filename_to_url:
                    url = filename_to_url[filename]
                    # Avoid duplicates
                    if url not in chunk_image_urls:
                        chunk_image_urls.append(url)
            
            num_images_in_chunk = len(chunk_image_urls)
            
            # Generate embedding for this chunk
            try:
                content_vector = self.generate_embedding(chunk)
            except Exception as e:
                logger.error(f"Failed to generate embedding for chunk {chunk_idx} of {filename}: {str(e)}")
                content_vector = [0.0] * 1536  # Fallback empty vector
            
            # Generate unique ID for this chunk
            doc_id = f"{filename}_chunk{chunk_idx}"
            safe_id = base64.urlsafe_b64encode(doc_id.encode('utf-8')).decode('ascii').rstrip('=')
            
            # Create metadata for this chunk
            chunk_metadata = document.get('metadata', {}).copy()
            chunk_metadata['chunk_index'] = chunk_idx
            chunk_metadata['total_chunks'] = len(chunks)
            chunk_metadata['image_count_in_chunk'] = len(chunk_image_urls)
            
            doc = {
                "id": safe_id,
                "filename": filename,
                "content": chunk,
                "source_url": file_url,
                "image_urls": chunk_image_urls,  # Only images relevant to this chunk
                "metadata": json.dumps(chunk_metadata),
                "content_vector": content_vector
            }
            indexed_docs.append(doc)
            
            logger.info(f"Chunk {chunk_idx}: {len(chunk_image_urls)} images, {num_images_in_chunk} image markers")
        
        try:
            result = self.search_client.upload_documents(documents=indexed_docs)
            logger.info(f"Indexed {len(indexed_docs)} chunks for document: {filename}")
            return result
        except Exception as e:
            logger.error(f"Error indexing document chunks: {str(e)}")
            raise
    
    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        include_images: bool = True
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search (vector + keyword + semantic) and extract relevant information using LLM"""
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
                # Extract content
                content = result.get("content", "")
                all_image_urls = result.get("image_urls", [])
                
                # Use LLM to extract relevant information
                extracted_info = self._extract_relevant_info_with_llm(
                    query=query,
                    content=content,
                    all_image_urls=all_image_urls,
                    include_images=include_images
                )
                
                # Skip if no relevant information found
                if not extracted_info or not extracted_info.get("answer"):
                    continue
                
                search_result = {
                    "answer": extracted_info.get("answer", ""),
                    "images": extracted_info.get("images", []),
                    "source_document": result.get("filename", ""),
                    "source_url": result.get("source_url", ""),
                    "score": result.get("@search.score", 0.0)
                }
                search_results.append(search_result)
            
            return search_results
            
        except Exception as e:
            logger.error(f"Error performing hybrid search: {str(e)}")
            raise
    
    def _extract_relevant_info_with_llm(
        self,
        query: str,
        content: str,
        all_image_urls: List[str],
        include_images: bool
    ) -> Dict[str, Any]:
        """Use LLM to extract relevant information and select relevant images from the document content
        
        Args:
            query: User's question
            content: Full document content with image markers (filename.png)
            all_image_urls: List of all image URLs available in the document
            include_images: Whether to include images in the response
            
        Returns:
            Dictionary with 'answer' (text) and 'images' (list of relevant image URLs)
        """
        try:
            # Extract image filename to URL mapping
            import re
            image_filename_pattern = r'\(([^)]+\.png)\)'
            image_filenames = re.findall(image_filename_pattern, content)
            
            # Build a list of image references for LLM
            image_references = []
            if include_images and all_image_urls:
                for idx, url in enumerate(all_image_urls):
                    # Extract filename from URL
                    filename = url.split('/')[-1]
                    image_references.append(f"{idx}: {filename}")
            
            image_context = "\n".join(image_references) if image_references else "画像なし"
            
            # Prompt for LLM to extract relevant information
            prompt = f"""以下は作業標準書のドキュメントの一部です。ユーザーの質問に答えるために、このドキュメントから関連する情報のみを抽出してください。

**重要な制約:**
1. ドキュメントに記載されている内容のみを使用してください（推測禁止）
2. ユーザーの質問に直接関連する文章のみを抽出してください
3. 質問に関連する画像の番号をリストで指定してください（画像番号は0から始まります）
4. ドキュメントに質問の答えが含まれていない場合は、answer を空文字列にしてください

**ユーザーの質問:**
{query}

**ドキュメントの内容:**
{content}

**利用可能な画像一覧:**
{image_context}

**回答形式（JSON）:**
{{
  "answer": "質問に対する回答テキスト（ドキュメントから関連部分を抽出）",
  "relevant_image_indices": [0, 2, 5]
}}

ドキュメントに質問の答えが含まれていない場合:
{{
  "answer": "",
  "relevant_image_indices": []
}}"""

            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": "あなたは作業標準書から必要な情報のみを抽出する専門家です。ドキュメントに記載されている内容のみを使用し、推測は一切しないでください。JSON形式で応答してください。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            logger.debug(f"LLM extraction response: {result_text[:200]}...")
            
            # Parse JSON response
            parsed = json.loads(result_text)
            answer = parsed.get("answer", "")
            relevant_indices = parsed.get("relevant_image_indices", [])
            
            # Select relevant images based on indices
            selected_images = []
            if include_images and relevant_indices and all_image_urls:
                for idx in relevant_indices:
                    if isinstance(idx, int) and 0 <= idx < len(all_image_urls):
                        selected_images.append(all_image_urls[idx])
            
            logger.info(f"Extracted answer length: {len(answer)}, selected {len(selected_images)} images from {len(all_image_urls)} total")
            
            return {
                "answer": answer,
                "images": selected_images
            }
            
        except Exception as e:
            logger.error(f"Error extracting relevant info with LLM: {str(e)}")
            # Fallback: return truncated content and all images
            return {
                "answer": content[:1000] if content else "",
                "images": all_image_urls[:3] if include_images else []
            }
