# from common.events.domain_event_manager import DomainEventManager
# from content.events.source_created_event import SourceCreated
# from knowledgebase.tasks.ingestion_task_queue import IngestionTaskQueue, IngestionPayload
# from common.logger.logger_service import get_logger

# logger = get_logger()

# def handle_source_created(payload: SourceCreated):
#     try:
#         # Trigger the ingestion process
#         ingestion_task_queue = IngestionTaskQueue()
#         ingestion_task_queue.create_source_ingestion_task(
#             payload=IngestionPayload(
#                 source_id=payload["source_id"]
#             )
#         )
#     except Exception as e:
#         logger.error(f"Error creating ingestion task: {str(e)}")
