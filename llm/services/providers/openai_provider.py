from typing import AsyncGenerator, List, Dict, Any, Optional
from openai import AsyncOpenAI
from ..llm_provider import BaseLLMProvider
import os
from openai.types.create_embedding_response import CreateEmbeddingResponse
import tiktoken
from common.logger.logger_service import get_logger

logger = get_logger()

class OpenAIProvider(BaseLLMProvider):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.default_model = "gpt-4o-mini"
        self.default_embedding_model = "text-embedding-3-small"
        self._encodings = {}  # Cache for encoders

    def _get_encoding(self, model: str):
        """Get or create tiktoken encoding for a model"""
        if model not in self._encodings:
            self._encodings[model] = tiktoken.encoding_for_model(model)
        return self._encodings[model]

    async def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken"""
        try:
            encoding = self._get_encoding(self.default_embedding_model)
            return len(encoding.encode(text))
        except Exception as e:
            logger.error(f"Error counting tokens with tiktoken: {e}")
            # Fallback: rough estimate
            return len(text.split()) * 1.3

    async def count_tokens_batch(self, texts: List[str]) -> List[int]:
        """Count tokens for multiple texts"""
        try:
            encoding = self._get_encoding(self.default_embedding_model)
            return [len(encoding.encode(text)) for text in texts]
        except Exception as e:
            logger.error(f"Error counting tokens batch with tiktoken: {e}")
            # Fallback: rough estimate
            return [len(text.split()) * 1.3 for text in texts]

    async def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        stream_options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None] | Dict[str, Any]:

        response = await self.client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            stream_options=stream_options
        )

        if stream:
            async def response_generator():
                async for chunk in response:
                    yield chunk
            return response_generator()
        
        return {
            "content": response.choices[0].message.content,
            "usage": response.usage
        } 

    async def create_embedding(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create an embedding vector for text"""
        response = await self.client.embeddings.create(
            model=model or self.default_embedding_model,
            input=text
        )
        
        return {
            "embedding": response.data[0].embedding,
            "usage": response.usage
        } 

    async def create_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create embeddings for multiple texts in one API call
        
        Returns:
            Dict containing:
                embeddings: List of embedding vectors
                usage: Token usage statistics
        """
        response: CreateEmbeddingResponse = await self.client.embeddings.create(
            model=model or self.default_embedding_model,
            input=texts
        )
        
        return {
            "embeddings": [data.embedding for data in response.data],
            "usage": response.usage
        } 