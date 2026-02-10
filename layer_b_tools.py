"""
Layer B Tools: Desktop Automation (No Vision)
Focus: Reliable, fast, safe control of files and processes via Python/PowerShell.
"""
import os
import shutil
import subprocess
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# --- Process / App Management ---

def list_processes(filter_name: Optional[str] = None) -> List[Dict[str, str]]:
    """
    List running processes on Windows using PowerShell.
    Returns: List of dicts with 'name', 'id', 'title'.
    """
    try:
        # PowerShell command to get process details
        cmd = ["powershell", "-Command", "Get-Process | Select-Object Name, Id, MainWindowTitle | ConvertTo-Json -Depth 1"]
        
        # Run command
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        if not result.stdout.strip():
            return []
            
        # Parse JSON
        processes = json.loads(result.stdout)
        
        # Ensure list (PowerShell returns single obj if only 1 match)
        if isinstance(processes, dict):
            processes = [processes]
            
        # Clean and filter
        clean_list = []
        for p in processes:
            name = p.get('Name', '')
            title = p.get('MainWindowTitle', '')
            pid = p.get('Id', '')
            
            # Simple filter if provided
            if filter_name and filter_name.lower() not in name.lower() and filter_name.lower() not in title.lower():
                continue
                
            # Only return interesting ones (has window title or explicitly requested)
            if title or filter_name:
                clean_list.append({'name': name, 'id': pid, 'title': title})
                
        return clean_list[:50] # Limit results
        
    except Exception as e:
        logger.error(f"Failed to list processes: {e}")
        return [{"error": str(e)}]

def manage_process(action: str, app_name: str) -> str:
    """
    Start or Stop a desktop application.
    action: 'start' or 'stop' or 'check'
    app_name: 'notepad', 'calc', 'spotify', etc.
    """
    action = action.lower()
    
    if action == 'start':
        try:
            # Try direct launch first
            subprocess.Popen(app_name, shell=True)
            return f"🚀 Launched {app_name}"
        except Exception as e:
            # Try via PowerShell Start-Process as fallback
            try:
                cmd = ["powershell", "-Command", f"Start-Process '{app_name}'"]
                subprocess.run(cmd, check=True)
                return f"🚀 Launched {app_name} (via PowerShell)"
            except Exception as e2:
                return f"❌ Failed to launch {app_name}: {e2}"

    elif action == 'stop':
        try:
            cmd = ["powershell", "-Command", f"Stop-Process -Name '{app_name}' -Force"]
            subprocess.run(cmd, check=True)
            return f"🛑 Stopped {app_name}"
        except Exception as e:
            return f"❌ Failed to stop {app_name} (Checks regex match?): {e}"

    elif action == 'check':
        procs = list_processes(filter_name=app_name)
        if procs:
            return f"✅ {app_name} is running: {json.dumps(procs, indent=2)}"
        return f"💤 {app_name} is not running."

    return "❌ specific action 'start', 'stop', or 'check'."


# --- Filesystem / Inbox Zero ---

def scan_folder(path: str) -> Dict[str, Any]:
    """
    Scan a folder and return stats for 'Inbox Zero' planning.
    """
    p = Path(path)
    if not p.exists():
        return {"error": "Path does not exist"}
        
    stats = {
        "total_files": 0,
        "extensions": {},
        "large_files": [],
        "old_files": []
    }
    
    try:
        limit = 100
        count = 0
        for item in p.iterdir():
            if item.is_file():
                count += 1
                stats["total_files"] += 1
                ext = item.suffix.lower()
                stats["extensions"][ext] = stats["extensions"].get(ext, 0) + 1
                
                # Size check (>100MB)
                size_mb = item.stat().st_size / (1024 * 1024)
                if size_mb > 100:
                    stats["large_files"].append(item.name)
                    
                # Age check (>90 days)
                # mtime = datetime.fromtimestamp(item.stat().st_mtime)
                # ... skip for brevity
                
                if count > limit:
                     break
                     
        return stats
    except Exception as e:
        return {"error": str(e)}

def propose_organize(path: str) -> str:
    """
    Generate a CLEANUP PLAN (JSON) for a folder.
    Does NOT execute. Returns text description + plan for user to confirm.
    """
    stats = scan_folder(path)
    if "error" in stats:
        return f"Error: {stats['error']}"
    
    # Simple Heuristic Plan
    plan = {
        "target_path": path,
        "operations": []
    }
    
    p = Path(path)
    # Define mapping
    rules = {
        ".jpg": "Images", ".png": "Images", ".gif": "Images",
        ".pdf": "Documents", ".docx": "Documents", ".txt": "Documents",
        ".exe": "Installers", ".msi": "Installers",
        ".zip": "Archives", ".7z": "Archives",
        ".mp3": "Audio", ".wav": "Audio"
    }

    try:
        for item in p.iterdir():
            if item.is_file():
                ext = item.suffix.lower()
                if ext in rules:
                    folder = rules[ext]
                    plan["operations"].append({
                        "file": item.name,
                        "action": "move",
                        "destination_subfolder": folder
                    })
    except Exception as e:
         return f"Error planning: {e}"

    if not plan["operations"]:
        return "✨ Folder looks clean! No organization needed."
        
    summary = f"📋 **Proposed Cleanup Plan for `{path}`**\n"
    summary += f"- Found {len(plan['operations'])} files to move.\n"
    summary += f"- Categories: {list(set(rules.values()))}\n\n"
    summary += "To execute, reply: `Execute Plan` (I will implement the execution function next step)."
    
    # Store plan in a temp file for 'state' (or just return it if we have chat history)
    # Ideally, we return the plan JSON hidden or code block so the LLM can read it back for the 'execute' step.
    return json.dumps(plan, indent=2)


def apply_file_ops(plan_json_str: str) -> str:
    """
    Execute a plan generated by propose_organize.
    """
    try:
        plan = json.loads(plan_json_str)
        base_path = Path(plan["target_path"])
        
        results = []
        for op in plan["operations"]:
            if op["action"] == "move":
                filename = op["file"]
                dest_folder = op["destination_subfolder"]
                
                # Create destination
                target_dir = base_path / dest_folder
                target_dir.mkdir(exist_ok=True)
                
                # Move
                src = base_path / filename
                dst = target_dir / filename
                
                if src.exists():
                    shutil.move(str(src), str(dst))
                    results.append(f"Moved {filename} -> {dest_folder}")
                else:
                    results.append(f"Skipped {filename} (not found)")
                    
        return f"✅ Cleanup Complete. {len(results)} files processed.\nDetails: {results[:5]}..."
        
    except Exception as e:
        return f"❌ Execution failed: {e}"
