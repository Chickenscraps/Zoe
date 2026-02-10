
import os
import re
from datetime import datetime
from typing import List, Dict, Optional

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SKILL_DIR, ".."))
PROJECTS_DIR = os.path.join(PROJECT_ROOT, "projects")

TEMPLATE = """# Project: {title}

## Current Understanding
{understanding}

## Decisions
- None yet.

## Open Questions
- None yet.

## Next Actions
- [ ] Initial setup

## Recent Changes
- {date}: Project initialized.

## Artifacts
- None yet.
"""

class ProjectJournal:
    def __init__(self, slug: str):
        self.slug = slug
        self.project_dir = os.path.join(PROJECTS_DIR, slug)
        self.journal_path = os.path.join(self.project_dir, "project_journal.md")
        self._ensure_exists()

    def _ensure_exists(self):
        if not os.path.exists(self.project_dir):
            os.makedirs(self.project_dir)
        
        if not os.path.exists(self.journal_path):
            with open(self.journal_path, "w") as f:
                f.write(TEMPLATE.format(
                    title=self.slug.replace("-", " ").title(),
                    understanding="Initial project setup.",
                    date=datetime.now().strftime("%Y-%m-%d")
                ))

    def read(self) -> str:
        with open(self.journal_path, "r") as f:
            return f.read()

    def get_section(self, section_name: str) -> str:
        """Extract content of a specific section."""
        content = self.read()
        pattern = f"## {section_name}\n(.*?)(?=\n## |$)"
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else ""

    def update_section(self, section_name: str, new_content: str, append: bool = False):
        """Update a specific section."""
        content = self.read()
        pattern = f"(## {section_name}\n)(.*?)(?=\n## |$)"
        
        def replacer(match):
            header = match.group(1)
            old_content = match.group(2)
            if append:
                return f"{header}{old_content}\n{new_content}"
            return f"{header}{new_content}"

        if re.search(pattern, content, re.DOTALL):
            new_full_content = re.sub(pattern, replacer, content, count=1, flags=re.DOTALL)
        else:
            # Section missing, append to end
            new_full_content = f"{content}\n\n## {section_name}\n{new_content}"

        with open(self.journal_path, "w") as f:
            f.write(new_full_content)

    def log_change(self, change: str):
        """Append to Recent Changes with timestamp."""
        entry = f"- {datetime.now().strftime('%Y-%m-%d %H:%M')}: {change}"
        self.update_section("Recent Changes", entry, append=True)

    def get_next_actions(self) -> List[str]:
        """Parse next actions list."""
        content = self.get_section("Next Actions")
        # Find lines starting with - [ ] or - [x]
        actions = []
        for line in content.splitlines():
            if line.strip().startswith("- [ ]"):
                actions.append(line.strip()[6:]) # Remove "- [ ] "
        return actions

if __name__ == "__main__":
    # Test
    pj = ProjectJournal("test-project")
    print("Initial Next Actions:", pj.get_next_actions())
    pj.update_section("Next Actions", "- [ ] Do task A\n- [ ] Do task B")
    print("Updated Next Actions:", pj.get_next_actions())
    pj.log_change("Updated actions list")
    print("Recent Changes:", pj.get_section("Recent Changes"))
