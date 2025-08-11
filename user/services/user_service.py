from common.supabase.supabase_client import get_authenticated_client, get_current_user, get_admin_client
from user.models.user_data import UserData
from datetime import datetime
from user.services.analytics_service import AnalyticsService
from typing import Dict, Any
from user.models.user_settings import AvatarType, Theme
from uuid import uuid4

class UserService:
    @staticmethod
    async def update_user(update_data: Dict[str, Any]) -> UserData:
        """Update user data with the provided fields"""
        supabase = get_authenticated_client()
        user = get_current_user()
        
        response = supabase.table("user_data")\
            .update(update_data)\
            .eq("id", user["id"])\
            .execute()
            
        if getattr(response, 'error', None):
            raise Exception(f"Error updating user: {response.error}")
            
        return UserData.from_supabase(response.data[0])

    @staticmethod
    async def get_or_create_user_data() -> UserData:
        """
        Gets or creates user data
        Does NOT mark onboarding as complete.
        """
        supabase = get_authenticated_client()
        supabase_admin = get_admin_client()
        user = get_current_user()
        
        # Try to get existing user data
        response = supabase.table("user_data").select("*").eq("id", user["id"]).execute()
        
        if not response.data:  # Empty list means no user found

            analytics_id = str(uuid4())
            
            # Create new user data
            user_data = UserData( 
                id=user["id"],
                email=user["email"],
                created_at=datetime.utcnow(),
                analytics_id=analytics_id,
                onboarding_completed=False,
                avatar_url=user['avatar_url'] if user['avatar_url'] else None,
                full_name=user['full_name'] if user['full_name'] else None
            )

            # Save user data
            response = supabase.table("user_data").insert(user_data.to_supabase()).execute()
            
            if getattr(response, 'error', None):
                raise Exception(f"Error creating user data: {response.error}")

            # Create analytics
            analytics = await AnalyticsService.create_analytics(analytics_id, user["id"])
            
            # Create default user settings
            settings_data = {
                "user_id": user["id"],
                "avatar_type": AvatarType.UPLOAD.value,
                "theme": Theme.LIGHT.value,
            }
            
            settings_response = supabase.table("user_settings")\
                .insert(settings_data)\
                .execute()
                
            if getattr(settings_response, 'error', None):
                print(f"Error creating user settings: {settings_response.error}")
            
            # Update user metadata in Supabase auth
            supabase_admin.auth.admin.update_user_by_id(
                user["id"],
                {
                    "user_metadata": {
                        "analytics_id": analytics_id
                    }
                }
            )

            return user_data
            
        return UserData.from_supabase(response.data[0]) 
