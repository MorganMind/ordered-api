from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any, Optional
from enum import Enum

class LLMProvider(Enum):
    OPENAI = "openai"
    GTE_SMALL = "gte-small"
    # Add more providers as needed
    # ANTHROPIC = "anthropic"
    # COHERE = "cohere"

class BaseLLMProvider(ABC):
    def __init__(self):
        self.default_model: Optional[str] = None
        self.default_embedding_model: Optional[str] = None

    @abstractmethod
    async def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        stream_options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None] | Dict[str, Any]:
        pass 
    
    @abstractmethod
    async def create_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        pass 

    @abstractmethod
    async def create_embedding(
        self,
        text: str,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        pass 

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        pass

    @abstractmethod
    async def count_tokens_batch(self, texts: List[str]) -> List[int]:
        pass 