<<<<<<< HEAD
from uuid import uuid4
=======
>>>>>>> 841269cafde83fe6014a93f44959c790b8e0a23b
from datetime import datetime
from common.supabase.supabase_client import get_authenticated_client, get_current_user, get_admin_client
from user.models.user_analytics import UserAnalytics
import asyncio

class AnalyticsService:
    @staticmethod
<<<<<<< HEAD
    async def create_analytics(user_id: str) -> UserAnalytics:
=======
    async def create_analytics(new_id: str, user_id: str) -> UserAnalytics:
>>>>>>> 841269cafde83fe6014a93f44959c790b8e0a23b
        supabase = get_admin_client()
        now = datetime.utcnow()
        
        analytics_data = {
<<<<<<< HEAD
            "id": str(uuid4()),
=======
            "id": new_id,
>>>>>>> 841269cafde83fe6014a93f44959c790b8e0a23b
            "user_id": user_id,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        
        response = supabase.table("user_analytics").insert(analytics_data).execute()
        return UserAnalytics.from_supabase(response.data[0])

    @staticmethod
    async def increment_metrics(analytics_id: str, **metrics) -> UserAnalytics:
        """
        Increment multiple metrics in a single call using RPC
        Example: await increment_metrics(analytics_id, messages_sent=1, total_tokens=50)
        """
        supabase = get_admin_client()
        
        # Call the RPC function
        response = supabase.rpc(
            'increment_analytics',
            {
                'p_analytics_id': analytics_id,
                'p_metrics': metrics
            }
        ).execute()
        
        if getattr(response, 'error', None):
            raise Exception(f"Failed to increment metrics: {response.error}")
        
        return UserAnalytics.from_supabase(response.data)
    
    @staticmethod
    async def _increment_async(**metrics):
        """Internal method to handle the async increment"""
        user = get_current_user()
        if not user.get('analytics_id'):
            # You might want to log this or handle it differently
            return
            
        await AnalyticsService.increment_metrics(
            user['analytics_id'],
            **metrics
        )

    @staticmethod
    def track(**metrics):
        """
        Create an async task to track metrics without waiting for completion
        """
        asyncio.create_task(AnalyticsService._increment_async(**metrics))

    @staticmethod
    def track_message(total_tokens: int, prompt_tokens: int, completion_tokens: int):
        """
        Track metrics related to message sending
        """
        AnalyticsService.track(
            messages_sent=1,
            total_tokens=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens
        )

    @staticmethod
    def track_upload():
        """
        Track metrics when a file is uploaded
        """
        AnalyticsService.track(uploads_count=1)

    @staticmethod
    async def get_user_analytics(user_id: str) -> UserAnalytics:
        """Get analytics data for a user"""
        supabase = get_authenticated_client()
        
        response = supabase.table("user_analytics")\
            .select("*")\
            .eq("user_id", user_id)\
            .execute()
        
        if not response.data:
            raise Exception(f"No analytics found for user {user_id}")
        
        return UserAnalytics.from_supabase(response.data[0])