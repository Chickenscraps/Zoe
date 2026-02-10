"""
Approval Gate Middleware (Production-Grade)
Enforces code-level safety via RISK_REGISTRY and audit logging.
Based on AGI Architecture Upgrade research §6.
"""
import os
import csv
import logging
import uuid
from datetime import datetime
from typing import Optional, Dict, Literal
from enum import Enum
import discord

# ============================================================================
# Configuration
# ============================================================================

ROOT_ADMIN_ID = 292890243852664855  # CHICKENSCRAPS
AUDIT_LOG_PATH = os.path.join(os.path.dirname(__file__), "audit.csv")

class RiskLevel(Enum):
    LOW = "LOW"           # Read-only, information retrieval
    MEDIUM = "MED"        # External read, browser access
    HIGH = "HIGH"         # Write access, system modification
    CRITICAL = "CRITICAL" # Destructive, admin privileges

# Static Risk Registry - Every tool must be classified
RISK_REGISTRY: Dict[str, RiskLevel] = {
    # LOW - Auto-execute
    "time_get": RiskLevel.LOW,
    "weather_check": RiskLevel.LOW,
    "memory_recall": RiskLevel.LOW,
    "get_news": RiskLevel.LOW,
    "get_directions": RiskLevel.LOW,
    "get_mood": RiskLevel.LOW,
    
    # MEDIUM - Auto-execute with audit log
    "google_search": RiskLevel.MEDIUM,
    "read_file": RiskLevel.MEDIUM,
    "read_url": RiskLevel.MEDIUM,
    "search_web": RiskLevel.MEDIUM,
    "polymarket_fetch": RiskLevel.MEDIUM,
    "vision_capture": RiskLevel.MEDIUM,
    
    # HIGH - Requires approval
    "write_file": RiskLevel.HIGH,
    "install_pip": RiskLevel.HIGH,
    "move_file": RiskLevel.HIGH,
    "send_email": RiskLevel.HIGH,
    "paper_trade": RiskLevel.HIGH,
    "manage_game_server": RiskLevel.HIGH,
    
    # CRITICAL - Root admin only
    "delete_file": RiskLevel.CRITICAL,
    "os_system": RiskLevel.CRITICAL,
    "execute_script": RiskLevel.CRITICAL,
    "shutdown": RiskLevel.CRITICAL,
    "trade_crypto": RiskLevel.CRITICAL,
    "firewall_change": RiskLevel.CRITICAL,
}

# ============================================================================
# Audit Logger
# ============================================================================

def _ensure_audit_log():
    """Create audit.csv with headers if it doesn't exist."""
    if not os.path.exists(AUDIT_LOG_PATH):
        with open(AUDIT_LOG_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "user_id", "tool", "args", "risk", "outcome", "approver_id"])

def log_audit(user_id: int, tool: str, args: dict, risk: RiskLevel, outcome: str, approver_id: Optional[int] = None):
    """Log an action to audit.csv."""
    _ensure_audit_log()
    with open(AUDIT_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(),
            user_id,
            tool,
            str(args),
            risk.value,
            outcome,
            approver_id or ""
        ])

# ============================================================================
# Approval Gate
# ============================================================================

