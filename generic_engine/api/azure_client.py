import os
import json
import logging
from typing import Any, Optional
from azure.storage.blob import BlobServiceClient, ContentSettings

class AzureClient:
    def __init__(self, container_name: str = "data"):
        self.container_name = container_name
        self.connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        self.blob_service_client = None

        if self.connection_string:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
                # Ensure the container exists
                try:
                    container_client = self.blob_service_client.get_container_client(self.container_name)
                    if not container_client.exists():
                        container_client.create_container(public_access="blob")
                        logging.info(f"Created Azure Container: {self.container_name} with public blob access")
                except Exception as container_err:
                    logging.warning(f"Could not verify or create container {self.container_name}: {container_err}")
                logging.info(f"Initialized Azure Blob Client for container: {container_name}")
            except Exception as e:
                logging.error(f"Failed to initialize BlobServiceClient: {e}")
        else:
            logging.warning("AZURE_STORAGE_CONNECTION_STRING environment variable not set.")

    def upload_json(self, blob_name: str, data: Any) -> bool:
        """Uploads JSON serializable data to Azure Blob Storage."""
        if not self.blob_service_client:
            logging.warning("Azure connection client not active. Skipping Azure upload.")
            return False
            
        try:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
            
            if isinstance(data, (dict, list)):
                json_data = json.dumps(data, ensure_ascii=False, indent=2)
            else:
                json_data = data
                
            content_settings = ContentSettings(content_type='application/json')
            blob_client.upload_blob(json_data, overwrite=True, content_settings=content_settings)
            logging.info(f"Successfully uploaded {blob_name} to Azure container {self.container_name}.")
            return True
        except Exception as e:
            logging.error(f"Failed to upload {blob_name} to Azure: {e}")
            return False

    def download_json(self, blob_name: str) -> Optional[Any]:
        """Downloads a blob from Azure Storage and attempts to parse it as JSON."""
        if not self.blob_service_client:
            logging.warning("Azure client not active. Skipping Azure download.")
            return None
            
        try:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
            
            if not blob_client.exists():
                logging.info(f"Blob {blob_name} does not exist in container {self.container_name}.")
                return None
                
            download_stream = blob_client.download_blob()
            raw_data = download_stream.readall().decode('utf-8')
            return json.loads(raw_data)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON for {blob_name}: {e}")
            return None
        except Exception as e:
            logging.error(f"Failed to download {blob_name} from Azure: {e}")
            return None

    def upload_file(self, file_path: str, blob_name: str, content_type: str = 'image/png') -> bool:
        """Uploads a binary file to Azure Blob Storage."""
        if not self.blob_service_client or not os.path.exists(file_path):
            logging.warning(f"Skipping upload. Client active: {bool(self.blob_service_client)}, File exists: {os.path.exists(file_path)}")
            return False
            
        try:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
            content_settings = ContentSettings(content_type=content_type)
            with open(file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True, content_settings=content_settings)
            logging.info(f"Uploaded binary file {file_path} as {blob_name} to container {self.container_name}.")
            return True
        except Exception as e:
            logging.error(f"Failed to upload file {file_path} to Azure: {e}")
            return False
