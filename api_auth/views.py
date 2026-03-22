"""
GET /api/v1/auth/me — current user from Supabase JWT (Bearer).

Kept out of user.urls + create_protected_urls so paths starting with `auth/`
are not treated as anonymous-by-prefix.
"""

from asgiref.sync import sync_to_async
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api_auth.me_response import build_auth_me_response
from common.decorators import auth_required


@csrf_exempt
@require_http_methods(["GET", "HEAD"])
@auth_required(allow_anonymous=False)
async def auth_me_view(request):
    """200 JSON for Supabase/JWT session — shape matches frontend mapMeResponseFromApi."""
    # build_auth_me_response may hit Django ORM (tenants.Tenant); async views must not call ORM directly.
    payload = await sync_to_async(build_auth_me_response, thread_sensitive=True)(request)
    return JsonResponse(payload)
