# from typing import Dict, Any, Optional
# from dataclasses import dataclass
# from common.task_queue.task_queue import BaseTaskQueue

# @dataclass
# class DeletionPayload:
#     source_id: str
#     file_url: str
#     user_id: str
#     video_id: str

# class DeletionTaskQueue(BaseTaskQueue):
#     def __init__(self):
#         super().__init__(queue_name="delete-content-queue")

#     def create_source_deletion_task(
#         self, 
#         payload: DeletionPayload,
#         delay_seconds: Optional[int] = None,
#         task_name: Optional[str] = None
#     ):
#         """Create a source deletion task"""
#         task_payload = {
#             "source_id": payload.source_id,
#             "file_url": payload.file_url,
#             "user_id": payload.user_id,
#             "video_id": payload.video_id
#         }

#         return self.create_task(
#             url_path="tasks/create/handle-delete-source",
#             payload=task_payload,
#             delay_seconds=delay_seconds,
#             task_name=task_name
#         ) 