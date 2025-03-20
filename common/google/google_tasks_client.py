from google.cloud import tasks_v2
from google.oauth2 import service_account
from django.conf import settings
import base64
import json
import os

class GoogleTasksClient:
    _instance = None
    _tasks_client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GoogleTasksClient, cls).__new__(cls)
            
            # Check if running in Cloud Run (production)
            if hasattr(settings, 'GOOGLE_CLOUD_CREDENTIALS'):
                # Local development: use credentials file
                credentials = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_CLOUD_CREDENTIALS_PATH
                )
                cls._tasks_client = tasks_v2.CloudTasksClient(
                    credentials=credentials
                )
            # Production: use base64 encoded credentials
            elif os.getenv('GOOGLE_CLOUD_CREDENTIALS_B64'):
                json_credentials = json.loads(
                    base64.b64decode(os.getenv('GOOGLE_CLOUD_CREDENTIALS_B64'))
                )
                credentials = service_account.Credentials.from_service_account_info(
                    json_credentials
                )
                cls._tasks_client = tasks_v2.CloudTasksClient(
                    credentials=credentials
                )
            else:
                raise ValueError("No Google Cloud credentials configured")
                 
        return cls._instance

    @classmethod
    def get_client(cls) -> tasks_v2.CloudTasksClient:
        """Get the Cloud Tasks client instance."""
        if cls._tasks_client is None:
            GoogleTasksClient()
        return cls._tasks_client
