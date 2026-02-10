
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Optional

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSTREAMS_FILE = os.path.join(SKILL_DIR, "workstreams.json")

DEFAULT_WORKSTREAMS = {
    "PRIMARY": {
        "title": "Ops & Improvements",
        "goal": "Maintain system health and improve agent capabilities.",
        "owner": "system",
        "next_actions": ["Review recent logs", "Check system health", "Groom idea vault"],
        "blockers": [],
        "last_progress": "",
        "artifacts": [],
        "risk_level": "LOW",
        "approval_required": False
    },
    "SECONDARY": {},
    "CREATIVE": {},
    "WORLD_CONTEXT": {
        "title": "World Intelligence",
        "goal": "Stay informed on tech, gaming, and markets.",
        "owner": "system",
        "next_actions": ["Check HN", "Check Reuters", "Summarize findings"],
        "blockers": [],
        "last_progress": "",
        "artifacts": [],
        "risk_level": "LOW",
        "approval_required": False
    },
    "MAINTENANCE": {
        "title": "System Maintenance",
        "goal": "Ensure optimal agent performance.",
        "owner": "system",
        "next_actions": ["Rotate logs", "Compact memory", "Check connection"],
        "blockers": [],
        "last_progress": "",
        "artifacts": [],
        "risk_level": "LOW",
        "approval_required": False
    }
}

class WorkstreamManager:
    def __init__(self):
        self.workstreams = self._load_workstreams()

    def _load_workstreams(self) -> Dict:
        try:
            with open(WORKSTREAMS_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return DEFAULT_WORKSTREAMS.copy()

    def _save_workstreams(self):
        with open(WORKSTREAMS_FILE, "w") as f:
            json.dump(self.workstreams, f, indent=2)

    def get_workstream(self, slot: str) -> Dict:
        return self.workstreams.get(slot, {})

    def update_workstream(self, slot: str, updates: Dict):
        if slot not in self.workstreams:
            self.workstreams[slot] = {}
        
        self.workstreams[slot].update(updates)
        self.workstreams[slot]["last_updated"] = datetime.now().isoformat()
        self._save_workstreams()

    def set_focus(self, slot: str, title: str, goal: str):
        self.update_workstream(slot, {
            "title": title,
            "goal": goal,
            "params": {"active": True}
        })

    def log_progress(self, slot: str, progress: str):
        if slot in self.workstreams:
            self.workstreams[slot]["last_progress"] = f"{datetime.now().isoformat()}: {progress}"
            self._save_workstreams()

    def _sync_tasks_from_file(self, slot: str) -> bool:
        """Auto-refill next_actions from project TASKS.md if queue is empty."""
        ws = self.workstreams.get(slot, {})
        artifacts = ws.get("artifacts", [])
        
        # Try to find TASKS.md in project paths
        import os
        import re
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        tasks_paths = [
            os.path.join(project_root, "projects", "botanica-wars", "TASKS.md"),
            os.path.join(project_root, "zoe_projects", "botanica_wars", "TASKS.md"),
        ]
        
        for tasks_path in tasks_paths:
            if os.path.exists(tasks_path):
                try:
                    with open(tasks_path, "r") as f:
                        content = f.read()
                    # Parse unchecked tasks: - [ ] Task name
                    unchecked = re.findall(r"- \[ \] (.+)", content)
                    if unchecked:
                        self.workstreams[slot]["next_actions"] = unchecked[:15]  # Max 15
                        self._save_workstreams()
                        return True
                except Exception:
                    pass
        return False

    def get_next_action(self, slot: str) -> Optional[str]:
        ws = self.workstreams.get(slot, {})
        actions = ws.get("next_actions", [])
        
        # Auto-refill if empty
        if not actions:
            if self._sync_tasks_from_file(slot):
                actions = self.workstreams.get(slot, {}).get("next_actions", [])
        
        return actions[0] if actions else None

    def pop_next_action(self, slot: str) -> Optional[str]:
        ws = self.workstreams.get(slot, {})
        actions = ws.get("next_actions", [])
        if actions:
            action = actions.pop(0)
            self._save_workstreams()
            return action
        return None

    def add_next_action(self, slot: str, action: str):
        if slot not in self.workstreams:
            return
        if "next_actions" not in self.workstreams[slot]:
            self.workstreams[slot]["next_actions"] = []
        
        if action not in self.workstreams[slot]["next_actions"]:
            self.workstreams[slot]["next_actions"].append(action)
            self._save_workstreams()
            
    def get_all_active(self) -> Dict:
        return {k: v for k, v in self.workstreams.items() if v.get("title")}

# Singleton
workstream_manager = WorkstreamManager()

if __name__ == "__main__":
    # Test
    print("Workstreams:", json.dumps(workstream_manager.get_all_active(), indent=2))
    workstream_manager.log_progress("PRIMARY", "Test progress log")
