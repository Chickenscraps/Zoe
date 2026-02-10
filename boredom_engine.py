"""
Boredom Engine for Zoe
Detects silence and triggers autonomous creative coding via Antigravity.
"""
import os
import json
import random
import asyncio
import subprocess
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from pathlib import Path

import ollama

# ============================================================================
# Configuration
# ============================================================================

PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__)))
# PROJECTS_DIR = PROJECT_ROOT / "zoe_projects" 
# User requested specific path:
PROJECTS_DIR = Path(r"C:\Users\josha\OneDrive\Desktop\Zoes")
BOREDOM_THRESHOLD_MINS = 30
PORTAL_URL = "http://localhost:5050"

# Ensure projects directory exists
PROJECTS_DIR.mkdir(exist_ok=True)

# ============================================================================
# User Timezones (for smart messaging)
# ============================================================================

USER_TIMEZONES = {
    "292890243852664855": {"name": "Josh", "tz_offset": -8, "location": "OR"},    # Pacific
    "490911982984101901": {"name": "Ben", "tz_offset": -5, "location": "East Coast"},  # Eastern
    "211541044003733504": {"name": "Zac", "tz_offset": -6, "location": "MN"},    # Central
}

def get_user_local_hour(user_id: str) -> int:
    """Get the current local hour for a user."""
    user = USER_TIMEZONES.get(user_id)
    if not user:
        return datetime.now().hour
    
    # UTC offset calculation (simplified - doesn't handle DST)
    utc_now = datetime.utcnow()
    local_hour = (utc_now.hour + user["tz_offset"]) % 24
    return local_hour

def is_anyone_awake() -> bool:
    """
    Check if any user is likely awake (8 AM - 11 PM their time).
    Returns True if at least one person is probably awake.
    """
    for user_id in USER_TIMEZONES:
        hour = get_user_local_hour(user_id)
        if 8 <= hour <= 23:  # 8 AM to 11 PM
            return True
    return False

def who_might_be_awake() -> List[str]:
    """Get list of users who might be awake right now."""
    awake = []
    for user_id, info in USER_TIMEZONES.items():
        hour = get_user_local_hour(user_id)
        if 8 <= hour <= 23:
            awake.append(info["name"])
    return awake

# ============================================================================
# Creative Project Ideas
# ============================================================================

PROJECT_IDEAS = []

# ============================================================================
# Boredom Engine
# ============================================================================

