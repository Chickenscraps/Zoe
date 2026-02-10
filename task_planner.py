"""
Task Planner Module
ReAct-style multi-turn planning for complex tasks.
"""
import os
import json
import asyncio
import uuid
import re
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any, Callable
from enum import Enum

from model_router import model_router

# ============================================================================
# Data Models
# ============================================================================

class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class PlanStatus(Enum):
    PLANNING = "planning"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class TaskStep:
    """A single step in a task plan."""
    id: str
    description: str
    tool: str
    args: Dict[str, Any]
    status: StepStatus = StepStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "tool": self.tool,
            "args": self.args,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "depends_on": self.depends_on
        }

@dataclass
class TaskPlan:
    """A multi-step plan for achieving a goal."""
    id: str
    goal: str
    steps: List[TaskStep]
    status: PlanStatus = PlanStatus.PLANNING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    final_result: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status.value,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "final_result": self.final_result
        }

# ============================================================================
# Task Decomposition (LLM-Powered)
# ============================================================================

DECOMPOSITION_PROMPT = """You are a task planner. Break down the user's goal into concrete steps.

Available tools:
- search_web(query): Search the web for information
- read_url(url): Read content from a URL
- read_file(path): Read a local file
- write_file(path, content): Write content to a file
- get_news(): Get latest news headlines
- get_weather(location): Get weather for a location
- memory_recall(query): Search Zoe's memory for relevant info

Rules:
1. Each step should use ONE tool
2. Steps can depend on previous steps (use step IDs)
3. Be concise but specific
4. Maximum 5 steps for most tasks

Output JSON array:
[
  {"id": "1", "description": "Search for X", "tool": "search_web", "args": {"query": "X"}, "depends_on": []},
  {"id": "2", "description": "Read the top result", "tool": "read_url", "args": {"url": "{{result_1}}"}, "depends_on": ["1"]}
]

Goal: {goal}

JSON plan:"""

async def decompose_task(goal: str, model: str = "gemini-2.0-flash-lite") -> TaskPlan:
    """
    Use LLM to decompose a complex goal into executable steps.
    """
    plan_id = str(uuid.uuid4())[:8]
    
    try:
        # Run async model call via router
        content = await model_router.chat(
            messages=[{"role": "user", "content": DECOMPOSITION_PROMPT.format(goal=goal)}],
            system="You are a task planning assistant. Output only valid JSON.",
            model=model
        )
        
        # Extract JSON from response
        json_match = re.search(r'\[[\s\S]*\]', content)
        if not json_match:
            raise ValueError("No JSON array found in response")
        
        steps_data = json.loads(json_match.group())
        
        steps = []
        for s in steps_data:
            step = TaskStep(
                id=s.get("id", str(uuid.uuid4())[:4]),
                description=s.get("description", ""),
                tool=s.get("tool", ""),
                args=s.get("args", {}),
                depends_on=s.get("depends_on", [])
            )
            steps.append(step)
        
        return TaskPlan(
            id=plan_id,
            goal=goal,
            steps=steps,
            status=PlanStatus.PLANNING
        )
        
    except Exception as e:
        # Return a minimal plan on error instead of crashing
        return TaskPlan(
            id=plan_id,
            goal=goal,
            steps=[
                TaskStep(
                    id="1",
                    description=f"Execute goal directly (Fallback): {goal}",
                    tool="search_web",
                    args={"query": goal}
                )
            ],
            status=PlanStatus.PLANNING
        )

# ============================================================================
# Plan Execution (ReAct Loop)
# ============================================================================

