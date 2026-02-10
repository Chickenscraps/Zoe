"""
Creative Pipeline for Zoe
Autonomous creative loop that builds projects, posts progress, deploys, and repeats.
"""
import os
import asyncio
import random
import json
from datetime import datetime
from typing import Optional, Dict
from pathlib import Path
from dotenv import load_dotenv

# Import Game Factory
from game_factory import game_factory, GENRES

load_dotenv(".env.secrets")

# Config
INTERNAL_CHANNEL_ID = 1462568916692762687  # Zoe's main channel (new server)
PLAYGROUND_PATH = r"C:\Users\josha\OneDrive\Desktop\Zoes"
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Zoe's Web App Ideas (Cleared)
ZOE_WEB_IDEAS = []

# Zoe's Game Ideas (Cleared)
ZOE_GAME_IDEAS = []


class CreativePipeline:
    """Autonomous creative loop for Zoe with state persistence."""
    
    def __init__(self, bot):
        self.bot = bot
        self.is_running = False
        self.current_project = None
        self.active_game_slug = None
        self.last_started_date = None
        self.units_completed = 0
        self.deploys_today = 0
        self.has_replanned = False
        self.internal_channel = None
        self.state_file = os.path.join(PLAYGROUND_PATH, "creative_state.json")
        self._load_state()
        
    def _load_state(self):
        """Load persistent state from disk."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.active_game_slug = data.get("active_game_slug")
                    self.last_started_date = data.get("last_started_date")
                    self.units_completed = data.get("units_completed", 0)
                    self.deploys_today = data.get("deploys_today", 0)
                    self.has_replanned = data.get("has_replanned", False)
                    print(f"📦 [CreativePipeline] Resumed: {self.active_game_slug} (Units: {self.units_completed}, Deploys: {self.deploys_today})")
            except Exception as e:
                print(f"⚠️ Failed to load state: {e}")

    def _save_state(self):
        """Save persistent state to disk."""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump({
                    "active_game_slug": self.active_game_slug,
                    "last_started_date": self.last_started_date,
                    "units_completed": self.units_completed,
                    "deploys_today": self.deploys_today,
                    "has_replanned": self.has_replanned
                }, f)
        except Exception as e:
            print(f"⚠️ Failed to save state: {e}")

    async def start(self):
        """Start the creative loop."""
        if self.is_running:
            return
            
        self.is_running = True
        self.internal_channel = self.bot.get_channel(INTERNAL_CHANNEL_ID)
        
        asyncio.create_task(self._creative_loop())
        
    async def _creative_loop(self):
        """Main creative loop - runs forever."""
        while self.is_running:
            try:
                await self._run_creative_cycle()
                await asyncio.sleep(60)  # Work every minute for focused sprint
            except Exception as e:
                print(f"❌ Creative cycle error: {e}")
                await asyncio.sleep(30)
                
    async def _run_creative_cycle(self):
        """One pulse of the creative engine."""
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 1. CONTINUE ACTIVE PROJECT
        if self.active_game_slug:
            await self._post_thought(f"still working on `{self.active_game_slug}`")
            
            # MILESTONE: REPLAN (Stage 2 Trigger)
            if self.units_completed >= 3 and not self.has_replanned:
                await self._replan_project()
                # Deploy Beta after replan
                await self._ship_project(tag="BETA")
                return

            result = await game_factory.run_work_unit(self.active_game_slug)
            await self._post_thought(result)
            self.units_completed += 1
            self._save_state()
            
            # MILESTONE: ALPHA (Stage 1 Trigger)
            if self.units_completed == 1 and self.deploys_today == 0:
                await self._ship_project(tag="ALPHA")

            if "No pending tasks" in result:
                if self.last_started_date == today:
                    # Final/Polish checks
                    if self.deploys_today < 3:
                        await self._ship_project(tag="FINAL" if self.deploys_today == 2 else "LATE-STAGE")
                    
                    await self._post_thought("tasks done for now, gonna add some polish")
                    self._add_polish_tasks()
                else:
                    await self._ship_project(tag="RELEASE")
            return

        # 2. START NEW PROJECT (Only if it's a new day!)
        if self.last_started_date == today:
            return

        # NEW DAY RESET
        if not ZOE_GAME_IDEAS:
            print("🎨 Creative Pipeline: No ideas in queue. Standing by.")
            return

        idea = random.choice(ZOE_GAME_IDEAS)
        slug = idea['name'].lower().replace(" ", "-")
        
        await self._post_thought(f"new day, starting on `{idea['name']}`")
        msg = await game_factory.create_new_game(idea['name'], idea['genre'])
        await self._post_thought(msg)
        
        self.active_game_slug = slug
        self.last_started_date = today
        self.units_completed = 0
        self.deploys_today = 0
        self.has_replanned = False
        self._save_state()
        
        # Initial Setup
        project_path = game_factory._get_project_path(slug)
        await self._post_thought("📦 *Installing dependencies...*")
        proc = await asyncio.create_subprocess_shell(f"cd {project_path} && npm install")
        await proc.wait()
        
        await self._post_thought("🏗️ *Initial work unit...*")
        result = await game_factory.run_work_unit(slug)
        await self._post_thought(result)
        self.units_completed = 1
        self._save_state()
        
        # Deploy Alpha
        await self._ship_project(tag="ALPHA")

    def _add_polish_tasks(self):
        """Auto-inject polish tasks."""
        tasks_file = Path(game_factory._get_project_path(self.active_game_slug)) / "TASKS.md"
        if tasks_file.exists():
            with open(tasks_file, "a") as f:
                f.write("\n- [ ] [POLISH] Refine UI animations\n- [ ] [POLISH] Balance gameplay variables\n- [ ] [POLISH] Add subtle sound effect hooks")

    async def _replan_project(self):
        """Research features mid-way and update the plan (with error resilience)."""
        await self._post_thought(f"🔍 *Halfway point for `{self.active_game_slug}`. Researching innovative features...*")
        
        try:
            # 1. Research
            import sys
            skill_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "AGENT PERSONA SKILL")
            if skill_dir not in sys.path:
                sys.path.insert(0, skill_dir)
                
            from web_access import search_web
            query = f"cool features for a {self.active_game_slug.replace('-', ' ')} video game"
            # search_web is synchronous
            results = search_web(query, max_results=3)
            context = ""
            if results:
                context = "\n".join([f"- {r['title']}: {r['snippet']}" for r in results])
                await self._post_thought(f"💡 *Research found ideas:* {results[0]['title']}")
            
            # 2. Replan
            from ai_coder import ask_coder
            project_path = game_factory._get_project_path(self.active_game_slug)
            tasks_file = project_path / "TASKS.md"
            tasks_content = tasks_file.read_text() if tasks_file.exists() else ""
            
            prompt = f"""We are mid-way through development. Based on this research:
{context}