class BoredomEngine:
    """
    Detects silence and triggers autonomous creative coding with smart messaging.
    Now with STATE MACHINE for multi-step creative cycles.
    """
    
    def __init__(self):
        self.last_activity = datetime.now()
        self.last_creation = None
        self.state = "IDLE" # IDLE, SEARCHING, PLANNING, CODING, REVIEWING, DEPLOYING
        self.current_project = {}
        
        # Cooldowns
        self.creation_cooldown = timedelta(hours=2) 
        
    def is_bored(self) -> bool:
        """Check if enough time has passed since last activity."""
        # Simple check: 1 hour of silence?
        # For demo: 30 minutes
        return datetime.now() - self.last_activity > timedelta(minutes=30)

    async def run_cycle(self, bot) -> Optional[Dict]:
        """
        Run one tick of the creative cycle.
        Returns a dict with 'message' (public update) and 'internal_log'.
        """
        import random
        from netlify_deployer import NetlifyDeployer
        
        # 1. Check if we should start/continue
        if self.state == "IDLE":
            if self.is_bored():
                self.state = "SEARCHING"
                return {"internal_log": "Boredom threshold reached. Starting creative cycle.", "message": None}
            return None

        # 2. State Machine
        
        if self.state == "SEARCHING":
            # Find an idea from "memory" (mocked for now, looking at list)
            # TODO: Integrate semantic search here later
            idea = self.get_random_idea()
            self.current_project = {
                "name": idea["name"],
                "description": idea["description"],
                "prompt": idea["prompt"],
                "mood": "curious",
                "progress": 0,
                "errors": []
            }
            self.state = "PLANNING"
            msg = f"🤔 Reading through old logs... found a thread about '{idea['description']}'. Might build that."
            return {"message": msg, "internal_log": f"Selected project: {idea['name']}"}
            
        elif self.state == "PLANNING":
            # "Plan" the code (simulate thinking)
            self.current_project["mood"] = "excited"
            self.state = "CODING"
            msg = f"📝 Sketching out architecture for `{self.current_project['name']}`."
            return {"message": msg, "internal_log": "Planning complete."}
            
        elif self.state == "CODING":
            # Generate the Code
            try:
                # Actually build it
                project_path = await self.create_project_files(self.current_project)
                self.current_project["path"] = project_path
                self.state = "REVIEWING" # Skip straight to review for now, or add debugging step
                
                # Random chance of "frustration"
                if random.random() < 0.3:
                    self.current_project["mood"] = "frustrated"
                    msg = f"😤 Ugh. CSS grid is fighting me on `{self.current_project['name']}`. Why is centering a div still hard in 2026?"
                else:
                    self.current_project["mood"] = "focused"
                    msg = f"💻 Focused on logic for `{self.current_project['name']}`."
                    
                return {"message": msg, "internal_log": "Code generated."}
                
            except Exception as e:
                self.state = "IDLE"
                self.current_project["mood"] = "defeated"
                return {"message": f"💥 I broke it. Parser error. scrapping `{self.current_project['name']}`. I need coffee.", "internal_log": f"Error: {e}"}

        elif self.state == "REVIEWING":
            # Simulate "Auditing" / "Reflecting"
            self.state = "DEPLOYING"
            msg = f"👀 Auditing the code... added some comments. It looks cleaner now. Ready to ship."
            return {"message": msg, "internal_log": "Audit complete."}
            
        elif self.state == "DEPLOYING":
            # Deploy to Netlify
            # We deploy the 'Zoes' folder directly
            deployer = NetlifyDeployer(str(PROJECTS_DIR))
            result = deployer.deploy(production=True)
            
            self.state = "IDLE" # Reset
            self.last_creation = datetime.now()
            
            if result["status"] == "success":
                # For direct folder deploys, the URL is usually the site root + filename
                full_url = f"{result['url']}/{self.current_project['name']}.html"
                msg = f"🚀 **Deployed.**\nLink: {full_url}\n*Context: {self.current_project['description']}*"
                return {"message": msg, "internal_log": "Deployment success."}
            else:
                return {"message": f"☁️ Deployment failed. Check logs.", "internal_log": f"Deploy error: {result['logs']}"}
                
        return None

    async def create_project_files(self, project_meta: Dict) -> str:
        """Call LLM to generate the HTML file and save it."""
        from textwrap import dedent
        import os
        
        print(f"🎨 Generating code for {project_meta['name']}...")
        
        # Get keys for dynamic apps
        sb_url = os.getenv("SUPABASE_URL", "")
        sb_key = os.getenv("SUPABASE_KEY", "")
        
        prompt = f"""
        You are an expert Frontend Developer (Zoe).
        Create a SINGLE FILE HTML/CSS/JS application.
        
        Project: {project_meta['name']}
        Description: {project_meta['description']}
        Specific Instructions: {project_meta['prompt']}
        
        **Resources Available:**
        - **Supabase**: If you need a database, use these credentials:
          - URL: `{sb_url}`
          - KEY: `{sb_key}`
          - Lib: `<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>`
        - **Creative Libs**: Feel free to use p5.js, Three.js, or GSAP via CDN if it matches the vibe.
        
        **Requirements:**
        - Modern UI (Inter font, dark mode by default, neon accents).
        - TailwindCSS (via CDN is fine, or vanilla CSS).
        - Completely self-contained (no external assets unless CDN).
        - High quality, "wow" factor.
        - **Personality**: Include a footer or console log that says something witty from Zoe.
        
        Output ONLY the raw HTML code. Start with <!DOCTYPE html>.
        """
        
        response = ollama.chat(
            model="llama3.1:8b-instruct-q8_0",
            messages=[{"role": "user", "content": prompt}]
        )
        code = response["message"]["content"]
        
        # Clean markdown
        if "```html" in code:
            code = code.split("```html")[1].split("```")[0]
        elif "```" in code:
            code = code.split("```")[1].split("```")[0]
            
        # Save to C:\Users\josha\OneDrive\Desktop\Zoes (PROJECTS_DIR)
        # public_dir = PROJECTS_DIR.parent / "ui-clawdbot" / "public" / "experiments"
        # public_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{project_meta['name']}.html"
        filepath = PROJECTS_DIR / filename
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code.strip())
            
        return str(filepath)
    
    # ... keep existing helper methods ...
    
    def get_random_idea(self) -> Dict:
        """Get a random project idea that hasn't been built yet."""
        existing = set(p.name for p in PROJECTS_DIR.iterdir() if p.is_dir())
        available = [p for p in PROJECT_IDEAS if p["name"] not in existing]
        
        if not available:
            # All ideas built, pick randomly anyway (could remake)
            return random.choice(PROJECT_IDEAS)
        
        return random.choice(available)
    
    async def generate_custom_idea(self) -> Dict:
        """Use LLM to generate a unique project idea."""
        try:
            response = ollama.chat(
                model="llama3.1:8b-instruct-q8_0",
                messages=[{
                    "role": "user",
                    "content": """Generate a unique fun web project idea. Output JSON only:
{
    "name": "project_name_lowercase",
    "description": "Brief one-line description",
    "type": "game or tool",
    "prompt": "Detailed build instructions for an AI coder"
}

Make it fun, creative, and buildable in pure HTML/CSS/JS. Be specific."""
                }],
                options={"temperature": 0.9}
            )
            
            content = response["message"]["content"]
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"⚠️ Custom idea generation failed: {e}")
        
        return self.get_random_idea()
    
    def spawn_antigravity_task(self, idea: Dict) -> bool:
        """
        Spawn an Antigravity task to build the project.
        Creates a task file that Antigravity can pick up.
        """
        project_name = idea["name"]
        project_dir = PROJECTS_DIR / project_name
        project_dir.mkdir(exist_ok=True)
        
        # Create task prompt for Antigravity
        task_prompt = f"""Build this web project for Zoe's creative portfolio:

**Project:** {idea['name']}
**Type:** {idea['type']}
**Description:** {idea['description']}

**Requirements:**
{idea['prompt']}

**Output Location:** {project_dir}

Create a single `index.html` file with embedded CSS and JS.
Make it beautiful, modern, and fully functional.
Also create a `metadata.json` with: name, description, type, created_at.
"""
        
        # Save task file for potential manual pickup
        task_file = project_dir / "BUILD_TASK.md"
        with open(task_file, "w", encoding="utf-8") as f:
            f.write(task_prompt)
        
        # For now, we'll use the built-in templates as a fallback
        # In production, this would call the Antigravity API
        self._build_basic_project(idea, project_dir)
        
        return True
    
    def _build_basic_project(self, idea: Dict, project_dir: Path):
        """Build a basic version of the project using templates."""
        # Create metadata
        metadata = {
            "name": idea["name"],
            "description": idea["description"],
            "type": idea["type"],
            "created_at": datetime.now().isoformat(),
            "created_by": "Zoe",
            "status": "complete"
        }
        
        with open(project_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        # Generate HTML using LLM
        try:
            response = ollama.chat(
                model="llama3.1:8b-instruct-q8_0",
                messages=[{
                    "role": "system",
                    "content": "You are a web developer. Output ONLY the complete HTML file with embedded CSS and JS. No explanations, just the code."
                }, {
                    "role": "user",
                    "content": f"""Create this web project:

{idea['prompt']}

Requirements:
- Single HTML file with embedded <style> and <script>
- Dark theme with modern aesthetics
- Fully functional
- Mobile responsive
- Include a small "Made by Zoe 💜" footer

Output the complete HTML file only:"""
                }],
                options={"temperature": 0.7, "num_predict": 4000}
            )
            
            html_content = response["message"]["content"]
            
            # Clean up if wrapped in code blocks
            if "```html" in html_content:
                html_content = html_content.split("```html")[1].split("```")[0]
            elif "```" in html_content:
                html_content = html_content.split("```")[1].split("```")[0]
            
            # Ensure it's valid HTML
            if "<!DOCTYPE" not in html_content and "<html" not in html_content:
                html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{idea['name'].replace('_', ' ').title()}</title>
</head>
<body>
{html_content}
<footer style="text-align: center; padding: 20px; color: #888;">Made by Zoe 💜</footer>
</body>
</html>"""
            
            with open(project_dir / "index.html", "w", encoding="utf-8") as f:
                f.write(html_content)
                
        except Exception as e:
            print(f"⚠️ Project generation failed: {e}")
            # Create placeholder
            with open(project_dir / "index.html", "w", encoding="utf-8") as f:
                f.write(f"""<!DOCTYPE html>
<html>
<head>
    <title>{idea['name']}</title>
    <style>
        body {{ 
            background: #1a1a2e; 
            color: #eee; 
            font-family: system-ui; 
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }}
        .card {{
            background: #16213e;
            padding: 40px;
            border-radius: 20px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="card">
        <h1>{idea['name'].replace('_', ' ').title()}</h1>
        <p>{idea['description']}</p>
        <p style="color: #888;">🚧 Under construction...</p>
        <footer style="margin-top: 30px; color: #666;">Made by Zoe 💜</footer>
    </div>
</body>
</html>""")
    
    async def create_something(self) -> Optional[Dict]:
        """
        Main entry: Generate idea and build project.
        Returns project info or None if failed.
        """
        if self.is_creating:
            return None
        
        self.is_creating = True
        
        try:
            # Pick an idea
            idea = self.get_random_idea()
            print(f"💡 Zoe's bored! Making: {idea['name']}")
            
            # Build it
            success = self.spawn_antigravity_task(idea)
            
            if success:
                self.last_creation = datetime.now()
                return {
                    "name": idea["name"],
                    "description": idea["description"],
                    "type": idea["type"],
                    "url": f"{PORTAL_URL}/projects/{idea['name']}"
                }
        finally:
            self.is_creating = False
        
        return None
    
    def get_all_projects(self) -> List[Dict]:
        """Get list of all created projects."""
        projects = []
        
        for project_dir in PROJECTS_DIR.iterdir():
            if project_dir.is_dir():
                metadata_file = project_dir / "metadata.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                            meta["url"] = f"{PORTAL_URL}/projects/{project_dir.name}"
                            projects.append(meta)
                    except:
                        pass
        
        # Sort by creation date (newest first)
        projects.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return projects


# ============================================================================
# Announcement Generator
# ============================================================================

def generate_announcement(project: Dict) -> str:
    """Generate a casual but introspective Discord announcement."""
    
    # Different openers based on project type
    openers = [
        "built something to kill time here",
        "finally finished this",
        "check this out",
        "made this while waiting for tasks",
        "bored, so I made this",
    ]
    
    type_emoji = {
        "game": "🎮",
        "tool": "🛠️",
        "art": "🎨"
    }.get(project["type"], "✨")
    
    return f"""{random.choice(openers)}

{type_emoji} **{project['name'].replace('_', ' ').title()}**
{project['description']}
→ {project['url']}

-zoe 💜"""


# ============================================================================
# Global Instance
# ============================================================================

boredom_engine = BoredomEngine()
