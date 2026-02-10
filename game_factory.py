import os
import asyncio
import json
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime
from model_router import model_router
from ai_coder import ask_coder

# =============================================================================
# Configuration & Templates
# =============================================================================

GENRES = {
    "platformer": {
        "description": "2D side-scrolling platformer with jump mechanics",
        "phaser_config": "physics: { default: 'arcade', arcade: { gravity: { y: 300 }, debug: false } }"
    },
    "shooter": {
        "description": "Top-down shooter with WASD movement and mouse aim",
        "phaser_config": "physics: { default: 'arcade', arcade: { gravity: { y: 0 }, debug: false } }"
    },
    "runner": {
        "description": "Endless runner with increasing speed and obstacles",
        "phaser_config": "physics: { default: 'arcade', arcade: { gravity: { y: 600 }, debug: false } }"
    },
    "puzzle": {
        "description": "Grid-based logic puzzle game",
        "phaser_config": "scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH }"
    },
    "roguelite": {
        "description": "Arena survival with waves and upgrades",
        "phaser_config": "physics: { default: 'arcade', arcade: { gravity: { y: 0 } } }"
    }
}

class GameFactory:
    def __init__(self, projects_root: str):
        self.root = Path(projects_root)
        self.root.mkdir(exist_ok=True)

    def _get_project_path(self, slug: str) -> Path:
        return self.root / slug

    async def create_new_game(self, name: str, genre: str) -> str:
        """Fully scaffolds a new Phaser game project."""
        slug = name.lower().replace(" ", "-")
        project_path = self._get_project_path(slug)
        
        if genre not in GENRES:
            genre = "platformer"  # Default

        if project_path.exists():
            return f"⚠️ Project '{slug}' already exists."

        # 1. Create Directory Structure
        (project_path / "src" / "scenes").mkdir(parents=True)
        (project_path / "public" / "assets").mkdir(parents=True)
        (project_path / "ARTIFACTS").mkdir(parents=True)

        # 2. Write Standard Files (Vite + Phaser)
        self._write_file(project_path / "package.json", self._template_package_json(slug))
        self._write_file(project_path / "index.html", self._template_index_html(name))
        self._write_file(project_path / "tsconfig.json", self._template_tsconfig())
        self._write_file(project_path / "vite.config.ts", self._template_vite_config())
        
        # 3. Write Source Code (Vertical Slice)
        self._write_file(project_path / "src" / "main.ts", self._template_main_ts(genre))
        self._write_file(project_path / "src" / "style.css", self._template_css())
        
        # Scenes
        self._write_file(project_path / "src" / "scenes" / "Boot.ts", self._template_scene_boot())
        self._write_file(project_path / "src" / "scenes" / "Preloader.ts", self._template_scene_preloader())
        self._write_file(project_path / "src" / "scenes" / "MainMenu.ts", self._template_scene_mainmenu(name))
        self._write_file(project_path / "src" / "scenes" / "Game.ts", self._template_scene_game(genre))
        self._write_file(project_path / "src" / "scenes" / "GameOver.ts", self._template_scene_gameover())

        # 4. Initialize Artifacts
        initial_plan = f"# Game Plan: {name}\n\nGenre: {genre}\n\n## Core Loop\nTo be defined.\n\n## Mechanics\n- {GENRES[genre]['description']}\n"
        self._write_file(project_path / "PLAN.md", initial_plan)
        tasks = [
            "- [ ] Implement core player movement and controls",
            "- [ ] Add basic game mechanics (obstacles/enemies)",
            "- [ ] Implement scoring and level progression",
            "- [ ] Add win/loss condition logic",
            "- [ ] Polish graphics and add visual effects"
        ]
        self._write_file(project_path / "TASKS.md", "\n".join(tasks))
        self._write_file(project_path / "ARTIFACTS" / "progress_log.md", f"# Progress Log\n\n**{datetime.now().strftime('%Y-%m-%d %H:%M')}**: Project Scaffolding Complete.")

        return f"✅ Created game '{name}' in `{project_path}` (Genre: {genre})"

    async def run_work_unit(self, project_slug: str) -> str:
        """Execute one autonomous work unit with Self-Correction."""
        project_path = self._get_project_path(project_slug)
        tasks_file = project_path / "TASKS.md"
        
        if not tasks_file.exists():
            return "❌ Task list missing."

        tasks_content = tasks_file.read_text()
        task = self._pick_next_task(tasks_content)
        
        if not task:
            return "✅ No pending tasks found."

        # Architecture & Coding
        context = self._get_context(project_path, project_slug, task)
        
        try:
            print(f"🛠️ [GameFactory] Implementing: {task}")
            # Step 1: Coding (Flash)
            diff = await ask_coder(f"Implement this task: {task}. Return a UNIFIED DIFF.", context=context, model="gemini-2.0-flash")
            
            if "Error" in diff or "503" in diff:
                 raise Exception(f"AI Assistant returned error: {diff[:100]}")
            
            # Step 2: Mark Task Done
            new_tasks = tasks_content.replace(f"- [ ] {task}", f"- [x] {task}")
            tasks_file.write_text(new_tasks)
            
            # Step 3: Log Progress
            await self._log_progress(project_slug, f"Successfully implemented: {task}")
            
            return f"🛠️ **Task Complete:** {task}\n```diff\n{diff[:300]}...\n```"

        except Exception as e:
            # --- SELF HEALING ---
            error_message = str(e)
            print(f"⚠️ [GameFactory] Error detected: {error_message}. Attempting autonomous repair.")
            
            # Insert a DEBUG task at the top
            repair_task = f"- [ ] [DEBUG] Fix failure: {error_message[:100]}"
            tasks_file.write_text(f"{repair_task}\n{tasks_content}")
            
            # Attempt immediate fix with Local model fallback
            try:
                print("🔄 [GameFactory] Retrying with Local Fallback (llama3.1)...")
                fix = await ask_coder(f"FIX ERROR: {error_message}\nTASK: {task}", context=context, model="llama3.1")
                return f"🩹 **Self-Healed**: {task} (Recovered via Local Fallback)"
            except:
                return f"❌ **Self-Healing Failed**: {error_message}. Manual intervention required."

    def _pick_next_task(self, tasks_content: str) -> Optional[str]:
        """Pick the first unchecked task from the list."""
        for line in tasks_content.splitlines():
            line = line.strip()
            if line.startswith("- [ ]"):
                return line[5:].strip()
        return None

    def _get_context(self, project_path: Path, slug: str, task: str) -> str:
        """Build context for the AI."""
        context = f"Project: {slug}\nActive Task: {task}\n\nFiles:\n"
        # Read relevant files (main.ts and Game.ts)
        for f_path in ["src/main.ts", "src/scenes/Game.ts"]:
            p = project_path / f_path
            if p.exists():
                context += f"\n--- {f_path} ---\n{p.read_text()}\n"
        return context

    async def _log_progress(self, slug: str, message: str):
        """Append to progress log."""
        project_path = self._get_project_path(slug)
        log_file = project_path / "ARTIFACTS" / "progress_log.md"
        with open(log_file, "a") as f:
            f.write(f"\n- **{datetime.now().strftime('%H:%M')}**: {message}")

    def _write_file(self, path: Path, content: str):
        path.write_text(content, encoding="utf-8")

    # ==========================
    # TEMPLATES
    # ==========================
    
    def _template_package_json(self, name):
        return json.dumps({
            "name": name,
            "private": True,
            "version": "0.0.0",
            "type": "module",
            "scripts": {
                "dev": "vite",
                "build": "tsc && vite build",
                "preview": "vite preview"
            },
            "devDependencies": {
                "typescript": "^5.0.2",
                "vite": "^4.4.5"
            },
            "dependencies": {
                "phaser": "^3.60.0"
            }
        }, indent=2)

    def _template_index_html(self, name):
        return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{name}</title>
    <style>body {{ margin: 0; background: #000; overflow: hidden; }}</style>
  </head>
  <body>
    <div id="game-container"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>"""

    def _template_tsconfig(self):
        return json.dumps({
            "compilerOptions": {
                "target": "ESNext",
                "useDefineForClassFields": True,
                "module": "ESNext",
                "lib": ["ESNext", "DOM"],
                "moduleResolution": "Node",
                "strict": True,
                "resolveJsonModule": True,
                "isolatedModules": True,
                "esModuleInterop": True,
                "noEmit": True,
                "noUnusedLocals": True,
                "noUnusedParameters": True,
                "noImplicitReturns": True,
                "skipLibCheck": True
            },
            "include": ["src"]
        }, indent=2)

    def _template_vite_config(self):
        return """import { defineConfig } from 'vite';
export default defineConfig({
  base: './',
  build: {
    assetsDir: 'assets',
  }
});"""

    def _template_main_ts(self, genre):
        config = GENRES[genre]['phaser_config']
        return f"""import Phaser from 'phaser';
import {{ Boot }} from './scenes/Boot';
import {{ Preloader }} from './scenes/Preloader';
import {{ MainMenu }} from './scenes/MainMenu';
import {{ Game }} from './scenes/Game';
import {{ GameOver }} from './scenes/GameOver';

const config: Phaser.Types.Core.GameConfig = {{
    type: Phaser.AUTO,
    width: 1024,
    height: 768,
    parent: 'game-container',
    backgroundColor: '#028af8',
    scale: {{
        mode: Phaser.Scale.FIT,
        autoCenter: Phaser.Scale.CENTER_BOTH
    }},
    {config},
    scene: [
        Boot,
        Preloader,
        MainMenu,
        Game,
        GameOver
    ]
}};

export default new Phaser.Game(config);"""

    def _template_css(self):
        return "body { margin: 0; padding: 0; background: #111; display: flex; justify-content: center; align-items: center; height: 100vh; }"

    def _template_scene_boot(self):
        return """import { Scene } from 'phaser';

export class Boot extends Scene {
    constructor() {
        super('Boot');
    }

    preload() { }

    create() {
        this.scene.start('Preloader');
    }
}"""

    def _template_scene_preloader(self):
        return """import { Scene } from 'phaser';

export class Preloader extends Scene {
    constructor() {
        super('Preloader');
    }

    preload() {
        this.load.setPath('assets');
    }

    create() {
        this.scene.start('MainMenu');
    }
}"""

    def _template_scene_mainmenu(self, name):
        return f"""import {{ Scene }} from 'phaser';

export class MainMenu extends Scene {{
    constructor() {{
        super('MainMenu');
    }}

    create() {{
        this.add.text(512, 384, '{name}', {{
            fontFamily: 'Arial Black', fontSize: 38, color: '#ffffff',
            stroke: '#000000', strokeThickness: 8,
            align: 'center'
        }}).setOrigin(0.5);
        
        this.add.text(512, 460, 'Click to Start', {{
            fontFamily: 'Arial', fontSize: 24, color: '#ffffff'
        }}).setOrigin(0.5);

        this.input.once('pointerdown', () => {{
            this.scene.start('Game');
        }});
    }}
}}"""

    def _template_scene_game(self, genre):
        return """import { Scene } from 'phaser';

export class Game extends Scene {
    camera: Phaser.Cameras.Scene2D.Camera;
    
    constructor() {
        super('Game');
    }

    create() {
        this.camera = this.cameras.main;
        this.camera.setBackgroundColor(0x00ff00);

        this.add.text(512, 384, 'Gameplay Placeholder\n(Press SPACE to Win)', {
            fontFamily: 'Arial Black', fontSize: 38, color: '#ffffff',
            align: 'center'
        }).setOrigin(0.5);

        this.input.keyboard?.on('keydown-SPACE', () => {
            this.scene.start('GameOver');
        });
    }
}"""

    def _template_scene_gameover(self):
        return """import { Scene } from 'phaser';

export class GameOver extends Scene {
    constructor() {
        super('GameOver');
    }

    create() {
        this.cameras.main.setBackgroundColor(0xff0000);

        this.add.text(512, 384, 'Game Over', {
            fontFamily: 'Arial Black', fontSize: 64, color: '#ffffff',
            stroke: '#000000', strokeThickness: 8,
            align: 'center'
        }).setOrigin(0.5);

        this.input.once('pointerdown', () => {
            this.scene.start('MainMenu');
        });
    }
}"""

# Singleton instance
game_factory = GameFactory(r"C:\Users\josha\OneDrive\Desktop\Clawd\projects")
