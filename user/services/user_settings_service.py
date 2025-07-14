from typing import Dict, Any, Optional
from ..models.user_settings import UserSettings, Theme, AvatarType
from common.supabase.supabase_client import get_authenticated_client, get_current_user
from datetime import datetime

class UserSettingsService:
    @staticmethod
    async def get_or_create_user_settings() -> UserSettings:
        """Gets or creates user settings for the current user"""
        supabase = get_authenticated_client()
        user = get_current_user()
        
        # Try to get existing user settings
        response = supabase.table("user_settings")\
            .select("*")\
            .eq("user_id", user["id"])\
            .execute()
        
        if not response.data:  # Empty list means no settings found
            # Create default settings
            settings_data = {
                "user_id": user["id"],
                "avatar_type": AvatarType.UPLOAD.value,
                "theme": Theme.LIGHT.value,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Save settings
            response = supabase.table("user_settings")\
                .insert(settings_data)\
                .execute()
                
            if getattr(response, 'error', None):
                raise Exception(f"Error creating user settings: {response.error}")
                
            return UserSettings.from_supabase(response.data[0])
            
        return UserSettings.from_supabase(response.data[0])

    @staticmethod
    async def update_user_settings(update_data: Dict[str, Any]) -> UserSettings:
        """Update one or more user settings"""
        supabase = get_authenticated_client()
        user = get_current_user()
        
        response = supabase.table("user_settings")\
            .update(update_data)\
            .eq("user_id", user["id"])\
            .execute()
            
        if getattr(response, 'error', None):
            raise Exception(f"Error updating user settings: {response.error}")
            
        return UserSettings.from_supabase(response.data[0])