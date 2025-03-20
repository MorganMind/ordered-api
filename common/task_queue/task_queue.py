from typing import Optional, Dict, Any
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2
from django.conf import settings
from common.logger.logger_service import get_logger
from datetime import datetime, timedelta
import json
from common.google.google_tasks_client import GoogleTasksClient

logger = get_logger()

class BaseTaskQueue:
    """Base class for Cloud Tasks queue implementations."""
    
    def __init__(
            self,  
            queue_name: str,
        ):
        """Initialize the base task queue with configuration."""
        self.client = GoogleTasksClient.get_client()  # Use the singleton client
        self.project_id = settings.GOOGLE_CLOUD_PROJECT
        self.location = settings.GOOGLE_CLOUD_LOCATION 
        self.service_account_email = settings.GOOGLE_SERVICE_ACCOUNT
        self.base_url = settings.GOOGLE_CLOUD_RUN_URL
        self.queue_name = queue_name 
       
    def _get_queue_path(self) -> str:
        """Get the full queue path."""
        return self.client.queue_path(self.project_id, self.location, self.queue_name)

    def _create_base_task(
        self,
        url_path: str,
        payload: Dict[str, Any],
        delay_seconds: Optional[int] = None,
        task_name: Optional[str] = None,
    ) -> tasks_v2.Task:
        """Create the base task configuration.""" 
        full_url = f"{self.base_url.rstrip('/')}/{url_path.lstrip('/')}"
       
        task = {
            'http_request': {
                'http_method': tasks_v2.HttpMethod.POST,
                'url': full_url,
                'oidc_token': {
                    'service_account_email': self.service_account_email,
                    'audience': f"{self.base_url}/"  # Make sure this matches your Cloud Run service URL
                },
                'headers': {
                    'Content-Type': 'application/json',
                },
                'body': json.dumps(payload).encode()
            }
        }
        print(task, self.project_id, self.service_account_email)
        if task_name:
            task['name'] = self.client.task_path(
                self.project_id, self.location, self.queue_name, task_name
            )

        if delay_seconds:
            timestamp = timestamp_pb2.Timestamp()
            timestamp.FromDatetime(
                datetime.utcnow() + timedelta(seconds=delay_seconds)
            )
            task['schedule_time'] = timestamp
        
        return task

    def create_task(
        self,
        url_path: str,
        payload: Dict[str, Any],
        delay_seconds: Optional[int] = None,
        task_name: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> str:
        """Create and enqueue a task."""
        try:
            task = self._create_base_task(url_path, payload, delay_seconds, task_name)
            
            response = self.client.create_task(
                request={'parent': self._get_queue_path(), 'task': task}
            )
            logger.info(f"Created task {response.name} in queue {self.queue_name}")
            return response.name
        except Exception as e:
            logger.error(f"Failed to create task: {str(e)}")
            raise CloudTasksException(f"Failed to create task: {str(e)}")

class CloudTasksException(Exception):
    """Custom exception for Cloud Tasks errors."""
    pass