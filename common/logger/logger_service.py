from contextvars import ContextVar
from typing import Optional
import logfire
from django.conf import settings

# Context variable for logger
logger: ContextVar[Optional[object]] = ContextVar('logger', default=None)

def get_logger():
    """Get or initialize logger instance"""
    current_logger = logger.get()
    if current_logger is not None:
        return current_logger
    
    # Initialize new logger (local/dev: no token → console-only, no Logfire cloud auth)
    token = getattr(settings, "LOGFIRE_TOKEN", None)
    if token:
        logfire.configure(token=token)
    else:
        logfire.configure(send_to_logfire=False)
    logger.set(logfire)
    return logfire

def set_logger(log_instance: object):
    """Set logger instance in current context"""
    logger.set(log_instance) 