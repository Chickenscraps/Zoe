"""
Project Manager Module
Handles "Project Mode" scaffolding, state tracking, and artifact management.
"""
import os
import json
import shutil
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path

# Base directory for all projects
PROJECTS_ROOT = Path("zoe_projects")
PROJECTS_ROOT.mkdir(exist_ok=True)

logger = logging.getLogger(__name__)

class Project:
    """Represents a managed project."""
    
    def __init__(self, name: str, path: Path, data: Dict[str, Any]):
        self.name = name
        self.path = path
        self.data = data
        
    @property
    def manifest_path(self) -> Path:
        return self.path / "project.json"

    def save(self):
        """Persist project state."""
        self.data["last_update"] = datetime.now().isoformat()
        with open(self.manifest_path, "w") as f:
            json.dump(self.data, f, indent=2)

    def add_log(self, entry: str):
        """Add entry to progress log."""
        log_path = self.path / "ARTIFACTS" / "progress_log.md"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a") as f:
            f.write(f"\n- **{timestamp}**: {entry}")

    def update_task_status(self, task_id: str, status: str):
        """Update a task in TASKS.md (simple string replace for now)."""
        tasks_path = self.path / "TASKS.md"
        if not tasks_path.exists(): return
        
        # This is a naive implementation; a real one would parse markdown
        # Ideally we'd keep tasks in json and render to md
        pass


class ProjectManager:
    """
    Manages project lifecycle: create, load, update.
    """
    
    def create_project(self, name: str, goal: str) -> Project:
        """Initialize a new project with scaffolding."""
        slug = name.lower().replace(" ", "_")
        path = PROJECTS_ROOT / slug
        
        if path.exists():
            raise FileExistsError(f"Project '{slug}' already exists.")
            
        # 1. Create Directory Structure
        path.mkdir()
        (path / "assets").mkdir()
        (path / "src").mkdir()
        (path / "tests").mkdir()
        (path / "scripts").mkdir()
        (path / "docs").mkdir()
        (path / "ARTIFACTS").mkdir()
        
        # 2. Create Documentation Artifacts
        self._create_file(path / "README.md", f"# {name}\n\n**Goal**: {goal}\n\n## Status\nInitialized.")
        self._create_file(path / "PLAN.md", "# Implementation Plan\n\n- [ ] Initial Scoping\n")
        self._create_file(path / "TASKS.md", "# Task List\n\n- [ ] Setup Environment\n")
        self._create_file(path / "ARCHITECTURE.md", "# Architecture\n\nTBD\n")
        self._create_file(path / "DECISIONS.md", "# Decision Log\n\n")
        self._create_file(path / "STYLEGUIDE.md", "# Style Guide\n\n- Python 3.12+\n- Google Docstrings\n")
        self._create_file(path / "CHANGELOG.md", "# Changelog\n\n## 0.1.0\n- Project initialized.\n")
        self._create_file(path / "ARTIFACTS" / "progress_log.md", "# Progress Log\n\n")
        
        # 3. Create Manifest
        manifest_data = {
            "name": name,
            "goal": goal,
            "created_at": datetime.now().isoformat(),
            "last_update": datetime.now().isoformat(),
            "status": "active",
            "milestones": [],
            "current_state": "initialization",
            "model_budget": 0.0,  # Placeholder
            "next_tasks": ["Setup Environment"]
        }
        
        with open(path / "project.json", "w") as f:
            json.dump(manifest_data, f, indent=2)
            
        return Project(name, path, manifest_data)

    def load_project(self, name_or_slug: str) -> Optional[Project]:
        """Load an existing project."""
        # Try exact slug match
        path = PROJECTS_ROOT / name_or_slug
        if path.exists():
            return self._load_from_path(path)
        
        # Search by name in manifests
        for p in PROJECTS_ROOT.iterdir():
            if not p.is_dir(): continue
            proj = self._load_from_path(p)
            if proj and proj.name.lower() == name_or_slug.lower():
                return proj
                
        return None

    def _load_from_path(self, path: Path) -> Optional[Project]:
        manifest = path / "project.json"
        if not manifest.exists(): return None
        try:
            with open(manifest, "r") as f:
                data = json.load(f)
            return Project(data.get("name"), path, data)
        except:
            return None

    def _create_file(self, path: Path, content: str):
        with open(path, "w") as f:
            f.write(content)

    def list_projects(self) -> List[str]:
        """Return list of project names."""
        projects = []
        for p in PROJECTS_ROOT.iterdir():
            if p.is_dir() and (p / "project.json").exists():
                projects.append(p.name)
        return projects

# Singleton
project_manager = ProjectManager()
