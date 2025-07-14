from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from ..services.file_service import FileService
from common.supabase.supabase_client import get_current_user
import json

@csrf_exempt
@require_http_methods(["POST"])
async def generate_file_upload_url_view(request):
    """Generate a signed URL for file upload"""
    try:
        data = json.loads(request.body)
        file_name = data.get("file_name")
        content_type = data.get("content_type")

        if not file_name or not content_type:
            return JsonResponse({
                "error": "file_name and content_type are required"
            }, status=400)
        
        user = get_current_user()
        
        result = await FileService.generate_file_upload_url(
            file_name=file_name,
            content_type=content_type,
            folder=f"users/{user['id']}/uploads/files"
        )
        
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
@require_http_methods(["POST"])
async def generate_image_upload_url_view(request):
    """Generate a signed URL for image upload"""
    try:
        data = json.loads(request.body)
        file_name = data.get("file_name")
        content_type = data.get("content_type")

        if not file_name or not content_type:
            return JsonResponse({
                "error": "file_name and content_type are required"
            }, status=400)

        # Validate content type for images
        if not content_type.startswith('image/'):
            return JsonResponse({
                "error": "Content type must be an image format"
            }, status=400)
        
        user = get_current_user()

        result = await FileService.generate_image_upload_url(
            file_name=file_name,
            content_type=content_type,
            folder=f"users/{user['id']}/uploads/images"
        )
        
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400) 