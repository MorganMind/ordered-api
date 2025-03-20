# from django.http import HttpResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.views.decorators.http import require_POST
# from common.decorators import pubsub_handler 
# from knowledgebase.services.knowledgebase_source_manager import KnowledgebaseSourceManager
# from knowledgebase.tasks.ingestion_task_queue import IngestionPayload
# from knowledgebase.tasks.deletion_task_queue import DeletionPayload
# from common.logger.logger_service import get_logger
# from content.services.content_service_admin import ContentServiceAdmin
# from files.services.file_service import FileService
# import asyncio

# logger = get_logger()

# @csrf_exempt
# @require_POST
# @pubsub_handler
# async def handle_source_ingestion(request):
#     """Handle incoming Pub/Sub messages for source ingestion."""
#     try:
#         # Access the parsed data directly
#         payload: IngestionPayload = request.pubsub_data

#         # Get the source from the database
#         source = await ContentServiceAdmin.get_source(payload["source_id"])  
        
#         logger.info(f"Source ingestion started: {source}")

#         # Process the ingestion using domain service
#         await KnowledgebaseSourceManager.ingest_source(
#             source=source
#         )
        
#         # Acknowledge successful processing
#         return HttpResponse(status=204)
            
#     except Exception as e:
#         logger.error(f"Failed to process source ingestion: {str(e)}")
#         # Return 500 to trigger Pub/Sub retry
#         return HttpResponse(status=500)

# @csrf_exempt
# @require_POST
# @pubsub_handler
# async def handle_source_deletion(request):
#     """Handle incoming Pub/Sub messages for source deletion."""
#     try:
#         # Access the parsed data directly
#         payload: DeletionPayload = request.pubsub_data 
        
#         logger.info(f"Source deletion started: {payload}")

#         try:
#             # Delete the file
#             await FileService.delete_file(payload["file_url"])
#         except Exception as e:
#             logger.error(f"Failed to delete file: {str(e)}")
        
#         try:
#             # Process the deletion using domain service
#             await KnowledgebaseSourceManager.delete_source(
#                 source_id=payload["source_id"],
#                 video_id=payload["video_id"],
#                 user_id=payload["user_id"]
#             )
#         except Exception as e:
#             logger.error(f"Failed to delete source video: {str(e)}")
        
#         # Acknowledge successful processing
#         return HttpResponse(status=204) 
            
#     except Exception as e:
#         logger.error(f"Failed to process source deletion: {str(e)}")
#         # Return 500 to trigger Pub/Sub retry
#         return HttpResponse(status=500)