from datetime import datetime
from typing import List, Optional
from uuid import uuid4
from ..models.invite import Invite
from common.supabase.supabase_client import get_authenticated_client, get_current_user, get_admin_client

class InviteService:
    @staticmethod
    async def create_invite(
        name: str,
        email: str
    ) -> Invite:
        """Create a new invite"""
        supabase = get_authenticated_client()
        user = get_current_user()
        
        invite = Invite(
            id=str(uuid4()),
            name=name,
            email=email,
            user_id=user["id"],
            created_at=datetime.utcnow()
        )
        
        response = supabase.table("invites")\
            .insert(invite.to_supabase())\
            .execute()
            
        if getattr(response, 'error', None):
            raise Exception(f"Error creating invite: {response.error}")
            
        return Invite.from_supabase(response.data[0])

    @staticmethod
    async def get_invites() -> List[Invite]:
        """Get all invites"""
        supabase_admin = get_admin_client()
        
        response = supabase_admin.table("invites")\
            .select("*")\
            .eq("pending", True)\
            .execute()
            
        return [Invite.from_supabase(invite) for invite in response.data]

    @staticmethod
    async def accept_invite(invite_id: str) -> Invite:
        """Accept an invite"""
        supabase = get_authenticated_client()
        user = get_current_user()
        
        # Get the invite
        response = supabase.table("invites")\
            .select("*")\
            .eq("id", invite_id)\
            .single()\
            .execute()
            
        if not response.data:
            raise Exception("Invite not found")
            
        invite = Invite.from_supabase(response.data)
        
        if not invite.pending:
            raise Exception("Invite is no longer pending")
            
        if invite.declined:
            raise Exception("Invite has been declined")
            
        # Update invite status
        update_data = {
            "pending": False,
            "accepted": True,
            "accepted_at": datetime.utcnow().isoformat(),
            "accepted_user_id": user["id"]
        }
        
        response = supabase.table("invites")\
            .update(update_data)\
            .eq("id", invite_id)\
            .execute()
            
        if getattr(response, 'error', None):
            raise Exception(f"Error accepting invite: {response.error}")
            
        return Invite.from_supabase(response.data[0])

    @staticmethod
    async def decline_invite(invite_id: str) -> Invite:
        """Decline an invite"""
        supabase = get_authenticated_client()
        user = get_current_user()
        
        update_data = {
            "pending": False,
            "declined": True,
            "accepted_user_id": user["id"]
        }
        
        response = supabase.table("invites")\
            .update(update_data)\
            .eq("id", invite_id)\
            .execute()
            
        if getattr(response, 'error', None):
            raise Exception(f"Error declining invite: {response.error}")
            
        return Invite.from_supabase(response.data[0])

    @staticmethod
    async def delete_invite(invite_id: str):
        """Delete an invite"""
        supabase = get_authenticated_client()
        
        response = supabase.table("invites")\
            .delete()\
            .eq("id", invite_id)\
            .execute()
            
        if getattr(response, 'error', None):
            raise Exception(f"Error deleting invite: {response.error}")

    @staticmethod
    async def get_invite(invite_id: str) -> Optional[Invite]:
        """Get a single invite by ID without authentication"""
        supabase_admin = get_admin_client()
        
        response = supabase_admin.table("invites")\
            .select("*")\
            .eq("id", invite_id)\
            .single()\
            .execute()
            
        if not response.data:
            return None
            
        return Invite.from_supabase(response.data) 