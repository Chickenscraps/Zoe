
import os
import sys

FORBIDDEN_TOKENS = ["llama", "ollama", "gguf", "vllm"]
EXCLUDED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".pyc", ".log", ".lock", ".json", ".pdf", ".exe", ".dll", ".sqlite"}
EXCLUDED_DIRS = {
    ".git", "node_modules", ".next", "__pycache__", "dist", ".build", 
    "venv", ".venv", ".agent", ".system_generated", "research"
}
EXCLUDED_FILES = {
    os.path.basename(__file__), # This script
    "implementation_plan.md",
    "task.md",
    "README.md", # Documentation might mention migration
    "package-lock.json",
    "pnpm-lock.yaml"
}

def scan_file(filepath):
    """Scan a file for forbidden tokens."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read().lower()
            for token in FORBIDDEN_TOKENS:
                if token in content:
                    return token, filepath
    except Exception:
        pass # Ignore binary/unreadable
    return None

def main():
    print("🔍 Scanning for forbidden tokens:", FORBIDDEN_TOKENS)
    print("📂 Excluding:", EXCLUDED_DIRS)
    
    found_issues = []
    root_dir = os.getcwd()
    
    for root, dirs, files in os.walk(root_dir):
        # Filter directories
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
        
        for file in files:
            if file in EXCLUDED_FILES:
                continue
                
            filepath = os.path.join(root, file)
            # Skip excluded extensions
            _, ext = os.path.splitext(file)
            if ext.lower() in EXCLUDED_EXTENSIONS:
                continue

            result = scan_file(filepath)
            if result:
                token, path = result
                print(f"❌ Found '{token}' in: {os.path.relpath(path, root_dir)}")
                found_issues.append((token, path))

    if found_issues:
        print(f"\n🚨 check_forbidden_tokens failed! Found {len(found_issues)} violations.")
        sys.exit(1)
    else:
        print("\n✅ No forbidden tokens found. Gemini Only enforced.")
        sys.exit(0)

if __name__ == "__main__":
    main()
