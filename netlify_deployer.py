import os
import subprocess
import json
from typing import Optional, Dict

class NetlifyDeployer:
    """
    Handles autonomous deployment of Zoe's experiments to Netlify.
    """
    def __init__(self, site_dir: str):
        self.site_dir = site_dir
        # If it's a react app, public dir might be distinct, but for raw HTML (Zoes folder), 
        # the site_dir IS the public dir.
        self.public_dir = site_dir
        
    def deploy(self, production: bool = True, auth_token: Optional[str] = None) -> Dict[str, str]:
        """
        Deploy the project to Netlify.
        """
        try:
            # Resolve token
            token = auth_token or os.getenv("NETLIFY_TOKEN")
            env = os.environ.copy()
            if token: env["NETLIFY_AUTH_TOKEN"] = token
            
            # 1. ENSURE SITE EXISTS/LINKED
            # We check if .netlify folder exists in the PARENT of site_dir (the project root)
            project_root = os.path.dirname(self.site_dir)
            
            # Base command
            cmd = ["npx", "netlify", "deploy", "--dir", self.public_dir, "--json"]
            
            if production:
                cmd.append("--prod")
            
            # Run with timeout to prevent hanging the bot
            print(f"🚀 [Netlify] Deploying {self.public_dir}...")
            
            result = subprocess.run(
                cmd, 
                cwd=project_root,
                capture_output=True,
                text=True,
                shell=True,
                env=env,
                timeout=120 # 2 minute limit
            )
            
            if result.returncode != 0:
                # If it's a "site not linked" error, we try to deploy with a generic site or create one
                if "site-id" in result.stderr.lower() or "not linked" in result.stderr.lower():
                    print("⚠️ Site not linked. Attempting to create/resolve...")
                    # For simplicity, we'll try to deploy to a site matching the folder name
                    slug = os.path.basename(project_root)
                    create_cmd = ["npx", "netlify", "sites:create", "--name", f"zoe-{slug}", "--manual"]
                    subprocess.run(create_cmd, cwd=project_root, shell=True, env=env, timeout=30)
                    # Retry deploy
                    result = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True, shell=True, env=env, timeout=120)

                if result.returncode != 0:
                    return {
                        "status": "error",
                        "logs": (result.stderr or result.stdout)[:500],
                        "url": None
                    }
                
            # Parse JSON output
            try:
                # Sometimes netlify outputs text before the JSON
                output = result.stdout
                if "{" in output:
                    output = output[output.find("{"):]
                data = json.loads(output)
                url = data.get("ssl_url") or data.get("deploy_url") or data.get("url")
                return {
                    "status": "success",
                    "url": url,
                    "logs": "Deployed successfully."
                }
            except Exception as e:
                # Fallback regex
                import re
                url_match = re.search(r"https://[\w-]+\.netlify\.app", result.stdout)
                url = url_match.group(0) if url_match else None
                return {
                    "status": "success" if url else "error",
                    "url": url,
                    "logs": f"Regex fallback (JSON failed: {e})"
                }
                
        except subprocess.TimeoutExpired:
            return {"status": "error", "logs": "Netlify deployment timed out (120s).", "url": None}
        except Exception as e:
            return {"status": "error", "logs": str(e), "url": None}

if __name__ == "__main__":
    # Test
    deployer = NetlifyDeployer("c:/Users/josha/OneDrive/Desktop/Clawd/ui-clawdbot")
    print(deployer.deploy(production=False))
