from typing import Optional, TypedDict

class UserContext(TypedDict):
    id: str
    email: Optional[str]
    analytics_id: Optional[str]
    avatar_url: Optional[str]
    full_name: Optional[str]