from django.http import JsonResponse
from django.views.decorators.http import require_GET
from user.services.analytics_service import AnalyticsService
from common.supabase.supabase_client import get_current_user

@require_GET
async def get_user_analytics_view(request):
    """Get analytics data for the currently authenticated user"""
    user = get_current_user()
    analytics = await AnalyticsService.get_user_analytics(user["id"])
    return JsonResponse(analytics.model_dump()) 