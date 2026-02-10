
"""
Game Server Manager for Zoe
Extensions to manage game servers via Docker or Scripts.
Protected by Approval Gate.
"""
import os
import asyncio
import logging
from typing import Dict, Any, Optional

# Mock Docker client for now, or use subprocess
# import docker 

class GameServerManager:
    def __init__(self, approval_gate):
        self.approval_gate = approval_gate
        self.logger = logging.getLogger("game_manager")
        self.servers = {
            "minecraft": {"type": "docker", "container": "mc_server_1", "status": "stopped"},
            "valheim": {"type": "script", "cmd": "./start_valheim.sh", "status": "stopped"}
        }

    async def list_servers(self) -> str:
        """List available servers and status."""
        lines = ["🖥️ **Game Servers**"]
        for name, info in self.servers.items():
            lines.append(f"- **{name}**: {info['status'].upper()} ({info['type']})")
        return "\n".join(lines)

    async def start_server(self, name: str, user_id: int) -> str:
        """Request to start a server."""
        if name not in self.servers:
            return f"❌ Unknown server: {name}"
        
        server = self.servers[name]
        if server["status"] == "running":
            return f"⚠️ {name} is already running."

        # Check Approval
        if self.approval_gate:
            allowed = await self.approval_gate.check_permission("start_server", user_id, f"Start {name}")
            if not allowed:
                return f"🛡️ request to start {name} submitted for approval."

        # Execute (Simulated)
        server["status"] = "running"
        self.logger.info(f"Started server {name}")
        return f"✅ **{name}** started!"

    async def stop_server(self, name: str, user_id: int) -> str:
        """Request to stop a server."""
        if name not in self.servers:
            return f"❌ Unknown server: {name}"

        server = self.servers[name]
        if server["status"] == "stopped":
            return f"⚠️ {name} is already stopped."

        # Check Approval
        if self.approval_gate:
            allowed = await self.approval_gate.check_permission("stop_server", user_id, f"Stop {name}")
            if not allowed:
                return f"🛡️ request to stop {name} submitted for approval."

        # Execute
        server["status"] = "stopped"
        self.logger.info(f"Stopped server {name}")
        return f"🛑 **{name}** stopped."
