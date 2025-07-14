from collections import defaultdict
from typing import Callable, Dict, List

class DomainEventManager:
    """Simple in-memory event dispatcher"""

    _subscribers: Dict[str, List[Callable]] = defaultdict(list)

    @staticmethod
    def emit(event_type: str, payload: dict):
        """Emit a domain event, notifying all subscribers"""
        for handler in DomainEventManager._subscribers[event_type]:
            handler(payload)  # Call the subscriber function

    @staticmethod
    def subscribe(event_type: str, handler: Callable):
        """Subscribe a handler function to an event"""
        DomainEventManager._subscribers[event_type].append(handler)
