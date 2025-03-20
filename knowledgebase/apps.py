# from django.apps import AppConfig

# class KnowledgebaseConfig(AppConfig):
#     name = 'knowledgebase'

#     def ready(self):
#         """This runs when Django starts—perfect for registering event listeners."""
#         from common.events.domain_event_manager import DomainEventManager
#         from knowledgebase.event_handlers.source_created_event_handler import handle_source_created
#         from knowledgebase.event_handlers.source_deleted_event_handler import handle_source_deleted

#         # 🔹 Subscribe to domain events
#         DomainEventManager.subscribe("SourceCreated", handle_source_created)
#         DomainEventManager.subscribe("SourceDeleted", handle_source_deleted)
