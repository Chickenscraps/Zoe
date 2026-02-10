import asyncio
import os
import base64
from openai import AsyncOpenAI

async def test_flash_vision():
    print("🧪 Testing Antigravity Flash Vision directly...")
    
    # 1x1 Red Pixel Base64
    red_pixel = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    data_uri = f"data:image/png;base64,{red_pixel}"
    
    # Using model router with direct Gemini API
    # Key from env or hardcoded for test
    ANTIGRAVITY_API_KEY = "sk-50f00d8905394467aa79543666012345"

    client = AsyncOpenAI(
        base_url=ANTIGRAVITY_BASE_URL,
        api_key=ANTIGRAVITY_API_KEY,
        timeout=30.0
    )

    try:
        print(f"📡 Sending request to {ANTIGRAVITY_BASE_URL} (model: gemini-3-flash)...")
        response = await client.chat.completions.create(
            model="gemini-3-flash",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What color is this?"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_uri
                            }
                        }
                    ]
                }
            ],
            max_tokens=100
        )
        print(f"✅ Success! Response: {response.choices[0].message.content}")
        
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_flash_vision())
