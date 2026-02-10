
import os
from datetime import datetime

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SKILL_DIR, ".."))
PROJECTS_DIR = os.path.join(PROJECT_ROOT, "projects")
VAULT_FILE = os.path.join(PROJECTS_DIR, "idea_vault.md")

class IdeaVault:
    def __init__(self):
        self._ensure_exists()

    def _ensure_exists(self):
        if not os.path.exists(PROJECTS_DIR):
            os.makedirs(PROJECTS_DIR)
        
        if not os.path.exists(VAULT_FILE):
            with open(VAULT_FILE, "w", encoding="utf-8") as f:
                f.write("# 🧠 Idea Vault\n\n| Date | Idea | Why | Feasibility | Next Steps | Status |\n|---|---|---|---|---|---|\n")

    def add_idea(self, title, why, feasibility="Medium", next_steps="TBD"):
        date = datetime.now().strftime("%Y-%m-%d")
        row = f"| {date} | {title} | {why} | {feasibility} | {next_steps} | New |\n"
        
        with open(VAULT_FILE, "a", encoding="utf-8") as f:
            f.write(row)
        return True

    def get_ideas(self):
        with open(VAULT_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        ideas = []
        for line in lines:
            if line.startswith("|") and not line.startswith("| Date"):
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 7:
                    ideas.append({
                        "date": parts[1],
                        "title": parts[2],
                        "why": parts[3],
                        "status": parts[6]
                    })
        return ideas

# Singleton
idea_vault = IdeaVault()

if __name__ == "__main__":
    idea_vault.add_idea("Test Idea", "Testing the vault", "High", "Check file")
