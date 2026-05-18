import os
import json
from typing import Any, Optional, Dict
from azure.storage.blob import BlobServiceClient, ContentSettings

class AzureClient:
    def __init__(self, container_name: str = "data"):
        self.container_name = container_name
        self.connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.blob_service_client = None

        if self.connection_string:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
            except Exception as e:
                import logging
                logging.error(f"Failed to initialize BlobServiceClient: {e}")

    def upload_json(self, blob_name: str, data: Any) -> bool:
        """Uploads JSON serializable data to Azure Blob Storage."""
        if not self.blob_service_client:
            import logging
            logging.warning("Azure connection string not found. Skipping Azure upload.")
            return False
            
        try:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
            
            if isinstance(data, (dict, list)):
                json_data = json.dumps(data, ensure_ascii=False, indent=2)
            else:
                json_data = data
                
            content_settings = ContentSettings(content_type='application/json')
            
            blob_client.upload_blob(json_data, overwrite=True, content_settings=content_settings)
            return True
        except Exception as e:
            import logging
            logging.error(f"Failed to upload to Azure: {e}")
            return False

    def download_json(self, blob_name: str) -> Optional[Any]:
        """Downloads a blob from Azure Storage and attempts to parse it as JSON."""
        if not self.blob_service_client:
            return None
            
        try:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
            
            if not blob_client.exists():
                return None
                
            download_stream = blob_client.download_blob()
            raw_data = download_stream.readall().decode('utf-8')
            return json.loads(raw_data)
        except json.JSONDecodeError as e:
            import logging
            logging.error(f"Failed to parse JSON for {blob_name}: {e}")
            return None
        except Exception as e:
            import logging
            logging.error(f"Failed to download {blob_name} from Azure: {e}")
            return None

    def upload_file(self, file_path: str, blob_name: str, content_type: str = 'image/png') -> bool:
        """Uploads a binary file to Azure Blob Storage."""
        if not self.blob_service_client or not os.path.exists(file_path):
            return False
            
        try:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
            content_settings = ContentSettings(content_type=content_type)
            with open(file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True, content_settings=content_settings)
            return True
        except Exception as e:
            import logging
            logging.error(f"Failed to upload file {file_path} to Azure: {e}")
            return False

azure_client = AzureClient()
