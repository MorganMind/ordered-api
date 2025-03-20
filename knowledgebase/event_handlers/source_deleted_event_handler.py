# from content.events.source_deleted import SourceDeleted
# from knowledgebase.tasks.deletion_task_queue import DeletionTaskQueue, DeletionPayload
# from common.logger.logger_service import get_logger

# logger = get_logger()

# def handle_source_deleted(payload: SourceDeleted):
#     try:
#         # Trigger the deletion process
#         deletion_task_queue = DeletionTaskQueue()
#         deletion_task_queue.create_source_deletion_task(
#             payload=DeletionPayload(
#                 source_id=payload["source_id"],
#                 file_url=payload["file_url"],
#                 user_id=payload["user_id"]
#             )
#         )
#     except Exception as e:
#         logger.error(f"Error creating deletion task: {str(e)}")
