
print("Debugging clawdbot.py for 'llama'...")
with open("clawdbot.py", "r", encoding="utf-8", errors="ignore") as f:
    content = f.read().lower()
    index = content.find("llama")
    if index != -1:
        print(f"FOUND at index {index}")
        start = max(0, index - 50)
        end = min(len(content), index + 50)
        print(f"Context: ...{content[start:end]}...")
    else:
        print("NOT FOUND")
