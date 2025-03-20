from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from common.decorators import cloud_task_handler
from common.google.google_pub_sub_client import GooglePubSubClient
from django.conf import settings
from config.pubsub_config import PUBSUB_CONFIG
import json
from common.logger.logger_service import get_logger
from common.auth_routes import auth_required
logger = get_logger()

@csrf_exempt
@cloud_task_handler
async def handle_ingest_source(request, payload):
    """
    Handle ingest source tasks from Cloud Tasks and publish to Pub/Sub.
    
    The @cloud_task_handler decorator:
    - Verifies the request is from Cloud Tasks
    - Handles error responses
    - Parses the payload
    """
    try:
        publisher = GooglePubSubClient.get_publisher()
        
        # Construct the full topic path
        topic_id = PUBSUB_CONFIG['TOPICS']['INGEST_SOURCE']
        topic_path = f"projects/{settings.GOOGLE_CLOUD_PROJECT}/topics/{topic_id}"

        # Convert payload to bytes
        payload_bytes = json.dumps(payload).encode("utf-8")

        # Publish to Pub/Sub
        publish_future = publisher.publish(
            topic_path,
            data=payload_bytes,
        )
        
        # Wait for message to be published
        message_id = publish_future.result()
        logger.info(f"Published message {message_id} to {topic_path}")

        # Return 200 to acknowledge successful processing
        return HttpResponse(status=200)

    except Exception as e:
        logger.error(f"Failed to process task: {str(e)}")
        # Return 500 to trigger Cloud Tasks retry
        return HttpResponse(status=500) 
    
@csrf_exempt
@cloud_task_handler
async def handle_delete_source(request, payload):
    """
    Handle delete source tasks from Cloud Tasks and publish to Pub/Sub.
    """
    try:
        publisher = GooglePubSubClient.get_publisher()
        
        # Construct the full topic path
        topic_id = PUBSUB_CONFIG['TOPICS']['DELETE_SOURCE']
        topic_path = f"projects/{settings.GOOGLE_CLOUD_PROJECT}/topics/{topic_id}"
            
        # Convert payload to bytes
        payload_bytes = json.dumps(payload).encode("utf-8")

        # Publish to Pub/Sub
        publish_future = publisher.publish(
            topic_path,
            data=payload_bytes,
        )

        # Wait for message to be published
        message_id = publish_future.result()
        logger.info(f"Published message {message_id} to {topic_path}")

        # Return 200 to acknowledge successful processing
        return HttpResponse(status=200)

    except Exception as e:
        logger.error(f"Failed to process task: {str(e)}")
        # Return 500 to trigger Cloud Tasks retry
        return HttpResponse(status=500) 


