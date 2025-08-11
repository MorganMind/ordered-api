<<<<<<< HEAD
from pydantic import BaseModel
=======
from pydantic import BaseModel, Field
>>>>>>> 841269cafde83fe6014a93f44959c790b8e0a23b
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
<<<<<<< HEAD
    user_id: str
=======
    user_id: str = Field(description="FK:UserData:CASCADE")
>>>>>>> 841269cafde83fe6014a93f44959c790b8e0a23b
    avatar_type: AvatarType = AvatarType.UPLOAD
    theme: Theme = Theme.LIGHT

    @staticmethod
    def from_supabase(data: dict) -> "UserSettings":
        return UserSettings(
            user_id=data["user_id"],
            avatar_type=AvatarType(data["avatar_type"]),
            theme=Theme(data["theme"]),
        )
