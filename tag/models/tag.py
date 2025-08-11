from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class Tag(BaseModel):
    id: str
    label: str
    description: Optional[str]
    user_id: Optional[str] = Field(None, description="FK:UserData:CASCADE")
    auto_generated: bool = False
    last_used: Optional[datetime] = None
    is_system: bool = False

    @classmethod
    def from_supabase(cls, data: dict):
        return cls(
            id=data["id"],
            label=data["label"],
            description=data.get("description", None),
            user_id=data.get("user_id", None),
            auto_generated=data["auto_generated"],
            last_used=datetime.fromisoformat(data["last_used"]) if data.get("last_used") else None,
            is_system=data.get("is_system", False)
        )

    def to_supabase(self):
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "user_id": self.user_id,
            "auto_generated": self.auto_generated,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "is_system": self.is_system
        } 