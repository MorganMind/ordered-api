from pydantic import BaseModel
from enum import Enum

class Theme(str, Enum):
    LIGHT = "light"
    DARK = "dark"

class AvatarType(str, Enum):
    ICON = "icon"
    CARICATURE = "caricature"
    UPLOAD = "upload"

    @classmethod
    def from_string(cls, value: str) -> 'AvatarType':
        try:
            return cls(value.lower())
        except ValueError:
            return cls.ICON

class UserSettings(BaseModel):
    user_id: str
    avatar_type: AvatarType = AvatarType.UPLOAD
    theme: Theme = Theme.LIGHT

    @staticmethod
    def from_supabase(data: dict) -> "UserSettings":
        return UserSettings(
            user_id=data["user_id"],
            avatar_type=AvatarType(data["avatar_type"]),
            theme=Theme(data["theme"]),
        )
