"""
Project Worker Module
Handles the "work unit" execution for autonomous projects.
"""
import asyncio
import logging
from project_manager import project_manager, Project
from model_router import router
from discord.ext import commands

logger = logging.getLogger(__name__)

async def run_project_cycle(bot: commands.Bot, guild_id: int):
    """
    Called by scheduler every N minutes.
    Picks an active project and executes one work unit.
    """
    logger.info("♻️ Project Cycle Triggered")
    
    # 1. Find active project
    # For MVP, we'll just check all projects and see if any are flagged 'in_progress'
    # Implementation: iterating files (simple)
    
    projects = project_manager.list_projects()
    active_project = None
    
    for p_name in projects:
        proj = project_manager.load_project(p_name)
        if proj and proj.data.get("status") == "in_progress":
            active_project = proj
            break
            
    if not active_project:
        # Nothing to do
        return

    # 2. Get Next Task
    tasks = active_project.data.get("next_tasks", [])
    if not tasks:
        logger.info(f"Project {active_project.name} has no tasks.")
        return

    current_task = tasks[0]
    logger.info(f"🔨 Working on {active_project.name}: {current_task}")
    
    # 3. Announce start (Discord)
    guild = bot.get_guild(guild_id)
    channel = None
    if guild:
        channel = guild.system_channel or guild.text_channels[0]
    
    if channel:
        await channel.send(f"🏗️ **{active_project.name}**: Starting work on `{current_task}`...")

    # 4. Generate Content (Model Router)
    # This is the "Work" - generating code, docs, etc.
    # We use a specialized prompt for "solving" the task based on project context/files.
    
    try:
        # Context building (simple fallback)
        context = f"Project: {active_project.name}\nGoal: {active_project.data['goal']}\nCurrent Task: {current_task}"
        
        system_prompt = """You are an autonomous developer (Zoe).
Execute the requested task for the project.
Return a brief summary of what you did and any code changes in unified diff format.
"""
        messages = [{"role": "user", "content": f"Context:\n{context}\n\nTask: Execute this task."}]
        
        result = await router.chat(messages, system=system_prompt)
        
        # 5. Apply Results
        # Simple parsing for "file blocks" or unified diffs
        import re
        
        # Regex to find ```python\n content \n``` or similar
        # and filename comments like # filename: src/main.py
        
        # For now, let's look for explicit file blocks with headers
        # Strategy: Look for "File: <path>" lines followed by code blocks
        
        applied_changes = []
        
        # Pattern: File: path/to/file
        # ```ext
        # content
        # ```
        file_pattern = re.compile(r"File:\s*([^\n]+)\s*```\w*\n(.*?)```", re.DOTALL)
        matches = file_pattern.findall(result)
        
        for filename, content in matches:
            filename = filename.strip()
            # Security check: ensure path is within project
            safe_path = (active_project.path / filename).resolve()
            if not str(safe_path).startswith(str(active_project.path.resolve())):
                logger.warning(f"Skipping unsafe file write: {filename}")
                continue
                
            # Create parent dirs
            safe_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file
            with open(safe_path, "w", encoding='utf-8') as f:
                f.write(content)
            applied_changes.append(filename)

        if applied_changes:
            logger.info(f"Applied changes to: {applied_changes}")
            active_project.add_log(f"Updated files: {', '.join(applied_changes)}")
        else:
             # Try diff application logic if no full files found (future)
             pass

        # 6. Log & Update
        active_project.add_log(f"Executed: {current_task}\nResult: {result[:100]}...")
        
        # Rotate task
        active_project.data["next_tasks"].pop(0)
        active_project.save()
        
        # 7. Announce completion
        if channel:
            summary = f"✅ **{active_project.name}**: Finished `{current_task}`."
            if applied_changes:
                summary += f"\nUpdated: `{', '.join(applied_changes)}`"
            await channel.send(summary)
            
    except Exception as e:
        logger.error(f"Project cycle failed: {e}")
        if channel:
            await channel.send(f"⚠️ **{active_project.name}**: Hit a snag. {e}")
