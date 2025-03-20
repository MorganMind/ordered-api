from django.conf import settings

# Get environment mode
ENV_SUFFIX = "-dev" if settings.ENV == "development" else ""

PUBSUB_CONFIG = {
    'TOPICS': {
        'INGEST_SOURCE': f'ingest-source-topic{ENV_SUFFIX}',
        'DELETE_SOURCE': f'delete-source-topic{ENV_SUFFIX}',
        # Add other topics as needed
    }
} 