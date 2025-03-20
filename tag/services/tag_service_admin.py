from tag.models.tag import Tag
from common.supabase.supabase_client import get_admin_client
from datetime import datetime
from uuid import uuid4

class TagServiceAdmin:

    @staticmethod
    async def create_tag(
        label: str,
        props: dict = None
    ) -> Tag:
        """Create a new tag"""
        supabase = get_admin_client()
        
        tag_data = {
            "id": str(uuid4()),
            "label": label,
            "last_used": datetime.utcnow().isoformat(),
            "is_system": True,
            **(props or {})
        }
        
        response = supabase.table("tags")\
            .insert(tag_data)\
            .execute()
            
        if getattr(response, 'error', None):
            raise Exception(f"Error adding tag: {response.error}")
            
        return Tag.from_supabase(response.data[0])

    @staticmethod   
    async def get_tag(tag_id: str) -> Tag:
        """Get a tag by ID"""
        supabase = get_admin_client()
        
        response = supabase.table("tags")\
            .select("*")\
            .eq("id", tag_id)\
            .execute()
            
        if getattr(response, 'error', None):
            raise Exception("Error getting tag")
        
        if len(response.data) == 0:
            return None
        return Tag.from_supabase(response.data[0])