from enum import Enum

class TaggableType(str, Enum):
    ARTICLE = "article"
    SOURCE = "source"

    @classmethod
    def from_string(cls, value: str) -> 'TaggableType':
        try:
            return cls(value.lower())
        except ValueError:
            return cls.ARTICLE 