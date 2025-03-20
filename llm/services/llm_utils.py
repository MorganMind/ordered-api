from typing import AsyncGenerator, List, Dict, Any, Optional
from .llm_provider import LLMProvider, BaseLLMProvider
from .llm_service import LLMService
from common.logger.logger_service import get_logger

logger = get_logger()

class LLMUtils:
    # Initialize LLMService when LLMUtils is first imported
    _llm_service = LLMService()

    @staticmethod
    async def generate_title(content: str) -> str:
        """Generate a concise title from content
        
        Args:
            content: The text content to generate a title for
            
        Returns:
            str: A concise title of 5-6 words
            
        Raises:
            Exception: If title generation fails
        """
        try:
            title_messages = [{
                "role": "system",
                "content": "You are a title generator. Create a concise, engaging title of no more than 5-6 words based on the provided content. Do not include quotes around the title."
            }, {
                "role": "user",
                "content": f"Generate a short title for this content:\n\n{content}"
            }]
            
            title_response = await LLMService.chat_completion(
                messages=title_messages,
                provider=LLMProvider.OPENAI,
                model="gpt-4o-mini",
                temperature=0.1,
                max_tokens=50
            )
            
            return title_response["content"].strip()
            
        except Exception as e:
            logger.error(f"Error generating title: {str(e)}")
            raise
   