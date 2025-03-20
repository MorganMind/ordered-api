from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from ..services.user_settings_service import UserSettingsService
from common.decorators import auth_required

@csrf_exempt
@require_http_methods(["GET"])
async def get_user_settings(request):
    """Get current user's settings"""
    try:
        settings = await UserSettingsService.get_or_create_user_settings()
        print("settings", settings)
        return JsonResponse(settings.dict())
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
@require_http_methods(["PATCH"])
async def update_user_settings(request):
    """Update user settings"""
    try:
        update_data = json.loads(request.body)
        settings = await UserSettingsService.update_user_settings(update_data)
        return JsonResponse(settings.dict())
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)