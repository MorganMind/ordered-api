from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class Invite(BaseModel):
    id: str
    name: str
    email: str
    pending: bool = True
    created_at: datetime
    accepted_at: Optional[datetime] = None
    accepted: bool = False
    declined: bool = False
    user_id: str  # User who created the invite
    accepted_user_id: Optional[str] = None  # User who accepted the invite

    @staticmethod
    def from_supabase(data: dict):
        return Invite(
            id=data["id"],
            name=data["name"],
            email=data["email"],
            pending=data.get("pending", True),
            created_at=datetime.fromisoformat(data["created_at"]),
            accepted_at=datetime.fromisoformat(data["accepted_at"]) if data.get("accepted_at") else None,
            accepted=data.get("accepted", False),
            declined=data.get("declined", False),
            user_id=data["user_id"],
            accepted_user_id=data.get("accepted_user_id")
        )

    def to_supabase(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "pending": self.pending,
            "created_at": self.created_at.isoformat(),
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "accepted": self.accepted,
            "declined": self.declined,
            "user_id": self.user_id,
            "accepted_user_id": self.accepted_user_id
        } 