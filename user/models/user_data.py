from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserData(BaseModel):
    id: str  # matches Supabase auth.user.id
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    created_at: datetime
    onboarding_completed: bool = False 
    analytics_id: Optional[str] = None  # Reference to their analytics data
    avatar_url: Optional[str] = None  # New field
    full_name: Optional[str] = None   # New field
<<<<<<< HEAD
    
    @property
    def has_completed_onboarding(self) -> bool:
        return self.onboarding_completed_at is not None
=======
>>>>>>> 841269cafde83fe6014a93f44959c790b8e0a23b

    @staticmethod
    def from_supabase(data: dict):
        return UserData(
            id=data["id"],
            email=data["email"],
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            created_at=datetime.fromisoformat(data["created_at"]),
            onboarding_completed=data.get("onboarding_completed"),
            analytics_id=data.get("analytics_id"), # Added this field
            avatar_url=data.get("avatar_url"),      # New field
            full_name=data.get("full_name"),        # New field
        )

    def to_supabase(self):
        return {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "created_at": self.created_at.isoformat(),
            "onboarding_completed": self.onboarding_completed,
            "analytics_id": self.analytics_id, # Added this field
            "avatar_url": self.avatar_url,          # New field
            "full_name": self.full_name,            # New field
        } 