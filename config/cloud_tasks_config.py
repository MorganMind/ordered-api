CLOUD_TASKS_CONFIG = {
    'DEFAULT_QUEUE': 'default',
    'SERVICE_ACCOUNT_EMAIL': 'matterseek@matterseek-staging.iam.gserviceaccount.com',  
    'RETRY_CONFIG': {
        'max_attempts': 5,
        'min_backoff_seconds': 1,
        'max_backoff_seconds': 300
    }
} 