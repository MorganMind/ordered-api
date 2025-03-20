from typing import AsyncGenerator, List, Dict, Any, Optional
from ..llm_provider import BaseLLMProvider
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer
from common.logger.logger_service import get_logger

logger = get_logger()

class GteSmallProvider(BaseLLMProvider):
    def __init__(self):
        super().__init__()
        self.default_model = "Supabase/gte-small"
        self.default_embedding_model = "Supabase/gte-small"
        self._model: Optional[SentenceTransformer] = None
        self._tokenizer = None

    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the model"""
        if self._model is None:
            self._model = SentenceTransformer(self.default_embedding_model)
        return self._model

    @property
    def tokenizer(self):
        """Lazy load tokenizer"""
        if self._tokenizer is None:
            self._tokenizer = AutoTokenizer.from_pretrained(self.default_embedding_model)
        return self._tokenizer

    async def count_tokens(self, text: str) -> int:
        """Count tokens using transformers tokenizer"""
        try:
            tokens = self.tokenizer.encode(text)
            return len(tokens)
        except Exception as e:
            logger.error(f"Error counting tokens with transformers: {e}")
            # Fallback: rough estimate
            return len(text.split()) * 1.3

    async def count_tokens_batch(self, texts: List[str]) -> List[int]:
        """Count tokens for multiple texts"""
        try:
            token_lists = self.tokenizer.batch_encode_plus(texts)["input_ids"]
            return [len(tokens) for tokens in token_lists]
        except Exception as e:
            logger.error(f"Error counting tokens batch with transformers: {e}")
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
        """Not implemented for GTE Small"""
        raise NotImplementedError("GTE Small does not support chat completion")

    async def create_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create embeddings using GTE Small model
        Returns normalized embeddings in the same format as OpenAI
        """
        try:
            # Generate embeddings
            embeddings = self.model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True  # This handles the F.normalize step
            )

            # Convert numpy arrays to lists for JSON serialization
            embedding_list = [emb.tolist() for emb in embeddings]

            # Estimate token usage (rough approximation)
            total_chars = sum(len(text) for text in texts)
            estimated_tokens = total_chars // 4  # Rough estimate

            return {
                "embeddings": embedding_list,
                "usage": {
                    "prompt_tokens": estimated_tokens,
                    "total_tokens": estimated_tokens
                }
            }

        except Exception as e:
            print(f"Error in GTE Small create_embeddings: {str(e)}")
            raise

    async def create_embedding(
        self,
        text: str,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a single embedding using GTE Small model
        """
        result = await self.create_embeddings([text], model)
        return {
            "embedding": result["embeddings"][0],
            "usage": result["usage"]
        } 