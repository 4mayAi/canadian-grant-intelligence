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

    def copy_blob(self, source_blob_name: str, target_blob_name: str) -> bool:
        """Copies a blob from source_blob_name to target_blob_name within the same container."""
        if not self.blob_service_client:
            import logging
            logging.warning("Azure client not active. Skipping Azure copy.")
            return False
            
        try:
            source_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=source_blob_name)
            target_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=target_blob_name)
            
            # Start copy operation
            copy_props = target_client.start_copy_from_url(source_client.url)
            
            # Poll for copy completion
            import time
            props = target_client.get_blob_properties()
            while props.copy.status == "pending":
                time.sleep(0.1)
                props = target_client.get_blob_properties()
                
            if props.copy.status == "success":
                import logging
                logging.info(f"Successfully copied {source_blob_name} to {target_blob_name} in Azure storage.")
                return True
            else:
                raise Exception(f"Copy status returned: {props.copy.status}")
                
        except Exception as e:
            import logging
            logging.warning(f"Fast Azure server-side copy failed, attempting download-and-upload fallback. Error: {e}")
            try:
                data = self.download_json(source_blob_name)
                if data is not None:
                    return self.upload_json(target_blob_name, data)
            except Exception as fallback_err:
                logging.error(f"Fallback download-and-upload copy failed: {fallback_err}")
            return False

    def delete_blob(self, blob_name: str) -> bool:
        """Deletes a blob from the container."""
        if not self.blob_service_client:
            import logging
            logging.warning("Azure client not active. Skipping Azure delete.")
            return False
            
        try:
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
            if blob_client.exists():
                blob_client.delete_blob()
                import logging
                logging.info(f"Successfully deleted blob {blob_name} from container {self.container_name}.")
            else:
                import logging
                logging.info(f"Blob {blob_name} does not exist. Skipping delete.")
            return True
        except Exception as e:
            import logging
            logging.error(f"Failed to delete blob {blob_name} from Azure: {e}")
            return False

azure_client = AzureClient()
