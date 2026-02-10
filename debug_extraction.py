"""Debug LLM extraction"""
import json
import ollama

# Load sample messages
with open('AGENT PERSONA SKILL\\josh_messages.json', 'r', encoding='utf-8') as f:
    messages = json.load(f)[:20]

# Format messages
formatted = '\n'.join([f"[{m['timestamp']}] {m['content']}" for m in messages])
print('MESSAGES:')
print(formatted[:500])
print('\n---\n')

# Test extraction
prompt = f'''Analyze these Discord messages from Josh. Return a JSON array with 3-5 observations about his communication style, interests, or phrases:

{formatted}

Return ONLY valid JSON: [{{"type": "interest", "content": "...", "confidence": 0.8}}]'''

response = ollama.chat(
    model='llama3.1',
    messages=[{'role': 'user', 'content': prompt}]
)

print('RESPONSE:')
print(response['message']['content'][:1500])

# Try to parse
import re
content = response['message']['content']
match = re.search(r'\[.*\]', content, re.DOTALL)
if match:
    try:
        facts = json.loads(match.group())
        print(f'\nPARSED {len(facts)} facts:')
        for f in facts:
            print(f"  - {f}")
    except json.JSONDecodeError as e:
        print(f'\nJSON PARSE ERROR: {e}')
else:
    print('\nNO JSON ARRAY FOUND')
