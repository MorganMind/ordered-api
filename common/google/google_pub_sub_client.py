from google.cloud import pubsub_v1
from google.oauth2 import service_account
from django.conf import settings
import base64
import json
import os

class GooglePubSubClient:
    _instance = None
    _publisher = None
    # _subscriber = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GooglePubSubClient, cls).__new__(cls)
            
            # Check if running in Cloud Run (production)
            if hasattr(settings, 'GOOGLE_CLOUD_CREDENTIALS'):
                # Local development: use credentials file
                credentials = service_account.Credentials.from_service_account_file(
                    settings.GOOGLE_CLOUD_CREDENTIALS_PATH
                )
                cls._publisher = pubsub_v1.PublisherClient(
                    credentials=credentials
                )
                # cls._subscriber = pubsub_v1.SubscriberClient(
                #     credentials=credentials
                # )
            # Production: use base64 encoded credentials
            elif os.getenv('GOOGLE_CLOUD_CREDENTIALS_B64'):
                json_credentials = json.loads(
                    base64.b64decode(os.getenv('GOOGLE_CLOUD_CREDENTIALS_B64'))
                )
                credentials = service_account.Credentials.from_service_account_info(
                    json_credentials
                )
                cls._publisher = pubsub_v1.PublisherClient(
                    credentials=credentials
                )
                # cls._subscriber = pubsub_v1.SubscriberClient(
                #     credentials=credentials
                # )
            else:
                raise ValueError("No Google Cloud credentials configured")
                 
        return cls._instance

    @classmethod
    def get_publisher(cls) -> pubsub_v1.PublisherClient:
        """Get the Pub/Sub publisher client instance."""
        if cls._publisher is None:
            GooglePubSubClient()
        return cls._publisher

    # @classmethod
    # def get_subscriber(cls) -> pubsub_v1.SubscriberClient:
    #     """Get the Pub/Sub subscriber client instance."""
    #     if cls._subscriber is None:
    #         GooglePubSubClient()
    #     return cls._subscriber
