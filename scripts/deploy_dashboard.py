import os
import requests
import zipfile
import io
import subprocess
import json

# Configuration
TOKEN = os.getenv("NETLIFY_TOKEN", "")
SITE_NAME = "euphonious-kitten-ef0a9d" # Updating to the actual active site name
SITE_ID = "f5ef5c5c-6f02-41dd-917a-f435c186c95c" # Hardcoding the ID to prevent new site creation
PROJECT_DIR = r"c:\Users\josha\OneDrive\Desktop\Clawd\zoe-terminal"
DIST_DIR = os.path.join(PROJECT_DIR, "dist")

# Env Vars to inject
ENV_VARS = {
    "VITE_SUPABASE_URL": os.getenv("SUPABASE_URL", ""),
    "VITE_SUPABASE_ANON_KEY": os.getenv("SUPABASE_KEY", "")
}

def create_env_file():
    env_path = os.path.join(PROJECT_DIR, ".env")
    print(f"Creating .env file at {env_path}...")
    with open(env_path, "w") as f:
        for key, value in ENV_VARS.items():
            f.write(f"{key}={value}\n")

def build_project():
    create_env_file()
    print(f"Building project in {PROJECT_DIR}...")
    # Install dependencies
    subprocess.check_call(["npm", "install"], cwd=PROJECT_DIR, shell=True)
    # Build
    subprocess.check_call(["npm", "run", "build"], cwd=PROJECT_DIR, shell=True)

def find_site_id():
    print(f"Finding site ID for {SITE_NAME}...")
    headers = {"Authorization": f"Bearer {TOKEN}"}
    # List sites (pagination might be needed if many sites, but let's try simple list)
    resp = requests.get("https://api.netlify.com/api/v1/sites", headers=headers)
    resp.raise_for_status()
    sites = resp.json()
    print(f"Found {len(sites)} sites.")
    for site in sites:
        print(f" - {site['name']} ({site['site_id']})")
        if site['name'] == SITE_NAME:
            return site['site_id']
    return None

def deploy(site_id):
    print(f"Zipping {DIST_DIR}...")
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(DIST_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, DIST_DIR)
                zf.write(file_path, arcname)
    zip_buffer.seek(0)
    
    print(f"Deploying to site ID: {site_id}...")
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/zip"
    }
    resp = requests.post(
        f"https://api.netlify.com/api/v1/sites/{site_id}/deploys",
        headers=headers,
        data=zip_buffer.read()
    )
    
    if resp.status_code in [200, 201]:
        data = resp.json()
        print(f"SUCCESS: Deployed to {data.get('url')}")
        print(f"Dashboard URL: https://{SITE_NAME}.netlify.app") # This matches the name we set above
    else:
        print(f"ERROR: {resp.status_code} - {resp.text}")

def create_site():
    print(f"Creating new site for {SITE_NAME}...")
    headers = {"Authorization": f"Bearer {TOKEN}"}
    resp = requests.post("https://api.netlify.com/api/v1/sites", headers=headers)
    if resp.status_code in [200, 201]:
        data = resp.json()
        print(f"CREATED: {data['name']} ({data['site_id']})")
        return data['site_id']
    else:
        print(f"ERROR Creating Site: {resp.status_code} - {resp.text}")
        return None

def main():
    try:
        build_project()
        # site_id = find_site_id()
        # if not site_id:
        #     print(f"Site {SITE_NAME} not found. Creating new site...")
        #     site_id = create_site()
        
        # Deploy to the hardcoded stable site
        deploy(SITE_ID)
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    main()
