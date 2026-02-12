"""Quick deploy script for Zoe's projects."""
import os
import requests
import zipfile
import io

# Load token
TOKEN = os.getenv("NETLIFY_TOKEN", "")
DIR_PATH = r"C:\Users\josha\OneDrive\Desktop\Zoes\zoe-manifesto"

# Create zip
zip_buffer = io.BytesIO()
with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(DIR_PATH):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, DIR_PATH)
            zf.write(file_path, arcname)
zip_buffer.seek(0)

# Deploy
print("Deploying to Netlify...")
resp = requests.post(
    "https://api.netlify.com/api/v1/sites",
    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/zip"},
    data=zip_buffer.read()
)

if resp.status_code in [200, 201]:
    data = resp.json()
    subdomain = data.get("subdomain", "unknown")
    print(f"SUCCESS: https://{subdomain}.netlify.app")
else:
    print(f"ERROR: {resp.status_code} - {resp.text[:200]}")
