from typing import AsyncGenerator, List, Dict, Any, Optional
from .llm_provider import LLMProvider, BaseLLMProvider
from common.logger.logger_service import get_logger

logger = get_logger()

class LLMService:
    _instance = None
    _providers: Dict[LLMProvider, BaseLLMProvider] = {}
    _default_provider = LLMProvider.OPENAI

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMService, cls).__new__(cls)
            # Initialize providers when first instance is created
            cls.configure_providers()
        return cls._instance

    @classmethod
    def configure_providers(cls) -> None:
        """Configure available LLM providers"""
        from .providers.openai_provider import OpenAIProvider
        from .providers.gte_small_provider import GteSmallProvider
        
        cls._providers = {
            LLMProvider.OPENAI: OpenAIProvider(),
            LLMProvider.GTE_SMALL: GteSmallProvider()
        }
        cls._default_provider = LLMProvider.OPENAI

    @classmethod
    async def chat_completion(
        cls,
        messages: List[Dict[str, str]],
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        stream: bool = False,
        stream_options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None] | Dict[str, Any]:
        """
        Generic chat completion method that works with any provider
        """
        active_provider = cls._providers.get(provider or cls._default_provider)
        if not active_provider:
            raise ValueError(f"Provider {provider} not configured")

        return await active_provider.create_chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            stream_options=stream_options
        )

    @classmethod
    async def create_embeddings(
        cls,
        texts: List[str],
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        batch_size: int = 100  # OpenAI allows up to 2048 inputs per request
    ) -> List[Dict[str, Any]]:
        """
        Create embeddings for multiple texts efficiently in batches
        Returns list of embeddings with their usage stats
        """
        active_provider = cls._providers.get(provider or cls._default_provider)
        if not active_provider:
            raise ValueError(f"Provider {provider} not configured")

        results = []
        total_usage = {"prompt_tokens": 0, "total_tokens": 0}

        # Process in batches to stay within API limits
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            print(f"embedding batch: {i} {batch_size}")
            try:
                response = await active_provider.create_embeddings(
                    texts=batch,
                    model=model
                )

                results.extend(response["embeddings"])

                # Accumulate token usage
                if "usage" in response:
                    total_usage["prompt_tokens"] += response["usage"]["prompt_tokens"]
                    total_usage["total_tokens"] += response["usage"]["total_tokens"]

            except Exception as e:
                logger.error(f"Error creating embeddings: {e}")
                raise e
        print(f"embedding batch END")
        return {
            "embeddings": results,
            "usage": total_usage
        }

    @classmethod
    async def create_embedding(
        cls,
        text: str,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None
    ) -> List[float]:
        """
        Create embedding for a single text
        Returns the embedding vector
        """
        active_provider = cls._providers.get(provider or cls._default_provider)
        if not active_provider:
            raise ValueError(f"Provider {provider} not configured")

        try:
            response = await active_provider.create_embeddings(
                texts=[text],  # Send as single-item list
                model=model
            )

            # Return just the embedding vector from the first (and only) result
            return response["embeddings"][0]

        except Exception as e:
            logger.error(
                "Error creating single embedding",
                extra={
                    "text_length": len(text),
                    "error": str(e)
                }
            )
            raise

    @classmethod
    async def count_tokens(
        cls,
        text: str,
        provider: LLMProvider = LLMProvider.OPENAI,
    ) -> int:
        """Count tokens using the specified provider's tokenizer"""
        active_provider = cls._providers.get(provider)
        if not active_provider:
            raise ValueError(f"Provider {provider} not configured")
            
        return await active_provider.count_tokens(text)

    @classmethod
    async def count_tokens_batch(
        cls,
        texts: List[str],
        provider: LLMProvider = LLMProvider.OPENAI,
    ) -> List[int]:
        """Count tokens for multiple texts using the specified provider's tokenizer"""
        active_provider = cls._providers.get(provider)
        if not active_provider:
            raise ValueError(f"Provider {provider} not configured")
            
        return await active_provider.count_tokens_batch(texts) 