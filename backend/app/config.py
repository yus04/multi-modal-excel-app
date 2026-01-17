from pydantic_settings import BaseSettings
from typing import List, Optional


class Settings(BaseSettings):
    # Azure OpenAI Configuration
    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_deployment_name: str = "gpt-4o"
    azure_openai_api_version: str = "2024-02-15-preview"
    
    # Azure AI Search Configuration
    azure_search_endpoint: str
    azure_search_api_key: str
    azure_search_index_name: str = "excel-procedures-index"
    
    # Azure Blob Storage Configuration
    azure_storage_connection_string: str
    azure_storage_container_name: str = "excel-files"
    
    # Azure Document Intelligence Configuration (Optional)
    azure_document_intelligence_endpoint: Optional[str] = None
    azure_document_intelligence_api_key: Optional[str] = None
    
    # Application Configuration
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"
    
    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
