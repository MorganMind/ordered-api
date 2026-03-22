import json

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from common.decorators import cloud_task_handler
from common.logger.logger_service import get_logger

logger = get_logger()


@csrf_exempt
@cloud_task_handler
async def handle_ingest_source(request, payload):
    """
    Cloud Tasks → Pub/Sub (ingest). Requires ``google-cloud-pubsub`` and config.
    """
    try:
        from common.google.google_pub_sub_client import GooglePubSubClient
        from config.pubsub_config import PUBSUB_CONFIG
    except ImportError as e:
        logger.warning("task_ingest_pubsub_unavailable", error=str(e))
        return HttpResponse(
            "Pub/Sub dependencies not installed",
            status=503,
            content_type="text/plain",
        )

    try:
        publisher = GooglePubSubClient.get_publisher()
        topic_id = PUBSUB_CONFIG["TOPICS"]["INGEST_SOURCE"]
        topic_path = f"projects/{settings.GOOGLE_CLOUD_PROJECT}/topics/{topic_id}"
        payload_bytes = json.dumps(payload).encode("utf-8")
        publish_future = publisher.publish(topic_path, data=payload_bytes)
        message_id = publish_future.result()
        logger.info("task_ingest_published", message_id=message_id, topic_path=topic_path)
        return HttpResponse(status=200)
    except Exception as e:
        logger.error("task_ingest_failed", error=str(e))
        return HttpResponse(status=500)


@csrf_exempt
@cloud_task_handler
async def handle_delete_source(request, payload):
    try:
        from common.google.google_pub_sub_client import GooglePubSubClient
        from config.pubsub_config import PUBSUB_CONFIG
    except ImportError as e:
        logger.warning("task_delete_pubsub_unavailable", error=str(e))
        return HttpResponse(
            "Pub/Sub dependencies not installed",
            status=503,
            content_type="text/plain",
        )

    try:
        publisher = GooglePubSubClient.get_publisher()
        topic_id = PUBSUB_CONFIG["TOPICS"]["DELETE_SOURCE"]
        topic_path = f"projects/{settings.GOOGLE_CLOUD_PROJECT}/topics/{topic_id}"
        payload_bytes = json.dumps(payload).encode("utf-8")
        publish_future = publisher.publish(topic_path, data=payload_bytes)
        message_id = publish_future.result()
        logger.info("task_delete_published", message_id=message_id, topic_path=topic_path)
        return HttpResponse(status=200)
    except Exception as e:
        logger.error("task_delete_failed", error=str(e))
        return HttpResponse(status=500)