class PlanExecutor:
    """Execute a task plan using ReAct pattern."""
    
    def __init__(self, tool_registry: Dict[str, Callable] = None):
        self.tool_registry = tool_registry or {}
        self.step_results: Dict[str, str] = {}
    
    def register_tool(self, name: str, func: Callable):
        """Register a tool function."""
        self.tool_registry[name] = func
    
    def _resolve_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Replace {{result_X}} placeholders with actual results."""
        resolved = {}
        for key, value in args.items():
            if isinstance(value, str) and "{{result_" in value:
                # Extract step ID and replace with result
                match = re.search(r'\{\{result_(\w+)\}\}', value)
                if match:
                    step_id = match.group(1)
                    if step_id in self.step_results:
                        resolved[key] = self.step_results[step_id]
                    else:
                        resolved[key] = value
                else:
                    resolved[key] = value
            else:
                resolved[key] = value
        return resolved
    
    def _check_dependencies(self, step: TaskStep) -> bool:
        """Check if all dependencies are completed."""
        for dep_id in step.depends_on:
            if dep_id not in self.step_results:
                return False
        return True
    
    async def execute_step(self, step: TaskStep) -> TaskStep:
        """Execute a single step (Action phase of ReAct)."""
        step.status = StepStatus.RUNNING
        
        try:
            # Resolve arguments with previous results
            resolved_args = self._resolve_args(step.args)
            
            # Get tool function
            tool_func = self.tool_registry.get(step.tool)
            if not tool_func:
                step.status = StepStatus.FAILED
                step.error = f"Tool '{step.tool}' not found"
                return step
            
            # Execute tool (Action)
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func(**resolved_args)
            else:
                result = tool_func(**resolved_args)
            
            # Observe result
            step.result = str(result)[:2000]  # Truncate long results
            step.status = StepStatus.COMPLETED
            self.step_results[step.id] = step.result
            
        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
        
        return step
    
    async def execute_plan(
        self, 
        plan: TaskPlan, 
        progress_callback: Callable[[TaskStep], None] = None
    ) -> TaskPlan:
        """
        Execute all steps in a plan.
        """
        plan.status = PlanStatus.EXECUTING
        
        # Execute steps in order, respecting dependencies
        pending = list(plan.steps)
        max_iterations = len(pending) * 2  # Prevent infinite loops
        iterations = 0
        
        while pending and iterations < max_iterations:
            iterations += 1
            
            # Find next executable step
            for step in pending[:]:
                if self._check_dependencies(step):
                    # Execute step
                    await self.execute_step(step)
                    pending.remove(step)
                    
                    # Report progress
                    if progress_callback:
                        progress_callback(step)
                    
                    # Small delay between steps
                    await asyncio.sleep(0.1)
                    break
            else:
                if pending:
                    # Skip steps with unmet dependencies
                    for step in pending:
                        step.status = StepStatus.SKIPPED
                        step.error = "Unmet dependencies"
                    break
        
        # Determine final status
        failed_steps = [s for s in plan.steps if s.status == StepStatus.FAILED]
        if failed_steps:
            plan.status = PlanStatus.FAILED
        else:
            plan.status = PlanStatus.COMPLETED
        
        plan.completed_at = datetime.now().isoformat()
        
        # Build final result summary
        results = []
        for step in plan.steps:
            if step.result:
                results.append(f"**{step.description}**: {step.result[:200]}")
        plan.final_result = "\n".join(results) if results else "No results"
        
        return plan

# ============================================================================
# Default Tool Registry
# ============================================================================

def get_default_tools() -> Dict[str, Callable]:
    """Get default tool implementations."""
    from tool_maps import read_url, search_web, github_tool, netlify_tool, supabase_tool
    from news_fetcher import get_news_summary
    
    async def memory_recall(query: str) -> str:
        """Search Zoe's memory."""
        try:
            from database_tool import get_memories
            results = get_memories("global_context", limit=5)
            return "\n".join([f"- {m['content']}" for m in results])
        except Exception as e:
            return f"Memory search failed: {e}"
    
    async def write_file_safe(path: str, content: str) -> str:
        """Write file with safety checks."""
        # Only allow writing to safe directories
        if not path.startswith("C:\\Users"): # Basic safety
             return "Write blocked: unsafe path"
        
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"Written to {path}"
        except Exception as e:
            return f"Write failed: {e}"
    
    return {
        "search_web": search_web,
        "read_url": read_url,
        "get_news": lambda: get_news_summary(),
        "memory_recall": memory_recall,
        "write_file": write_file_safe,
        "github_tool": github_tool,
        "netlify_tool": netlify_tool,
        "supabase_tool": supabase_tool
    }

# ============================================================================
# High-Level API
# ============================================================================

async def plan_and_execute(
    goal: str,
    progress_callback: Callable[[TaskStep], None] = None
) -> TaskPlan:
    """
    Full pipeline: Decompose goal → Execute steps → Return results.
    """
    # Think: Decompose the goal
    plan = await decompose_task(goal)
    
    # Act: Execute the plan
    executor = PlanExecutor(get_default_tools())
    plan = await executor.execute_plan(plan, progress_callback)
    
    return plan

if __name__ == "__main__":
    async def main():
        """Test the task planner."""
        goal = "Find the latest AI news and summarize it"
        print(f"🎯 Goal: {goal}")
        plan = await plan_and_execute(goal, lambda s: print(f"Step {s.id} done"))
        print(f"Final: {plan.status}")
    
    asyncio.run(main())
