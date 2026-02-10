import uuid
from datetime import datetime
from typing import List
from database import Goal, GoalRepository

class GoalEngine:
    def __init__(self):
        pass

    def get_current_obsessions(self) -> str:
        """Return a formatted string of active goals for the prompt."""
        goals = GoalRepository.get_active()
        if not goals:
            return "Current Obsession: Finding a purpose."
        
        return "\n".join([f"- [Obsession] {g.description}" for g in goals])

    def add_goal(self, description: str, priority: int = 1):
        """Add a new obsession."""
        goal = Goal(
            id=str(uuid.uuid4()),
            description=description,
            status="active",
            priority=priority,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat()
        )
        GoalRepository.upsert(goal)

    def complete_goal(self, description_partial: str):
        """Mark a goal as complete if it matches."""
        goals = GoalRepository.get_active()
        for g in goals:
            if description_partial.lower() in g.description.lower():
                g.status = "completed"
                g.updated_at = datetime.now().isoformat()
                GoalRepository.upsert(g)
                return f"Completed: {g.description}"
        return "Goal not found."

goal_engine = GoalEngine()
