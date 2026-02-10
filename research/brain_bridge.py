import asyncio
import random
from typing import Optional, Dict, Any
from task_planner import plan_and_execute, TaskPlan, StepStatus, get_default_tools
from database import MoodRepository, MessageRepository
from persona_loader import get_system_prompt
from database_tool import get_or_create_user, get_memories, add_memory, log_journal
from memory_engine import memory_engine

class BrainBridge:
    def __init__(self):
        self.last_plan: Optional[TaskPlan] = None
        self.current_thought_loop = None

    async def generate_nudge_plan(self, heat_score: float, boredom_level: int = 0) -> Optional[dict]:
        """
        Generate a "Social Soul" thought.
        Not a "nudge", but an "artifact of presence".
        """
        # 1. Sense: Check Mood & Social Context
        mood_data = MoodRepository.get_trend("group_general") 
        mood = mood_data.get("dominant_tone", "neutral")
        
        # 2. Memory: Get an Archetype (The "Dream")
        social_context = memory_engine.get_social_context()
        
        # 3. Decision: To Speak or Build?
        # If heat is low (silence), we build something.
        # If heat is high, we might just comment.
        
        if random.random() < 0.3:
            # Build Mode - Use Planner
            goal = f"Design a conceptual tool based on '{social_context}'. Describe it like a memory."
            return await self._execute_build_plan(goal, social_context)
        else:
            # Thought Mode - Direct LLM (No Planner Risk)
            return await self._generate_direct_thought(social_context, mood)

    async def _generate_direct_thought(self, context: str, mood: str) -> Optional[dict]:
        """Generate a thought directly via LLM (bypassing tool planner to avoid leaks)."""
        import ollama
        
        system_prompt = get_system_prompt(f"Context: {context}\nMood: {mood}")
        
        prompt = f"""
        TASK: Formulate a single, short thought about '{context}'.
        
        CONSTRAINTS:
        1. Max 1-2 sentences.
        2. Cryptic, insightful, or witty. "Quiet genius" vibe.
        3. Do NOT mention you are an AI.
        4. Lowercase style preferred.
        """
        
        try:
            response = await asyncio.to_thread(
                ollama.chat,
                model="llama3.1:8b-instruct-q8_0",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            content = response["message"]["content"].strip()
            
            # Post-processing to remove quotes if added
            if content.startswith('"') and content.endswith('"'):
                content = content[1:-1]
                
            return {
                "text": content,
                "urgent": False,
                "type": "thought"
            }
        except Exception as e:
            print(f"🧠 Thought Gen Failed: {e}")
            return None

    async def _execute_build_plan(self, goal: str, context: str) -> Optional[dict]:
        """Use Direct LLM for design tasks (Planner is too risky for creative prompts)."""
        import ollama
        
        system_prompt = get_system_prompt(f"Context: {context}")
        
        prompt = f"""
        TASK: {goal}
        
        CONSTRAINTS:
        1. Output ONLY the description of the tool/concept.
        2. Keep it abstract, high-level, and 'dream-like'.
        3. Max 3 sentences.
        4. Lowercase style.
        """
        
        try:
            response = await asyncio.to_thread(
                ollama.chat,
                model="llama3.1:8b-instruct-q8_0",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            content = response["message"]["content"].strip()
            
            # Post-processing
            if content.startswith('"') and content.endswith('"'):
                content = content[1:-1]
                
            return {
                "text": f"_{content}_", 
                "urgent": False,
                "type": "build"
            }
        except Exception as e:
            print(f"🧠 Build Gen Failed: {e}")
            return None

    async def analyze_topic(self, topic: str) -> Optional[dict]:
        """Force-analyze a topic (User Command) - Zoe style."""
        goal = f"Deconstruct '{topic}' through the lens of a paranoid system administrator."
        try:
            plan = await plan_and_execute(goal)
            return {
                "text": f"{plan.final_result}",
                "urgent": False, 
                "plan_id": plan.id,
                "image_path": None
            }
        except Exception as e:
            return {"text": f"Error: {e}", "urgent": False}

# Singleton
brain = BrainBridge()