Please update the remaining TASKS.md list to include one high-impact innovative feature and refine the end goals.
Current Tasks:
{tasks_content}

Return ONLY the updated markdown checklist format.
"""
            new_tasks = await ask_coder(prompt, model="gemini-2.0-flash")
            
            if new_tasks and "- [ ]" in new_tasks:
                tasks_file.write_text(new_tasks)
                await self._post_thought("📝 *Project replanned with new research-backed features!*")
            else:
                await self._post_thought("⚠️ *Replan yielded no changes, moving forward with original plan.*")
                
        except Exception as e:
            await self._post_thought(f"⚠️ *Innovation loop failed: {str(e)[:50]}. Moving forward to avoid blocking.*")
        
        # ALWAYS set this to True once we've attempted it, to prevent infinite loops
        self.has_replanned = True
        self._save_state()

    async def _ship_project(self, tag: str = "UPDATE"):
        """Build, Deploy, and share the project with a milestone tag."""
        await self._post_thought(f"🏁 **[{tag}]** Shipping progress for `{self.active_game_slug}`...")
        
        project_path = game_factory._get_project_path(self.active_game_slug)
        # Build
        await self._post_thought("🏗️ *Building...*")
        build_proc = await asyncio.create_subprocess_shell(f"cd {project_path} && npx vite build")
        await build_proc.wait()
        
        # Deploy (run in executor to avoid blocking Discord heartbeat)
        from netlify_deployer import NetlifyDeployer
        deployer = NetlifyDeployer(str(project_path / "dist"))
        await self._post_thought(f"deploying {tag}...")
        
        loop = asyncio.get_event_loop()
        deploy_result = await loop.run_in_executor(None, lambda: deployer.deploy(production=True))
        
        if deploy_result["status"] == "success" and deploy_result["url"]:
            await self._post_thought(f"🌐 **LIVE [{tag}]:** {deploy_result['url']}")
            self.deploys_today += 1
            if tag in ["RELEASE", "FINAL"]:
                self.active_game_slug = None
                self.units_completed = 0
            self._save_state()
        else:
            await self._post_thought(f"❌ *Deployment {tag} failed:* {deploy_result['logs'][:100]}")

    async def _post_thought(self, message: str):
        """Post internal thought to the thoughts channel."""
        if self.internal_channel:
            try: await self.internal_channel.send(message)
            except: pass
        print(f"[ZOE THOUGHT] {message}")


# Global instance
creative_pipeline: Optional[CreativePipeline] = None

async def start_creative_pipeline(bot):
    """Initialize and start the creative pipeline."""
    global creative_pipeline
    creative_pipeline = CreativePipeline(bot)
    await creative_pipeline.start()
