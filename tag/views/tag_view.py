from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
from ..services.tag_service import TagService
from ..models.taggable_type import TaggableType
from common.auth_routes import create_protected_urls

@csrf_exempt
@require_http_methods(["POST"])
async def create_tag_view(request):
    try:
        data = json.loads(request.body)
        label = data.get("label")
        props = data.get("props", {})
        
        if not label:
            return JsonResponse({"error": "Label is required"}, status=400)
            
        tag = await TagService.create_tag(label, props)
        return JsonResponse(tag.to_supabase())
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
async def create_tagging_view(request):
    try:
        data = json.loads(request.body)
        tag_id = data.get("tag_id")
        taggable_id = data.get("taggable_id")
        taggable_type = data.get("taggable_type")
        
        if not all([tag_id, taggable_id, taggable_type]):
            return JsonResponse({"error": "Missing required fields"}, status=400)
            
        tagging = await TagService.create_tagging(
            tag_id,
            taggable_id,
            TaggableType.from_string(taggable_type)
        )
        return JsonResponse(tagging.to_supabase())
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
@require_http_methods(["DELETE"])
async def remove_tagging_view(request):
    try:
        data = json.loads(request.body)
        tag_id = data.get("tag_id")
        taggable_id = data.get("taggable_id")
        
        if not all([tag_id, taggable_id]):
            return JsonResponse({"error": "Missing required fields"}, status=400)
            
        await TagService.remove_tagging(tag_id, taggable_id)
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@require_http_methods(["GET"])
async def get_user_tags_view(request):
    try:
        tags = await TagService.get_user_tags()
        return JsonResponse({"tags": [tag.to_supabase() for tag in tags]})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@require_http_methods(["GET"])
async def get_taggings_for_item_view(request, taggable_type: str, taggable_id: str):
    try:
        tags = await TagService.get_taggings_for_item(
            taggable_id,
            TaggableType.from_string(taggable_type)
        )
        return JsonResponse({"tags": [tag.to_supabase() for tag in tags]})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@require_http_methods(["POST"])
async def get_item_ids_for_tags_view(request):
    try:
        data = json.loads(request.body)
        tag_ids = data.get("tag_ids", [])
        type_filters = data.get("type_filters", [])
        
        if not tag_ids:
            return JsonResponse({"item_ids": []})
            
        tags = [await TagService.get_tag(tag_id) for tag_id in tag_ids]
        type_filters = [TaggableType.from_string(t) for t in type_filters]
        
        item_ids = await TagService.get_item_ids_for_tags(tags, type_filters)
        return JsonResponse({"item_ids": item_ids})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)