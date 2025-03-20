from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from common.decorators import auth_required
from ..services.invite_service import InviteService
import json

@csrf_exempt
@require_POST
async def create_invite_view(request):
    """Create a new invite"""
    try:
        data = json.loads(request.body)
        name = data.get("name")
        email = data.get("email")
        
        if not email:
            return JsonResponse({"error": "Email is required"}, status=400)
            
        invite = await InviteService.create_invite(
            name=name,
            email=email
        )
        return JsonResponse(invite.model_dump())
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@require_GET
async def get_invites_view(request):
    """Get all invites"""
    try:
        invites = await InviteService.get_invites()
        return JsonResponse({
            "invites": [invite.model_dump() for invite in invites]
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
@require_POST
async def accept_invite_view(request, invite_id: str):
    """Accept an invite"""
    try:
        invite = await InviteService.accept_invite(invite_id)
        return JsonResponse(invite.model_dump())
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
@require_POST
async def decline_invite_view(request, invite_id: str):
    """Decline an invite"""
    try:
        invite = await InviteService.decline_invite(invite_id)
        return JsonResponse(invite.model_dump())
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
@require_http_methods(["DELETE"])
async def delete_invite_view(request, invite_id: str):
    """Delete an invite"""
    try:
        await InviteService.delete_invite(invite_id)
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@require_GET
async def get_invite_view(request, invite_id: str):
    """Get a single invite by ID - no auth required"""
    try:
        invite = await InviteService.get_invite(invite_id)
        if not invite:
            return JsonResponse({"error": "Invite not found"}, status=404)
            
        return JsonResponse(invite.model_dump())
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400) 