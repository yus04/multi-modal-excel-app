import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional
from app.models import ExcelSchema, FieldDefinition, SchemaCreateRequest

logger = logging.getLogger(__name__)


class SchemaService:
    """Service for managing Excel schemas"""
    
    def __init__(self):
        # In-memory storage (for production, use database)
        self.schemas: Dict[str, ExcelSchema] = {}
        logger.info("SchemaService initialized")
    
    def create_schema(self, request: SchemaCreateRequest) -> ExcelSchema:
        """Create a new schema"""
        schema_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()
        
        schema = ExcelSchema(
            id=schema_id,
            name=request.name,
            description=request.description,
            fields=request.fields,
            created_at=now,
            updated_at=now
        )
        
        self.schemas[schema_id] = schema
        logger.info(f"Created schema: {schema_id} - {request.name}")
        return schema
    
    def get_schema(self, schema_id: str) -> Optional[ExcelSchema]:
        """Get a schema by ID"""
        return self.schemas.get(schema_id)
    
    def list_schemas(self) -> List[ExcelSchema]:
        """List all schemas"""
        return list(self.schemas.values())
    
    def update_schema(self, schema_id: str, request: SchemaCreateRequest) -> Optional[ExcelSchema]:
        """Update an existing schema"""
        if schema_id not in self.schemas:
            return None
        
        now = datetime.utcnow().isoformat()
        schema = self.schemas[schema_id]
        schema.name = request.name
        schema.description = request.description
        schema.fields = request.fields
        schema.updated_at = now
        
        logger.info(f"Updated schema: {schema_id}")
        return schema
    
    def delete_schema(self, schema_id: str) -> bool:
        """Delete a schema"""
        if schema_id in self.schemas:
            del self.schemas[schema_id]
            logger.info(f"Deleted schema: {schema_id}")
            return True
        return False
