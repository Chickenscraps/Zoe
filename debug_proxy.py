from openai import OpenAI
import os

print("🔍 Debugging Antigravity Proxy...")
client = OpenAI(
    base_url="http://127.0.0.1:8045/v1",
    api_key=os.getenv("OPENAI_API_KEY", "sk-placeholder")
)

try:
    response = client.chat.completions.create(
        model="gemini-3-flash",
        messages=[{"role": "user", "content": "Hello! Confirm you are working."}]
    )
    print("✅ Success!")
    print(f"Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"❌ Failure: {e}")
    if hasattr(e, 'response') and e.response:
        print(f"Body: {e.response.text}")
