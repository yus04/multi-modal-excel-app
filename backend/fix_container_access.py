"""
Fix Blob Storage container access level to allow public read access
"""
import os
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient, PublicAccess

# Load environment variables
load_dotenv()

connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
container_name = os.getenv("AZURE_STORAGE_CONTAINER_NAME", "content")

if not connection_string:
    print("Error: AZURE_STORAGE_CONNECTION_STRING not found in environment")
    exit(1)

# Connect to Blob Storage
blob_service_client = BlobServiceClient.from_connection_string(connection_string)

try:
    # Get container client
    container_client = blob_service_client.get_container_client(container_name)
    
    # Set public access level to Blob
    container_client.set_container_access_policy(
        signed_identifiers={},
        public_access=PublicAccess.Blob
    )
    
    print(f"✓ Successfully set container '{container_name}' to Blob (public read) access")
    print(f"  Images and files in this container are now publicly accessible")
    
except Exception as e:
    print(f"✗ Error setting container access: {str(e)}")
    exit(1)
