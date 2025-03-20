from common.google.google_storage_client import GoogleStorageClient
from uuid import uuid4
from datetime import datetime
from typing import Dict
from django.conf import settings
from common.logger.logger_service import get_logger
import os
import tempfile
from typing import Tuple

class FileService:
    @staticmethod
    async def generate_file_upload_url(
        file_name: str,
        content_type: str,
        folder: str = "system/uploads/files"
    ) -> Dict[str, str]:
        """Generate a signed URL for file upload"""
        # Generate a unique blob name
        extension = file_name.split('.')[-1] if '.' in file_name else ''
        blob_name = f"{folder}/{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid4()}"
        if extension:
            blob_name += f".{extension}"
        
        # Generate signed URL
        upload_url = await GoogleStorageClient.generate_upload_signed_url(
            bucket_name=settings.GOOGLE_CLOUD_STORAGE_BUCKET,
            blob_name=blob_name,
            content_type=content_type
        )
         
        return {
            "upload_url": upload_url,
            "blob_name": blob_name,
            "file_type": extension,
            "content_type": content_type
        }

    @staticmethod
    async def generate_image_upload_url(
        file_name: str,
        content_type: str,
        folder: str = "system/uploads/images"
    ) -> Dict[str, str]:
        """Generate a signed URL for image upload"""
        # Generate a unique blob name
        extension = file_name.split('.')[-1] if '.' in file_name else ''
        blob_name = f"{folder}/{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid4()}"
        if extension:
            blob_name += f".{extension}"

        # Generate signed URL
        upload_url = await GoogleStorageClient.generate_upload_signed_url(
            bucket_name=settings.GOOGLE_CLOUD_STORAGE_BUCKET,
            blob_name=blob_name,
            content_type=content_type
        )

        return {
            "upload_url": upload_url,
            "blob_name": blob_name,
            "file_type": extension,
            "content_type": content_type
        }
    
    @staticmethod
    async def delete_file(file_path: str) -> None:
        """Delete a file from Google Cloud Storage"""
        try:
            storage_client = GoogleStorageClient.get_client()
            bucket = storage_client.bucket(settings.GOOGLE_CLOUD_STORAGE_BUCKET)
            blob = bucket.blob(file_path)
            blob.delete()
        except Exception as e:
            # Log error but don't raise - this is a background task
            print(f"Error deleting file {file_path}: {str(e)}")

    @staticmethod
    async def generate_download_url(file_path: str, expiration: int = 3600) -> str:
        """Generate a signed URL for downloading a file"""
        storage_client = GoogleStorageClient.get_client()
        bucket = storage_client.bucket(settings.GOOGLE_CLOUD_STORAGE_BUCKET)
        blob = bucket.blob(file_path)
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=expiration,
            method="GET"
        )
        
        return url 
    
    @staticmethod
    async def download_file(blob_name: str) -> str:
        """
        Downloads a file from GCS to a temporary location
        Returns: Tuple[temp_file_path, content_type]
        """
        logger = get_logger()
        storage_client = GoogleStorageClient.get_client()
        bucket = storage_client.bucket(settings.GOOGLE_CLOUD_STORAGE_BUCKET)
        
        try:
            # Create temp directory if it doesn't exist
            temp_dir = tempfile.gettempdir()
            temp_file_path = os.path.join(temp_dir, os.path.basename(blob_name))
            
            logger.info("Starting file download", extra={
                "blob_name": blob_name,
                "temp_path": temp_file_path
            })
            
            # Get blob  
            blob = bucket.blob(blob_name)
            
            # Download
            blob.download_to_filename(temp_file_path)
            
            logger.info("File download complete", extra={
                "blob_name": blob_name,
                "file_size": os.path.getsize(temp_file_path),
                "content_type": blob.content_type
            })
            
            return temp_file_path
            
        except Exception as e:
            logger.error("File download failed", extra={
                "blob_name": blob_name,
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise
            
    @staticmethod
    async def cleanup_temp_file(file_path: str):
        """Remove temporary file after processing"""
        logger = get_logger()
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info("Temporary file cleaned up", extra={
                    "file_path": file_path
                })
        except Exception as e:
            logger.error("Failed to cleanup temp file", extra={
                "file_path": file_path,
                "error": str(e)
            }) 