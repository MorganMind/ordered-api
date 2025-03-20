# from typing import Dict, Any, Optional
# from dataclasses import dataclass
# from common.task_queue.task_queue import BaseTaskQueue

# @dataclass
# class IngestionPayload:
#     source_id: str

# class IngestionTaskQueue(BaseTaskQueue):
#     """Specialized task queue for data ingestion tasks."""
    
#     def __init__(self):
#         super().__init__(queue_name="ingest-content-queue")

#     def create_source_ingestion_task(
#         self,
#         payload: IngestionPayload,
#         delay_seconds: Optional[int] = None,
#         task_name: Optional[str] = None
#     ) -> str:
#         """Create an ingestion task with typed payload."""
#         task_payload = {
#             "source_id": payload.source_id
#         }
        
#         return self.create_task(
#             url_path="tasks/create/handle-ingest-source",
#             payload=task_payload,
#             delay_seconds=delay_seconds,
#             task_name=task_name
#         ) 