class ApprovalGate:
    """Production-grade safety middleware."""
    
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.pending_requests: Dict[str, dict] = {}
        self.logger = logging.getLogger("approval_gate")
        _ensure_audit_log()
        self.logger.info("ApprovalGate initialized with RISK_REGISTRY")

    def classify_risk(self, tool_name: str) -> RiskLevel:
        """Classify a tool's risk level."""
        return RISK_REGISTRY.get(tool_name, RiskLevel.HIGH)  # Default to HIGH if unknown

    def enforce(
        self, 
        tool_name: str, 
        args: dict, 
        user_id: int
    ) -> Literal["ALLOW", "DENY", "REQUIRE_APPROVAL"]:
        """
        Enforce safety policy on a tool call.
        Returns:
            ALLOW - Execute immediately
            DENY - Block (non-admin calling CRITICAL)
            REQUIRE_APPROVAL - Pause and request admin approval
        """
        risk = self.classify_risk(tool_name)
        
        # LOW/MEDIUM: Auto-allow
        if risk in [RiskLevel.LOW, RiskLevel.MEDIUM]:
            if risk == RiskLevel.MEDIUM:
                log_audit(user_id, tool_name, args, risk, "ALLOWED")
            return "ALLOW"
        
        # HIGH/CRITICAL: Check permissions
        is_admin = user_id == ROOT_ADMIN_ID
        
        if risk == RiskLevel.CRITICAL:
            if is_admin:
                log_audit(user_id, tool_name, args, risk, "ALLOWED_ADMIN")
                return "ALLOW"
            else:
                log_audit(user_id, tool_name, args, risk, "DENIED")
                return "DENY"
        
        # HIGH: Admin auto-approves, others need approval
        if risk == RiskLevel.HIGH:
            if is_admin:
                log_audit(user_id, tool_name, args, risk, "ALLOWED_ADMIN")
                return "ALLOW"
            else:
                return "REQUIRE_APPROVAL"
        
        return "DENY"  # Fallback

    async def request_approval(
        self, 
        tool_name: str, 
        args: dict, 
        user_id: int, 
        channel: discord.TextChannel
    ) -> str:
        """
        Create an approval request with interactive buttons.
        Returns the request token.
        """
        token = str(uuid.uuid4())[:8]
        risk = self.classify_risk(tool_name)
        
        self.pending_requests[token] = {
            "tool": tool_name,
            "args": args,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "risk": risk
        }
        
        embed = discord.Embed(
            title="⚠️ Authorization Required",
            description=f"User <@{user_id}> requested a **{risk.value}** risk action.",
            color=discord.Color.orange() if risk == RiskLevel.HIGH else discord.Color.red()
        )
        embed.add_field(name="Tool", value=f"`{tool_name}`", inline=True)
        embed.add_field(name="Risk Level", value=risk.value, inline=True)
        embed.add_field(name="Arguments", value=f"```{args}```", inline=False)
        embed.set_footer(text=f"Token: {token} | Only CHICKENSCRAPS can approve.")
        
        # Send to channel
        await channel.send(embed=embed)
        
        # Also DM admin
        try:
            admin = await self.bot.fetch_user(ROOT_ADMIN_ID)
            await admin.send(embed=embed)
        except Exception as e:
            self.logger.warning(f"Could not DM admin: {e}")
        
        log_audit(user_id, tool_name, args, risk, "PENDING_APPROVAL")
        return token

    async def approve(self, token: str, approver_id: int) -> bool:
        """Approve a pending request."""
        if approver_id != ROOT_ADMIN_ID:
            return False
        
        if token not in self.pending_requests:
            return False
        
        req = self.pending_requests.pop(token)
        log_audit(req["user_id"], req["tool"], req["args"], req["risk"], "APPROVED", approver_id)
        self.logger.info(f"Request {token} approved by {approver_id}")
        return True

    async def deny(self, token: str, denier_id: int) -> bool:
        """Deny a pending request."""
        if denier_id != ROOT_ADMIN_ID:
            return False
        
        if token not in self.pending_requests:
            return False
        
        req = self.pending_requests.pop(token)
        log_audit(req["user_id"], req["tool"], req["args"], req["risk"], "DENIED", denier_id)
        self.logger.info(f"Request {token} denied by {denier_id}")
        return True

    # Legacy compatibility
    async def check_permission(self, action: str, user_id: int, context: str = "") -> bool:
        """Legacy method for backward compatibility."""
        result = self.enforce(action, {"context": context}, user_id)
        return result == "ALLOW"

    def is_sensitive(self, action: str) -> bool:
        """Check if action is HIGH or CRITICAL risk."""
        risk = self.classify_risk(action)
        return risk in [RiskLevel.HIGH, RiskLevel.CRITICAL]
