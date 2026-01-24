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
        self.search_endpoint = search_endpoint
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
        
        # Track schema-based indexes
        self.schema_indexes = {}  # Maps schema_id to index_name
        
        # Cache for field name translations (to avoid redundant AI calls)
        self.field_name_cache = {}  # Maps original field name to English field name
        
        # Track if default index has been checked
        self._default_index_checked = False
        
        # Load existing schema indexes on initialization
        self.load_existing_schema_indexes()
    
    def _ensure_default_index_exists(self):
        """Create default search index if it doesn't exist (lazy initialization)"""
        if self._default_index_checked:
            return
        
        try:
            self.index_client.get_index(self.index_name)
            logger.info(f"Default index '{self.index_name}' already exists")
            # Check document count
            doc_count = self.get_document_count()
            logger.info(f"Index '{self.index_name}' contains {doc_count} documents")
        except Exception:
            logger.info(f"Creating default index '{self.index_name}' (first use)")
            self._create_index()
        
        self._default_index_checked = True
    
    def get_document_count(self, schema_id: Optional[str] = None) -> int:
        """Get the number of documents in an index
        
        Args:
            schema_id: If provided, gets count from schema-specific index
            
        Returns:
            Number of documents in the index
        """
        try:
            if schema_id and schema_id in self.schema_indexes:
                index_name = self.schema_indexes[schema_id]
                client = SearchClient(
                    endpoint=self.search_endpoint,
                    index_name=index_name,
                    credential=self.credential
                )
            else:
                index_name = self.index_name
                client = self.search_client
            
            # Search with no filter to get total count
            results = client.search(search_text="*", include_total_count=True, top=0)
            count = results.get_count()
            logger.debug(f"Index '{index_name}' document count: {count}")
            return count
        except Exception as e:
            logger.error(f"Error getting document count: {str(e)}")
            return 0
    
    def _get_schema_index_name(self, schema_id: str) -> str:
        """Get the index name for a specific schema"""
        # Sanitize schema_id for use in index name
        safe_schema_id = schema_id.replace('-', '').replace('_', '')[:20]
        return f"{self.index_name}-schema-{safe_schema_id}".lower()
    
    def _translate_field_name_to_english(self, field_name: str, field_description: str = None) -> str:
        """Translate field name to English using AI and sanitize for Azure Search
        
        Uses GPT to translate Japanese (or other language) field names to 
        meaningful English field names that comply with Azure AI Search requirements.
        
        Args:
            field_name: Original field name (e.g., "作業名")
            field_description: Optional field description for context
            
        Returns:
            English field name in snake_case (e.g., "work_name")
            
        Examples:
            "作業名" -> "work_name"
            "管理番号" -> "management_number"
            "準備物" -> "preparation_items"
            "手顺1" -> "step_1"
        """
        # Check cache first
        cache_key = f"{field_name}:{field_description or ''}"
        if cache_key in self.field_name_cache:
            logger.debug(f"Using cached field name: '{field_name}' -> '{self.field_name_cache[cache_key]}'")
            return self.field_name_cache[cache_key]
        
        # If already in English (ASCII only), just sanitize
        if field_name.isascii():
            sanitized = self._sanitize_ascii_field_name(field_name)
            self.field_name_cache[cache_key] = sanitized
            return sanitized
        
        try:
            # Build prompt for AI translation
            context = f" (Description: {field_description})" if field_description else ""
            
            prompt = f"""Convert the following field name to a valid English field name for a database.

Field name: {field_name}{context}

Requirements:
1. Use English only (ASCII characters)
2. Use snake_case format (lowercase with underscores)
3. Start with a letter (a-z)
4. Use only letters, numbers, and underscores
5. Be descriptive and concise (max 50 characters)
6. If it's a numbered field (like "手顺1"), include the number (e.g., "step_1")

Examples:
- "作業名" -> "work_name"
- "管理番号" -> "management_number"
- "準備物" -> "preparation_items"
- "手顺1" -> "step_1"
- "手顺1の画像" -> "step_1_image"
- "注意事項" -> "precautions"

Respond with ONLY the English field name, nothing else."""

            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": "You are an expert at translating field names to English database-friendly names. Respond with only the field name, no explanations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=50
            )
            
            english_name = response.choices[0].message.content.strip()
            
            # Additional sanitization to ensure Azure Search compliance
            sanitized = self._sanitize_ascii_field_name(english_name)
            
            # Cache the result
            self.field_name_cache[cache_key] = sanitized
            
            logger.info(f"Translated field name: '{field_name}' -> '{sanitized}'")
            return sanitized
            
        except Exception as e:
            logger.error(f"Error translating field name '{field_name}': {str(e)}")
            # Fallback: use a safe default
            fallback = f"field_{hash(field_name) % 10000}"
            self.field_name_cache[cache_key] = fallback
            return fallback
    
    def _sanitize_ascii_field_name(self, field_name: str) -> str:
        """Sanitize ASCII field name for Azure AI Search
        
        Azure AI Search field names must:
        1. Begin with a letter (a-z, A-Z)
        2. Contain only ASCII letters, digits, or underscore
        3. Be unique within the index
        
        Args:
            field_name: ASCII field name
            
        Returns:
            Sanitized field name
        """
        import re
        
        # Convert to lowercase
        sanitized = field_name.lower()
        
        # Replace any non-alphanumeric characters (except underscore) with underscore
        sanitized = re.sub(r'[^a-z0-9_]', '_', sanitized)
        
        # Remove consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        
        # Ensure it starts with a letter
        if not sanitized or not sanitized[0].isalpha():
            sanitized = f"field_{sanitized}" if sanitized else "field"
        
        # Ensure it's not too long (Azure limit is 128 chars, leave room for _vector)
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        
        return sanitized
    
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
    
    def create_schema_based_index(self, schema):
        """
        Create a dynamic index based on user-defined schema
        
        For each field in the schema:
        - Creates a searchable text field (field_name)
        - Creates a vector field (field_name_vector)
        
        Args:
            schema: ExcelSchema object with field definitions
        """
        from app.models import FieldDataType
        
        schema_index_name = self._get_schema_index_name(schema.id)
        
        # Check if index already exists
        try:
            self.index_client.get_index(schema_index_name)
            logger.info(f"Schema-based index '{schema_index_name}' already exists")
            self.schema_indexes[schema.id] = schema_index_name
            logger.info(f"Schema index registered: schema_id='{schema.id}' -> index_name='{schema_index_name}'")
            return schema_index_name
        except Exception:
            logger.info(f"Creating new schema-based index '{schema_index_name}'")

        
        # Build field list
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchableField(name="filename", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="source_url", type=SearchFieldDataType.String),
            SimpleField(name="schema_id", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="schema_name", type=SearchFieldDataType.String, filterable=True),
            SimpleField(name="metadata", type=SearchFieldDataType.String),
        ]
        
        # Add user-defined fields from schema
        vector_profile_name = "myHnswProfile"
        semantic_content_fields = []
        
        # Helper function to process fields recursively (for nested table fields)
        def add_fields_from_definition(field_def, parent_safe_name=None):
            field_name = field_def.name
            # Translate field name to English using AI
            safe_field_name = self._translate_field_name_to_english(field_name, field_def.description)
            
            # If this is a sub-field, prefix with parent name
            if parent_safe_name:
                safe_field_name = f"{parent_safe_name}_{safe_field_name}"
            
            if field_def.data_type == FieldDataType.TEXT:
                # Add searchable text field
                fields.append(
                    SearchableField(
                        name=safe_field_name,
                        type=SearchFieldDataType.String,
                        searchable=True,
                        filterable=False,
                        facetable=False
                    )
                )
                # Add to semantic content fields
                semantic_content_fields.append(SemanticField(field_name=safe_field_name))
                
            elif field_def.data_type == FieldDataType.IMAGE:
                # For image fields, store the text description
                fields.append(
                    SearchableField(
                        name=safe_field_name,
                        type=SearchFieldDataType.String,
                        searchable=True,
                        filterable=False,
                        facetable=False
                    )
                )
                semantic_content_fields.append(SemanticField(field_name=safe_field_name))
                
            elif field_def.data_type == FieldDataType.TABLE:
                # For table type, only create fields for sub-fields (flattened)
                # This allows searching within specific columns of the table
                # The parent table field itself is not stored to avoid redundancy
                if field_def.sub_fields:
                    for sub_field in field_def.sub_fields:
                        add_fields_from_definition(sub_field, safe_field_name)
                # Note: No parent field or vector for table type - only sub-fields are indexed
                return  # Skip adding vector field for table type
            
            # Add vector field for this field (not for table type)
            fields.append(
                SearchField(
                    name=f"{safe_field_name}_vector",
                    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True,
                    vector_search_dimensions=1536,
                    vector_search_profile_name=vector_profile_name
                )
            )
        
        # Process all top-level fields
        for field in schema.fields:
            add_fields_from_definition(field)
        
        # Configure vector search
        vector_search = VectorSearch(
            profiles=[
                VectorSearchProfile(
                    name=vector_profile_name,
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
                content_fields=semantic_content_fields
            )
        )
        
        semantic_search = SemanticSearch(configurations=[semantic_config])
        
        # Create the index
        index = SearchIndex(
            name=schema_index_name,
            fields=fields,
            vector_search=vector_search,
            semantic_search=semantic_search
        )
        
        self.index_client.create_index(index)
        logger.info(f"Created schema-based index {schema_index_name} with {len(schema.fields)} user-defined fields")
        
        # Track this index
        self.schema_indexes[schema.id] = schema_index_name
        logger.info(f"Schema index registered: schema_id='{schema.id}' -> index_name='{schema_index_name}'")
        logger.info(f"Currently registered schema indexes: {list(self.schema_indexes.keys())}")
        
        return schema_index_name
    
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
        
        # Ensure default index exists (lazy initialization)
        self._ensure_default_index_exists()
        
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
    
    def index_document_with_schema(
        self, 
        document: Dict[str, Any], 
        filename: str, 
        file_url: str,
        schema
    ):
        """
        Index document using schema-based field extraction
        
        Creates/uses a schema-specific index where each user-defined field gets:
        - A searchable text field (field_name)
        - A vector field (field_name_vector)
        
        Args:
            document: Document with content, images, and extracted_fields
            filename: Name of the file
            file_url: URL of the source file
            schema: ExcelSchema object with field definitions
        """
        from app.models import FieldDataType
        
        logger.info(f"Indexing document with schema: {schema.name} (ID: {schema.id})")
        
        # Ensure schema-specific index exists
        schema_index_name = self.create_schema_based_index(schema)
        
        # Create a search client for this schema's index
        schema_search_client = SearchClient(
            endpoint=self.search_endpoint,
            index_name=schema_index_name,
            credential=self.credential
        )
        
        # Get extracted fields from Content Understanding
        extracted_fields = document.get('extracted_fields', {})
        all_images = document.get('images', [])
        
        logger.info(f"Using extracted fields from Content Understanding: {len(extracted_fields)} fields")
        
        # Prepare field data and vectors
        field_data = {}
        field_vectors = {}
        
        # Helper function to process fields recursively (for nested table fields)
        def process_field(field_def, parent_safe_name=None, parent_value=None):
            field_name = field_def.name
            # Translate field name to English using AI (will use cache if already translated)
            safe_field_name = self._translate_field_name_to_english(field_name, field_def.description)
            
            # If this is a sub-field, prefix with parent name
            if parent_safe_name:
                safe_field_name = f"{parent_safe_name}_{safe_field_name}"
            
            logger.info(f"Processing field: {field_name} -> {safe_field_name} (type: {field_def.data_type})")
            
            # Get the extracted value for this field
            if parent_value is not None:
                # This is a sub-field, use parent_value
                field_value = parent_value.get(field_name) if isinstance(parent_value, dict) else None
            else:
                # Top-level field
                field_value = extracted_fields.get(field_name)
            
            if field_def.data_type == FieldDataType.TABLE:
                # Handle table type - field_value should be an array
                if field_value is None or not isinstance(field_value, list):
                    logger.warning(f"Table field '{field_name}' has no valid array value")
                else:
                    logger.info(f"Table field '{field_name}' has {len(field_value)} rows")
                    
                    # Process sub-fields: flatten all rows into searchable text fields
                    # This allows searching within specific columns of the table
                    if field_def.sub_fields:
                        for sub_field in field_def.sub_fields:
                            sub_field_name = sub_field.name
                            sub_safe_name = self._translate_field_name_to_english(sub_field_name, sub_field.description)
                            full_sub_safe_name = f"{safe_field_name}_{sub_safe_name}"
                            
                            # Collect all values for this sub-field across all rows
                            sub_field_values = []
                            for row in field_value:
                                if isinstance(row, dict) and sub_field_name in row:
                                    val = row[sub_field_name]
                                    if val:
                                        sub_field_values.append(str(val))
                            
                            # Join all values with newlines for searchability
                            sub_field_content = "\n".join(sub_field_values) if sub_field_values else ""
                            
                            # Store sub-field data
                            field_data[full_sub_safe_name] = sub_field_content
                            
                            # Generate vector for sub-field
                            if sub_field_content:
                                try:
                                    vector = self.generate_embedding(sub_field_content)
                                    field_vectors[f"{full_sub_safe_name}_vector"] = vector
                                except Exception as e:
                                    logger.error(f"Error generating embedding for sub-field {full_sub_safe_name}: {str(e)}")
                                    field_vectors[f"{full_sub_safe_name}_vector"] = [0.0] * 1536
                            else:
                                field_vectors[f"{full_sub_safe_name}_vector"] = [0.0] * 1536
                
                # Note: Table field itself is NOT stored - only sub-fields are indexed
                # This avoids redundancy since all data is available through sub-fields
                    
            else:
                # Handle TEXT and IMAGE types
                if field_value is None or (isinstance(field_value, str) and not field_value.strip()):
                    field_content = ""
                    logger.warning(f"Field '{field_name}' has no extracted value")
                else:
                    field_content = str(field_value)
                    logger.info(f"Field '{field_name}' has value: {field_content[:100]}...")
                
                # Store field data
                field_data[safe_field_name] = field_content
                
                # Generate vector for this field
                if field_content:
                    try:
                        vector = self.generate_embedding(field_content)
                        field_vectors[f"{safe_field_name}_vector"] = vector
                        logger.debug(f"Generated embedding for {safe_field_name} ({len(field_content)} chars)")
                    except Exception as e:
                        logger.error(f"Error generating embedding for field {safe_field_name}: {str(e)}")
                        field_vectors[f"{safe_field_name}_vector"] = [0.0] * 1536
                else:
                    field_vectors[f"{safe_field_name}_vector"] = [0.0] * 1536
        
        # Process all top-level fields
        for field in schema.fields:
            process_field(field)
        
        # Create search document with schema fields
        doc_id = filename
        safe_id = base64.urlsafe_b64encode(doc_id.encode('utf-8')).decode('ascii').rstrip('=')
        
        # Build the document
        doc = {
            "id": safe_id,
            "filename": filename,
            "source_url": file_url,
            "schema_id": schema.id,
            "schema_name": schema.name,
            "metadata": json.dumps({
                "upload_date": document.get('metadata', {}).get('upload_date', ''),
                "image_count": len(all_images),
                "field_count": len(schema.fields),
                "extracted_field_count": len(extracted_fields)
            })
        }
        
        # Add all field data and vectors
        doc.update(field_data)
        doc.update(field_vectors)
        
        # Index the document
        try:
            result = schema_search_client.upload_documents(documents=[doc])
            logger.info(f"Successfully indexed document '{filename}' in schema-based index '{schema_index_name}'")
            logger.info(f"Document has {len(field_data)} fields with {len(field_vectors)} vector fields")
            return result
        except Exception as e:
            logger.error(f"Error indexing document with schema: {str(e)}")
            raise
    
    def _extract_field_content(self, full_content: str, field) -> str:
        """
        Extract content for a specific field from the full document content
        
        This is a placeholder implementation. In production, you would:
        1. Use Azure AI Content Understanding to analyze Excel structure
        2. Match field definitions to actual Excel columns/sections
        3. Extract only the relevant content for each field
        
        For now, we use a simple heuristic:
        - Look for field name in the content
        - Extract surrounding text
        """
        field_name = field.name
        
        # Simple heuristic: find field name mentions and extract context
        lines = full_content.split('\\n')
        relevant_lines = []
        
        for i, line in enumerate(lines):
            # Check if field name or description appears in the line
            if field_name.lower() in line.lower() or (field.description and field.description.lower() in line.lower()):
                # Include some context lines
                start = max(0, i - 2)
                end = min(len(lines), i + 10)
                relevant_lines.extend(lines[start:end])
        
        if relevant_lines:
            extracted = '\\n'.join(relevant_lines)
            logger.debug(f"Extracted {len(extracted)} chars for field '{field_name}'")
            return extracted
        
        # Fallback: if field name not found, distribute content among fields
        # This is a simple fallback - divide content among all fields
        # In production, you would use AI to properly segment the content
        logger.warning(f"Could not find specific content for field '{field_name}', using full content")
        return full_content
    
    def _determine_relevant_fields(self, query: str, schema) -> List[str]:
        """
        Use AI to determine which fields are relevant to the user's query
        
        Args:
            query: User's search query
            schema: ExcelSchema object with field definitions
            
        Returns:
            List of relevant field names
        """
        try:
            # Build field descriptions for the LLM
            field_descriptions = []
            for field in schema.fields:
                desc = f"- {field.name} ({field.data_type})"
                if field.description:
                    desc += f": {field.description}"
                field_descriptions.append(desc)
            
            fields_text = "\n".join(field_descriptions)
            
            prompt = f"""ユーザーの質問に答えるために、どのフィールドが関連しているかを判断してください。

**利用可能なフィールド:**
{fields_text}

**ユーザーの質問:**
{query}

質問に関連するフィールドの名前をJSON配列形式で返してください。
関連するフィールドが複数ある場合は、すべてのフィールド名を含めてください。
関連するフィールドがない場合は、空の配列を返してください。

**回答形式（JSON）:**
{{
  "relevant_fields": ["フィールド名1", "フィールド名2"]
}}"""

            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": "あなたはユーザーの質問に関連するフィールドを判断する専門家です。JSON形式で応答してください。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            logger.debug(f"Field determination response: {result_text}")
            
            # Parse JSON response
            parsed = json.loads(result_text)
            relevant_fields = parsed.get("relevant_fields", [])
            
            logger.info(f"Determined {len(relevant_fields)} relevant fields for query: {relevant_fields}")
            return relevant_fields
            
        except Exception as e:
            logger.error(f"Error determining relevant fields: {str(e)}")
            # Fallback: return all fields
            return [field.name for field in schema.fields]
    
    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        include_images: bool = True,
        schema_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search (vector + keyword + semantic) and extract relevant information using LLM
        
        Args:
            query: Search query
            top_k: Number of results to return
            include_images: Whether to include images in results
            schema_id: If provided, searches in the schema-specific index.
                      If None, searches across ALL indexes (default + all schema indexes)
        
        Returns:
            List of search results
        """
        try:
            logger.info(f"=== HYBRID SEARCH START ===")
            logger.info(f"Query: '{query}'")
            logger.info(f"Top K: {top_k}")
            logger.info(f"Include Images: {include_images}")
            logger.info(f"Schema ID: {schema_id}")
            logger.info(f"Registered schema indexes: {list(self.schema_indexes.keys())}")
            
            # Determine which index(es) to search
            if schema_id:
                # Search in specific schema index
                if schema_id in self.schema_indexes:
                    logger.info(f"Using schema-specific index for schema_id: {schema_id}")
                    return self._hybrid_search_schema_index(query, top_k, include_images, schema_id)
                else:
                    logger.warning(f"Schema ID '{schema_id}' not found in registered indexes. Falling back to default index.")
                    logger.info(f"Using default index: {self.index_name}")
                    return self._hybrid_search_default_index(query, top_k, include_images)
            else:
                # Search ALL indexes (default + all schema indexes)
                logger.info(f"Searching across ALL indexes (default + {len(self.schema_indexes)} schema indexes)")
                return self._hybrid_search_all_indexes(query, top_k, include_images)
            
        except Exception as e:
            logger.error(f"Error performing hybrid search: {str(e)}")
            raise
    
    def _hybrid_search_all_indexes(
        self,
        query: str,
        top_k: int,
        include_images: bool
    ) -> List[Dict[str, Any]]:
        """
        Search across all indexes (default + all schema indexes) and merge results
        
        Results are merged and re-ranked by score
        """
        all_results = []
        
        # Search default index
        try:
            logger.info(f"Searching default index: {self.index_name}")
            default_results = self._hybrid_search_default_index(query, top_k, include_images)
            all_results.extend(default_results)
            logger.info(f"Default index returned {len(default_results)} results")
        except Exception as e:
            logger.error(f"Error searching default index: {str(e)}")
        
        # Search all schema indexes
        for schema_id in self.schema_indexes.keys():
            try:
                logger.info(f"Searching schema index: {schema_id}")
                schema_results = self._hybrid_search_schema_index(query, top_k, include_images, schema_id)
                all_results.extend(schema_results)
                logger.info(f"Schema index {schema_id} returned {len(schema_results)} results")
            except Exception as e:
                logger.error(f"Error searching schema index {schema_id}: {str(e)}")
        
        # Sort by score (descending) and return top_k
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        merged_results = all_results[:top_k]
        
        logger.info(f"Merged {len(all_results)} total results, returning top {len(merged_results)}")
        return merged_results
    
    def _hybrid_search_schema_index(
        self,
        query: str,
        top_k: int,
        include_images: bool,
        schema_id: str
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search on a schema-specific index
        
        Uses AI to determine which fields are relevant to the query,
        then searches across those fields with their vectors
        """
        from app.models import FieldDataType
        
        schema_index_name = self.schema_indexes[schema_id]
        logger.info(f"Searching in schema-based index: {schema_index_name}")
        
        # Create search client for schema index
        schema_search_client = SearchClient(
            endpoint=self.search_endpoint,
            index_name=schema_index_name,
            credential=self.credential
        )
        
        # TODO: Get schema object to determine relevant fields
        # For now, we'll search across all vector fields in the index
        
        # Generate query embedding
        query_vector = self.generate_embedding(query)
        
        # Get index definition to find all vector fields
        try:
            index_def = self.index_client.get_index(schema_index_name)
            vector_fields = [
                field.name for field in index_def.fields
                if field.name.endswith('_vector')
            ]
            logger.info(f"Found {len(vector_fields)} vector fields: {vector_fields}")
        except Exception as e:
            logger.error(f"Error getting index definition: {str(e)}")
            vector_fields = []
        
        # Perform hybrid search across all vector fields
        # Build vector queries for all vector fields
        vector_queries = []
        for vector_field in vector_fields[:5]:  # Limit to first 5 to avoid too many queries
            vector_queries.append({
                "kind": "vector",
                "vector": query_vector,
                "fields": vector_field,
                "k": top_k * 2
            })
        
        # If no vector queries, add at least one default
        if not vector_queries:
            logger.warning("No vector fields found, using default search")
        
        # Select fields to return (all non-vector fields)
        select_fields = [
            field.name for field in index_def.fields
            if not field.name.endswith('_vector')
        ]
        
        results = schema_search_client.search(
            search_text=query,
            vector_queries=vector_queries if vector_queries else None,
            select=select_fields,
            query_type="semantic",
            semantic_configuration_name="my-semantic-config",
            top=top_k
        )
        
        search_results = []
        for result in results:
            # Extract all field data
            filename = result.get("filename", "")
            source_url = result.get("source_url", "")
            schema_name = result.get("schema_name", "")
            
            # Collect all field content
            field_contents = []
            for field_name in select_fields:
                if field_name not in ['id', 'filename', 'source_url', 'schema_id', 'schema_name', 'metadata']:
                    field_value = result.get(field_name, "")
                    if field_value:
                        field_contents.append(f"[{field_name}]\\n{field_value}")
            
            combined_content = "\\n\\n".join(field_contents)
            
            # Use LLM to extract relevant information
            extracted_info = self._extract_relevant_info_with_llm(
                query=query,
                content=combined_content,
                all_image_urls=[],  # Schema-based documents don't have image_urls in the same way
                include_images=False  # For now, image handling in schema mode is different
            )
            
            # Skip if no relevant information found
            if not extracted_info or not extracted_info.get("relevant_content"):
                continue
            
            search_result = {
                "relevant_content": extracted_info.get("relevant_content", ""),
                "images": extracted_info.get("images", []),
                "source_document": filename,
                "source_url": source_url,
                "score": result.get("@search.score", 0.0),
                "schema_name": schema_name
            }
            
            search_results.append(search_result)
        
        logger.info(f"Schema-based search returned {len(search_results)} results (before RAG)")
        
        # Generate final answer using RAG if we have results
        if search_results:
            logger.info("Generating final answer using RAG for schema index results...")
            final_answer = self._generate_answer_with_rag(query, search_results)
            
            # Replace relevant_content with generated answer in each result
            for result in search_results:
                result["answer"] = final_answer
                del result["relevant_content"]  # Remove intermediate data
        
        return search_results
    
    def _hybrid_search_default_index(
        self,
        query: str,
        top_k: int,
        include_images: bool
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search (vector + keyword + semantic) and extract relevant information using LLM
        
        Searches the default index (non-schema-based documents)
        """
        try:
            # Ensure default index exists before searching
            self._ensure_default_index_exists()
            
            logger.info(f"Generating embedding for query: '{query}'")
            # Generate query embedding
            query_vector = self.generate_embedding(query)
            logger.info(f"Embedding generated, vector length: {len(query_vector)}")
            
            # Check index document count before searching
            doc_count = self.get_document_count()
            logger.info(f"Index '{self.index_name}' contains {doc_count} documents before search")
            
            # Perform hybrid search with semantic ranking
            logger.info(f"Executing search on index: {self.index_name}")
            logger.info(f"Search parameters: top_k={top_k}, semantic=True, vector_k={top_k * 2}")
            
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
            
            # Convert to list to count results
            results_list = list(results)
            logger.info(f"Azure Search returned {len(results_list)} raw results")
            
            search_results = []
            logger.info(f"Processing {len(results_list)} results from Azure Search")
            
            for idx, result in enumerate(results_list):
                logger.debug(f"Processing result {idx + 1}/{len(results_list)}: {result.get('filename', 'unknown')}")
                # Extract content
                content = result.get("content", "")
                all_image_urls = result.get("image_urls", [])
                metadata_str = result.get("metadata", "{}")
                
                # Parse metadata to check for schema
                try:
                    metadata = json.loads(metadata_str)
                except:
                    metadata = {}
                
                # Check if document has schema-based indexing
                if metadata.get('has_schema') and metadata.get('field_data'):
                    # Get schema info (in production, fetch from schema service)
                    # For now, we'll work with the field data stored in metadata
                    field_data = metadata.get('field_data', {})
                    
                    # Filter content to only include relevant fields
                    # This is a simplified version - in production, you would:
                    # 1. Fetch the actual schema
                    # 2. Use _determine_relevant_fields to identify relevant fields
                    # 3. Search only within those fields
                    
                    logger.info(f"Document has schema: {metadata.get('schema_name')}")
                    # For now, proceed with the full content but log that it has schema
                
                # Use LLM to extract relevant information
                logger.debug(f"Extracting relevant info with LLM for result {idx + 1}")
                logger.debug(f"Content length: {len(content)}, Image URLs: {len(all_image_urls)}")
                
                # First extract relevant portions
                extracted_info = self._extract_relevant_info_with_llm(
                    query=query,
                    content=content,
                    all_image_urls=all_image_urls,
                    include_images=include_images
                )
                
                # Skip if no relevant information found
                if not extracted_info or not extracted_info.get("relevant_content"):
                    logger.debug(f"Result {idx + 1} skipped: No relevant information extracted by LLM")
                    continue
                
                logger.debug(f"Result {idx + 1} included: Relevant content length={len(extracted_info.get('relevant_content', ''))}")
                
                search_result = {
                    "relevant_content": extracted_info.get("relevant_content", ""),
                    "images": extracted_info.get("images", []),
                    "source_document": result.get("filename", ""),
                    "source_url": result.get("source_url", ""),
                    "score": result.get("@search.score", 0.0)
                }
                
                # Add schema info if available
                if metadata.get('has_schema'):
                    search_result['schema_name'] = metadata.get('schema_name')
                
                search_results.append(search_result)
            
            logger.info(f"=== HYBRID SEARCH END ===")
            logger.info(f"Total results after LLM filtering: {len(search_results)}")
            
            # Generate final answer using RAG
            if search_results:
                logger.info("Generating final answer using RAG...")
                final_answer = self._generate_answer_with_rag(query, search_results)
                
                # Replace relevant_content with generated answer in each result
                for result in search_results:
                    result["answer"] = final_answer
                    del result["relevant_content"]  # Remove intermediate data
            
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
        """Use LLM to extract relevant portions from document content
        
        This is the Retrieve step - extracting relevant content from documents.
        The actual answer generation happens in _generate_answer_with_rag.
        
        Args:
            query: User's question
            content: Full document content with image markers (filename.png)
            all_image_urls: List of all image URLs available in the document
            include_images: Whether to include images in the response
            
        Returns:
            Dictionary with 'relevant_content' (text) and 'images' (list of relevant image URLs)
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
            prompt = f"""以下は作業標準書のドキュメントの一部です。ユーザーの質問に関連する情報をドキュメントから抽出してください。

**重要な制約:**
1. ドキュメントに記載されている内容のみを使用してください（推測禁止）
2. 質問に直接関連する文章のみを抽出してください
3. 質問に関連する画像の番号をリストで指定してください（画像番号は0から始まります）
4. ドキュメントに質問の答えが含まれていない場合は、relevant_content を空文字列にしてください

**ユーザーの質問:**
{query}

**ドキュメントの内容:**
{content}

**利用可能な画像一覧:**
{image_context}

**回答形式（JSON）:**
{{
  "relevant_content": "質問に関連する部分をドキュメントから抽出",
  "relevant_image_indices": [0, 2, 5]
}}

ドキュメントに質問の答えが含まれていない場合:
{{
  "relevant_content": "",
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
            relevant_content = parsed.get("relevant_content", "")
            relevant_indices = parsed.get("relevant_image_indices", [])
            
            # Select relevant images based on indices
            selected_images = []
            if include_images and relevant_indices and all_image_urls:
                for idx in relevant_indices:
                    if isinstance(idx, int) and 0 <= idx < len(all_image_urls):
                        selected_images.append(all_image_urls[idx])
            
            logger.info(f"Extracted relevant content length: {len(relevant_content)}, selected {len(selected_images)} images from {len(all_image_urls)} total")
            
            return {
                "relevant_content": relevant_content,
                "images": selected_images
            }
            
        except Exception as e:
            logger.error(f"Error extracting relevant info with LLM: {str(e)}")
            # Fallback: return truncated content and all images
            return {
                "relevant_content": content[:1000] if content else "",
                "images": all_image_urls[:3] if include_images else []
            }
    
    def _generate_answer_with_rag(
        self,
        query: str,
        search_results: List[Dict[str, Any]]
    ) -> str:
        """Generate answer using RAG (Retrieval-Augmented Generation)
        
        Takes the retrieved and extracted information from multiple documents
        and generates a comprehensive answer to the user's question.
        
        Args:
            query: User's question
            search_results: List of search results with relevant_content
            
        Returns:
            Generated answer text
        """
        try:
            # Combine all relevant content from search results
            combined_context = ""
            for idx, result in enumerate(search_results, 1):
                source = result.get("source_document", "Unknown")
                content = result.get("relevant_content", "")
                if content:
                    combined_context += f"\n\n[ドキュメント{idx}: {source}]\n{content}"
            
            if not combined_context.strip():
                return "関連する情報が見つかりませんでした。"
            
            # RAG prompt: Use retrieved context to answer the question
            rag_prompt = f"""以下の作業標準書の情報を使用して、ユーザーの質問に答えてください。

**重要な制約:**
1. 以下のドキュメント情報のみを使用してください
2. 推測や追加情報は含めないでください
3. 質問に直接答える形式で回答してください
4. 複数のドキュメントから情報がある場合は、統合してわかりやすく説明してください
5. 手順や注意事項があれば、リスト形式で説明してください

**ユーザーの質問:**
{query}

**検索されたドキュメント情報:**
{combined_context}

**回答:**
上記の情報をもとに、質問に対する明確で簡潔な回答を生成してください。"""
            
            logger.info(f"Generating RAG answer with {len(search_results)} documents, total context length: {len(combined_context)}")
            
            response = self.openai_client.chat.completions.create(
                model=self.chat_model,
                messages=[
                    {"role": "system", "content": "あなたは作業標準書の専門家です。提供されたドキュメント情報のみを使用して、正確でわかりやすい回答を生成してください。"},
                    {"role": "user", "content": rag_prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            answer = response.choices[0].message.content.strip()
            logger.info(f"Generated RAG answer length: {len(answer)}")
            
            return answer
            
        except Exception as e:
            logger.error(f"Error generating RAG answer: {str(e)}")
            # Fallback: return first result's content
            if search_results:
                return search_results[0].get("relevant_content", "エラーが発生しました。")
            return "回答を生成できませんでした。"
    
    def get_all_documents(self) -> List[Dict[str, Any]]:
        """Get all indexed documents from all indexes (default + schema-based)
        
        Returns list of documents with metadata including:
        - filename
        - schema_id (if applicable)
        - schema_name (if applicable)
        - source_url
        - id
        """
        all_documents = []
        
        # Get documents from default index
        try:
            logger.info(f"Fetching documents from default index: {self.index_name}")
            results = self.search_client.search(
                search_text="*",
                select=["id", "filename", "source_url", "metadata"],
                top=1000  # Reasonable limit
            )
            
            for result in results:
                metadata_str = result.get("metadata", "{}")
                try:
                    metadata = json.loads(metadata_str)
                except:
                    metadata = {}
                
                doc = {
                    "id": result.get("id"),
                    "filename": result.get("filename"),
                    "source_url": result.get("source_url"),
                    "schema_id": None,
                    "schema_name": None,
                    "index_name": self.index_name
                }
                
                # Check if document has schema info in metadata
                if metadata.get("schema_id"):
                    doc["schema_id"] = metadata.get("schema_id")
                    doc["schema_name"] = metadata.get("schema_name")
                
                all_documents.append(doc)
            
            logger.info(f"Found {len(all_documents)} documents in default index")
        except Exception as e:
            logger.error(f"Error fetching documents from default index: {str(e)}")
        
        # Get documents from all schema indexes
        for schema_id, index_name in self.schema_indexes.items():
            try:
                logger.info(f"Fetching documents from schema index: {index_name}")
                schema_client = SearchClient(
                    endpoint=self.search_endpoint,
                    index_name=index_name,
                    credential=self.credential
                )
                
                results = schema_client.search(
                    search_text="*",
                    select=["id", "filename", "source_url", "schema_id", "schema_name"],
                    top=1000
                )
                
                for result in results:
                    doc = {
                        "id": result.get("id"),
                        "filename": result.get("filename"),
                        "source_url": result.get("source_url"),
                        "schema_id": result.get("schema_id", schema_id),
                        "schema_name": result.get("schema_name"),
                        "index_name": index_name
                    }
                    all_documents.append(doc)
                
                logger.info(f"Found {len([d for d in all_documents if d['schema_id'] == schema_id])} documents in schema index {index_name}")
            except Exception as e:
                logger.error(f"Error fetching documents from schema index {index_name}: {str(e)}")
        
        logger.info(f"Total documents found across all indexes: {len(all_documents)}")
        return all_documents
    
    def load_existing_schema_indexes(self):
        """Load all existing schema-based indexes from Azure Search
        
        This method scans all indexes in the search service and identifies
        schema-based indexes by their naming pattern, then registers them.
        """
        try:
            logger.info("Scanning for existing schema-based indexes...")
            all_indexes = self.index_client.list_indexes()
            
            schema_pattern = f"{self.index_name}-schema-"
            
            for index in all_indexes:
                if index.name.startswith(schema_pattern):
                    # Extract schema ID from index name
                    schema_id_part = index.name[len(schema_pattern):]
                    
                    # Try to find the original schema_id
                    # For now, we'll use a simplified approach - register with the extracted ID
                    logger.info(f"Found schema-based index: {index.name}")
                    
                    # Try to get a document from this index to find the schema_id
                    try:
                        schema_client = SearchClient(
                            endpoint=self.search_endpoint,
                            index_name=index.name,
                            credential=self.credential
                        )
                        results = schema_client.search(
                            search_text="*",
                            select=["schema_id"],
                            top=1
                        )
                        
                        for result in results:
                            schema_id = result.get("schema_id")
                            if schema_id:
                                self.schema_indexes[schema_id] = index.name
                                logger.info(f"Registered schema index: schema_id='{schema_id}' -> index_name='{index.name}'")
                            break
                    except Exception as e:
                        logger.warning(f"Could not get schema_id from index {index.name}: {str(e)}")
            
            logger.info(f"Loaded {len(self.schema_indexes)} schema-based indexes")
        except Exception as e:
            logger.error(f"Error loading existing schema indexes: {str(e)}")
