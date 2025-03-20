from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods
from user.services.user_service import complete_onboarding, UserService
from user.models.onboarding_payload import OnboardingPayload
import json

async def get_or_create_user_data_view(request):
    user_data = await UserService.get_or_create_user_data()
    return JsonResponse(user_data.model_dump())

@csrf_exempt
@require_POST
async def complete_onboarding_view(request):

    try:
        data = json.loads(request.body)
        payload = OnboardingPayload(**data)
        
        user_data = await complete_onboarding(payload)
        return JsonResponse(user_data.model_dump())
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
@require_http_methods(["PATCH"])
async def update_user_view(request):
    try:
        data = json.loads(request.body)
        allowed_fields = {
            "first_name", "last_name", "onboarding_completed",
            "avatar_url", "full_name"
        }

        update_data = {
            k: v for k, v in data.items() 
            if k in allowed_fields
        }
        
        updated_user = await UserService.update_user(update_data)
        return JsonResponse(updated_user.to_supabase())
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500) 