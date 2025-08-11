<<<<<<< HEAD
from pydantic import BaseModel
=======
from pydantic import BaseModel, Field
>>>>>>> 841269cafde83fe6014a93f44959c790b8e0a23b
from .taggable_type import TaggableType

class Tagging(BaseModel):
    id: str
<<<<<<< HEAD
    tag_id: str
=======
    tag_id: str = Field(description="FK:Tag:CASCADE")
>>>>>>> 841269cafde83fe6014a93f44959c790b8e0a23b
    taggable_type: TaggableType
    taggable_id: str

    @classmethod
    def from_supabase(cls, data: dict):
        return cls(
            id=data["id"],
            tag_id=data["tag_id"],
            taggable_type=TaggableType.from_string(data["taggable_type"]),
            taggable_id=data["taggable_id"]
        )

    def to_supabase(self):
        return {
            "id": self.id,
            "tag_id": self.tag_id,
            "taggable_type": self.taggable_type.value,
            "taggable_id": self.taggable_id
        } 