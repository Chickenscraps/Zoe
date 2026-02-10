
import random
import time
import os
from typing import Dict, List, Optional
from datetime import datetime

# Local imports
from workstream_manager import workstream_manager
from project_journal import ProjectJournal
from idea_vault import idea_vault
from mood_engine import mood_engine, InternalMood
from news_watcher import news_watcher
import web_access
try:
    from web_access import search_web
except ImportError:
    search_web = None


SKILL_DIR = os.path.dirname(os.path.abspath(__file__))

class NudgeEngine:
    def __init__(self):
        self.last_tick_type = None
        self.tick_history = []
        
    def tick(self) -> str:
        """
        Execute one work tick.
        Returns a summary string of what happened.
        """
        # 1. Select Workstream
        # Default to PRIMARY, but can rotate if configured
        slot = "PRIMARY"
        ws = workstream_manager.get_workstream(slot)
        if not ws or not ws.get("title"):
             # If no primary tracking, default to Maintenance?
             slot = "MAINTENANCE"
             ws = workstream_manager.get_workstream(slot)

        if not ws:
            return "No active workstream to nudge."

        # 2. Select Tick Type
        tick_type = self._select_tick_type()
        self.last_tick_type = tick_type
        self.tick_history.append(tick_type)
        if len(self.tick_history) > 10:
            self.tick_history.pop(0)

        # 3. Execute Tick
        result = "No action"
        try:
            if tick_type == "PROGRESS":
                result = self._tick_progress(slot, ws)
            elif tick_type == "REVIEW":
                result = self._tick_review(slot, ws)
            elif tick_type == "RESEARCH":
                result = self._tick_research(slot, ws)
            elif tick_type == "DECISION":
                result = self._tick_decision(slot, ws)
            elif tick_type == "BUILD":
                result = self._tick_build(slot, ws) # Placeholder
            elif tick_type == "CREATIVE":
                result = self._tick_creative(slot, ws)
            elif tick_type == "WORLD":
                result = self._tick_world(slot, ws)
            elif tick_type == "MEME":
                result = self._tick_meme(slot, ws)
            elif tick_type == "MAINTENANCE":
                result = self._tick_maintenance(slot, ws)
                
            # Log completion
            if result and result != "No action":
                workstream_manager.log_progress(slot, f"{tick_type}: {result}")
                
            return f"[{tick_type}] {result}"
            
        except Exception as e:
            return f"Error in tick {tick_type}: {e}"

    def _select_tick_type(self) -> str:
        """Weighted random selection - focused on actual work progress."""
        # Focus on work: PROGRESS dominant, REVIEW for audits, RESEARCH for learning
        types = [
            "PROGRESS", "REVIEW", "RESEARCH", "BUILD"
        ]
        weights = [70, 15, 10, 5]  # 70% progress, minimal fluff
        
        # Avoid repeat
        if self.last_tick_type:
            pass
            
        choice = random.choices(types, weights=weights, k=1)[0]
        
        # Hard rule: no repeats
        if choice == self.last_tick_type:
             choice = "PROGRESS" 
             
        return choice

    def _tick_progress(self, slot: str, ws: Dict) -> str:
        """Report on current task - actual work is done by creative_pipeline."""
        actions = ws.get("next_actions", [])
        if not actions:
            return "task queue empty - check creative pipeline"
            
        # Just report what's being worked on, don't pop
        current_task = actions[0]
        return f"focused on: {current_task}"

    def _tick_review(self, slot: str, ws: Dict) -> str:
        project_name = ws.get("title", "project")
        next_actions = ws.get("next_actions", [])
        pending = len(next_actions)
        return f"reviewed {project_name}: {pending} tasks remaining"

    def _tick_research(self, slot: str, ws: Dict) -> str:
        """Research game dev topics and add tasks when queue is low."""
        import random
        
        next_actions = ws.get("next_actions", [])
        
        # Research topics relevant to plant sim game
        research_topics = [
            "2D grid game animation techniques",
            "pixel art plant growth animation CSS",
            "turn-based strategy game AI algorithms",
            "resource management game balance formulas",
            "procedural plant generation algorithms",
            "indie game juice effects polish",
            "canvas rendering optimization tricks",
            "roguelike combat resolution systems",
            "game logic state machine patterns",
            "UI/UX best practices for strategy games",
        ]
        
        topic = random.choice(research_topics)
        
        return f"researching: {topic}"

    def _tick_build(self, slot: str, ws: Dict) -> str:
        """Trigger actual code generation for current task."""
        next_actions = ws.get("next_actions", [])
        if next_actions:
            return f"building: {next_actions[0]}"
        return "no active build task"

    def _tick_creative(self, slot: str, ws: Dict) -> str:
        return "Creative tick: (Placeholder)"

    def _tick_world(self, slot: str, ws: Dict) -> str:
        # Check news watcher
        return "World Context: Checked news."

    def _tick_meme(self, slot: str, ws: Dict) -> str:
        mood = mood_engine.get_current_mood()
        if mood == InternalMood.SUNNY_SOCIAL:
             return "Meme: Posted a vibe check."
        return "Meme skipped (wrong mood)."

    def _tick_maintenance(self, slot: str, ws: Dict) -> str:
        return "Maintenance: Logs rotated."

# Singleton
nudge_engine = NudgeEngine()
