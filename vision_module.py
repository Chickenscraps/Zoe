"""
Vision Module for Zoe
Handles image analysis using Gemini Vision directly.
"""
import base64
import io
import aiohttp
import os
import google.generativeai as genai
from PIL import Image
from typing import Optional

# Configuration
VISION_MODEL_NAME = "gemini-2.0-flash-lite"

class VisionModule:
    def __init__(self):
        self.enabled = True
        self.api_key = os.getenv("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(VISION_MODEL_NAME)
        else:
            print("⚠️ GEMINI_API_KEY not found. Vision disabled.")
            self.enabled = False

    async def analyze_image(self, image_url: str, prompt: str = "Describe this image.") -> str:
        """
        Download and analyze an image using Gemini Vision.
        """
        if not self.enabled:
            return"[Vision Disabled - No Key]"

        try:
            # 1. Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as resp:
                    if resp.status != 200:
                        return "[Error downloading image]"
                    image_data = await resp.read()
            
            # Convert to PIL Image
            image = Image.open(io.BytesIO(image_data))
            
            # 2. Call Gemini
            # Run in executor because genai is synchronous blocking
            import asyncio
            response = await asyncio.to_thread(
                self.model.generate_content,
                [prompt, image]
            )
            
            return f"[Gemini Vision] {response.text}"

        except Exception as e:
            print(f"⚠️ Vision analysis failed: {e}")
            return f"[Vision Error: {e}]"
            
vision_module = VisionModule()
