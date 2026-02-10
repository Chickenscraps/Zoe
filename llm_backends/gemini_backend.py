"""
Gemini Direct API Backend
Handles direct API calls to Google Gemini with proper error handling and retries.
"""
import os
import asyncio
import logging
from typing import List, Dict, Optional
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

class GeminiBackend:
    """Direct Gemini API backend using Google's official SDK."""
    
    def __init__(self):
        """Initialize with API key from environment."""
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not found in environment. "
                "Please set it in .env.secrets or Windows environment variables."
            )
        
        # Configure the SDK (DO NOT log the key)
        self.client = genai.Client(api_key=api_key)
        logger.info("✅ Gemini backend initialized")
    
    async def generate_text(
        self,
        messages: List[Dict[str, str]],
        model: str = "gemini-2.0-flash-lite",
        temperature: float = 0.7,
        max_output_tokens: int = 4096,
        timeout_s: int = 120,
        retries: int = 3
    ) -> str:
        """
        Generate text using Gemini API.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (gemini-2.0-flash-lite or gemini-2.5-pro)
            temperature: Sampling temperature (0.0-1.0)
            max_output_tokens: Maximum tokens in response
            timeout_s: Request timeout in seconds
            retries: Number of retry attempts
            
        Returns:
            Generated text response
            
        Raises:
            Exception: If all retries fail
        """
        # Convert messages to Gemini format
        gemini_contents = self._convert_messages(messages)
        
        # Configure generation
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            safety_settings=[
                types.SafetySetting(
                    category="HARM_CATEGORY_HARASSMENT",
                    threshold="BLOCK_NONE"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH",
                    threshold="BLOCK_NONE"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    threshold="BLOCK_NONE"
                ),
                types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="BLOCK_NONE"
                ),
            ]
        )
        
        # Retry loop
        for attempt in range(retries):
            try:
                logger.info(f"🤖 [Gemini] Calling {model} (attempt {attempt + 1}/{retries})...")
                
                # Generate with timeout
                response = await asyncio.wait_for(
                    self._generate_async(model, gemini_contents, config),
                    timeout=timeout_s
                )
                
                if response and response.text:
                    logger.info(f"✅ [Gemini] {model} responded ({len(response.text)} chars)")
                    return response.text
                else:
                    logger.warning(f"⚠️ [Gemini] Empty response from {model}")
                    if attempt == retries - 1:
                        raise RuntimeError("Empty response from Gemini")
                        
            except asyncio.TimeoutError:
                logger.warning(f"⏱️ [Gemini] Timeout ({timeout_s}s) on attempt {attempt + 1}")
                if attempt == retries - 1:
                    raise RuntimeError(f"Gemini timeout after {retries} attempts")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check for rate limits
                if "429" in error_msg or "quota" in error_msg or "rate limit" in error_msg:
                    logger.warning(f"🚦 [Gemini] Rate limit hit: {e}")
                    if attempt < retries - 1:
                        wait_time = min(2 ** attempt, 30)  # Cap at 30 seconds
                        logger.info(f"⏳ Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                        continue
                
                # Check for server errors (5xx)
                if "500" in error_msg or "503" in error_msg or "internal error" in error_msg:
                    logger.warning(f"🔥 [Gemini] Server error: {e}")
                    if attempt < retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                
                # Other errors
                logger.error(f"❌ [Gemini] Error on attempt {attempt + 1}: {e}")
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
        
        raise RuntimeError(f"Failed to generate after {retries} attempts")
    
    async def _generate_async(self, model: str, contents: List, config):
        """Async wrapper for generate_content."""
        # Run blocking call in executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
        )
    
    def _convert_messages(self, messages: List[Dict[str, str]]) -> List:
        """
        Convert OpenAI-style messages to Gemini format.
        
        Gemini expects:
        - 'user' and 'model' roles (not 'assistant')
        - System messages merged into first user message
        """
        gemini_contents = []
        system_content = None
        
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                # Store system message to prepend to first user message
                system_content = content
            elif role == "assistant":
                # Convert 'assistant' to 'model' for Gemini
                gemini_contents.append({
                    "role": "model",
                    "parts": [{"text": content}]
                })
            else:  # user or other
                # Prepend system message if this is the first user message
                if system_content and not any(c.get("role") == "user" for c in gemini_contents):
                    content = f"{system_content}\n\n{content}"
                    system_content = None
                
                gemini_contents.append({
                    "role": "user",
                    "parts": [{"text": content}]
                })
        
        return gemini_contents


# Singleton instance
_backend = None

def get_backend() -> GeminiBackend:
    """Get or create singleton Gemini backend instance."""
    global _backend
    if _backend is None:
        _backend = GeminiBackend()
    return _backend
