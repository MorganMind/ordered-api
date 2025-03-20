from google.cloud import storage
from google.oauth2 import service_account
from django.conf import settings
import base64
import json
import os

class GoogleStorageClient:
    _instance = None
    _storage_client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GoogleStorageClient, cls).__new__(cls)
            
            # Check if running in Cloud Run (production)
            if hasattr(settings, 'GOOGLE_CLOUD_CREDENTIALS'):
                # Local development: use credentials file
                credentials = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_CLOUD_CREDENTIALS_PATH
                )
                cls._storage_client = storage.Client(
                    credentials=credentials,
                    project=settings.GOOGLE_CLOUD_PROJECT
                )
            # Production: use base64 encoded credentials
            elif os.getenv('GOOGLE_CLOUD_CREDENTIALS_B64'):
                json_credentials = json.loads(
                    base64.b64decode(os.getenv('GOOGLE_CLOUD_CREDENTIALS_B64'))
                )
                credentials = service_account.Credentials.from_service_account_info(
                    json_credentials
                )
                cls._storage_client = storage.Client(
                    credentials=credentials,
                    project=credentials.project_id
                )
            else:
                raise ValueError("No Google Cloud credentials configured")
                 
        return cls._instance

    @classmethod
    def get_client(cls) -> storage.Client:
        if cls._storage_client is None:
            GoogleStorageClient() 
        return cls._storage_client

    @classmethod
    async def generate_upload_signed_url(
        cls,
        bucket_name: str,
        blob_name: str,
        content_type: str,
        expiration: int = 300  # 5 minutes
    ) -> str:
        """Generate a signed URL for uploading a file to Google Cloud Storage"""
        storage_client = cls.get_client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=expiration,
            method="PUT",
            content_type=content_type,
        )
        
        return url 