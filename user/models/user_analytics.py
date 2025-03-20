from pydantic import BaseModel
from datetime import datetime

class UserAnalytics(BaseModel):
    id: str
    user_id: str
    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    messages_sent: int = 0
    uploads_count: int = 0
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def from_supabase(data: dict):
        return UserAnalytics(
            id=data["id"],
            user_id=data["user_id"],
            total_tokens=data.get("total_tokens", 0),
            prompt_tokens=data.get("prompt_tokens", 0),
            completion_tokens=data.get("completion_tokens", 0),
            messages_sent=data.get("messages_sent", 0),
            uploads_count=data.get("uploads_count", 0),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"])
        ) 