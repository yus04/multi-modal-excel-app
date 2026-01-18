import io
import base64
from typing import List, Dict, Any, Optional
from azure.storage.blob import BlobServiceClient, ContentSettings, PublicAccess
from azure.core.exceptions import ResourceNotFoundError
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class BlobStorageService:
    def __init__(self, connection_string: str, container_name: str):
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_name = container_name
        self._ensure_container_exists()
    
    def _ensure_container_exists(self):
        """Create container if it doesn't exist"""
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            container_client.get_container_properties()
        except ResourceNotFoundError:
            logger.info(f"Creating container: {self.container_name}")
            self.blob_service_client.create_container(
                self.container_name,
                public_access=PublicAccess.Blob
            )
    
    def upload_file(self, file_content: bytes, filename: str, content_type: str = "application/octet-stream") -> str:
        """Upload a file to blob storage"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=filename
            )
            
            content_settings = ContentSettings(content_type=content_type)
            blob_client.upload_blob(
                file_content,
                overwrite=True,
                content_settings=content_settings
            )
            
            return blob_client.url
        except Exception as e:
            logger.error(f"Error uploading file {filename}: {str(e)}")
            raise
    
    def upload_image(self, image_data: bytes, filename: str) -> str:
        """Upload an image to blob storage"""
        return self.upload_file(image_data, filename, content_type="image/png")
    
    def get_file_url(self, filename: str) -> str:
        """Get the URL for a file in blob storage"""
        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=filename
        )
        return blob_client.url
    
    def download_file(self, filename: str) -> bytes:
        """Download a file from blob storage"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=filename
            )
            return blob_client.download_blob().readall()
        except ResourceNotFoundError:
            logger.error(f"File not found: {filename}")
            raise
    
    def file_exists(self, filename: str) -> bool:
        """Check if a file exists in blob storage"""
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=filename
            )
            blob_client.get_blob_properties()
            return True
        except ResourceNotFoundError:
            return False
