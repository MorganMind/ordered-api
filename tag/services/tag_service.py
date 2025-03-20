from typing import List, Optional
from uuid import uuid4
from datetime import datetime
from ..models.tag import Tag
from ..models.tagging import Tagging
from ..models.taggable_type import TaggableType
from common.supabase.supabase_client import get_authenticated_client, get_current_user

class TagService:
    @staticmethod
    async def create_tag(
        label: str,
        props: dict = None
    ) -> Tag:
        """Create a new tag"""
        supabase = get_authenticated_client()
        user = get_current_user()
        
        tag_data = {
            "id": str(uuid4()),
            "label": label,
            "user_id": user["id"],
            "last_used": datetime.utcnow().isoformat(),
            **(props or {})
        }
        
        response = supabase.table("tags")\
            .insert(tag_data)\
            .execute()
            
        if getattr(response, 'error', None):
            raise Exception(f"Error adding tag: {response.error}")
            
        return Tag.from_supabase(response.data[0])

    @staticmethod
    async def create_tagging(
        tag_id: str,
        taggable_id: str,
        taggable_type: TaggableType
    ) -> Tagging:
        """Create a new tagging"""
        supabase = get_authenticated_client()
        
        tagging_data = {
            "id": str(uuid4()),
            "tag_id": tag_id,
            "taggable_type": taggable_type.value,
            "taggable_id": taggable_id
        }
        
        response = supabase.table("taggings")\
            .insert(tagging_data)\
            .execute()
            
        if getattr(response, 'error', None):
            raise Exception(f"Error adding tagging: {response.error}")
            
        return Tagging.from_supabase(response.data[0])

    @staticmethod
    async def remove_tagging(
        tag_id: str,
        taggable_id: str
    ) -> None:
        """Remove a tagging"""
        supabase = get_authenticated_client()
        
        response = supabase.table("taggings")\
            .delete()\
            .eq("tag_id", tag_id)\
            .eq("taggable_id", taggable_id)\
            .execute()
            
        if getattr(response, 'error', None):
            raise Exception("Error deleting tagging")

    @staticmethod   
    async def get_tag(tag_id: str) -> Tag:
        """Get a tag by ID"""
        supabase = get_authenticated_client()
        
        response = supabase.table("tags")\
            .select("*")\
            .eq("id", tag_id)\
            .execute()
            
        if getattr(response, 'error', None):
            raise Exception("Error getting tag")
            
        return Tag.from_supabase(response.data[0])

    @staticmethod
    async def get_user_tags() -> List[Tag]:
        """Get all tags for the current user"""
        supabase = get_authenticated_client()
        user = get_current_user()
        
        response = supabase.table("tags")\
            .select("*")\
            .eq("user_id", user["id"])\
            .execute()
            
        if getattr(response, 'error', None):
            raise Exception("Error getting tags")
            
        return [Tag.from_supabase(tag) for tag in response.data]

    @staticmethod
    async def get_taggings_for_item(
        taggable_id: str,
        taggable_type: TaggableType
    ) -> List[Tag]:
        """Get all tags for a specific item"""
        supabase = get_authenticated_client()
        
        response = supabase.table("taggings")\
            .select("tags!inner(*)")\
            .eq("taggable_id", taggable_id)\
            .eq("taggable_type", taggable_type.value)\
            .execute()
            
        if getattr(response, 'error', None):
            raise Exception("Error getting taggings")
            
        return [Tag.from_supabase(item["tags"]) for item in response.data]

    @staticmethod
    async def get_item_ids_for_tags(
        tags: List[Tag],
        type_filters: List[TaggableType] = None
    ) -> List[str]:
        """Get all item IDs that have any of the specified tags"""
        if not tags:
            return []
            
        supabase = get_authenticated_client()
        type_filters = type_filters or list(TaggableType)
        
        response = supabase.table("taggings")\
            .select("taggable_id")\
            .in_("taggable_type", [t.value for t in type_filters])\
            .in_("tag_id", [tag.id for tag in tags])\
            .execute()
            
        if getattr(response, 'error', None):
            raise Exception("Error getting taggings")
            
        return [item["taggable_id"] for item in response.data] 