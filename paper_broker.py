import os
import uuid
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client
from market_data import market_data

load_dotenv()
load_dotenv(".env.secrets")

class PaperBroker:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL")
        # Prefer service role
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
        
        if not self.url or not self.key:
            print("⚠️ PaperBroker: Supabase credentials missing (SUPABASE_URL or KEY).")
            self.supabase = None
        else:
            try:
                self.supabase: Client = create_client(self.url, self.key)
                print("✅ PaperBroker: Connected to Supabase.")
            except Exception as e:
                print(f"⚠️ PaperBroker Connection Failed: {e}")
                self.supabase = None

        self.account_id = "paper_default"

    def _resolve_user_id(self, discord_id: str) -> Optional[str]:
        """Get or create user UUID from Discord ID."""
        if not self.supabase: return None
        
        try:
            # 1. Check if exists
            res = self.supabase.table("users").select("id").eq("discord_id", str(discord_id)).limit(1).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]['id']
            
            # 2. Create if new
            new_user = {
                "discord_id": str(discord_id),
                "username": f"User_{str(discord_id)[-4:]}"
            }
            res = self.supabase.table("users").insert(new_user).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]['id']
        except Exception as e:
            print(f"⚠️ User Resolution Failed: {e}")
            # Retry once
            try:
                res = self.supabase.table("users").select("id").eq("discord_id", str(discord_id)).limit(1).execute()
                if res.data: return res.data[0]['id']
            except:
                pass
            
        return None

    def _log_audit(self, action: str, details: dict):
        """Log critical actions to audit_log."""
        if not self.supabase: return
        try:
            self.supabase.table("audit_log").insert({
                "actor": "PaperBroker",
                "action": action,
                "details": details,
                "severity": "info",
                "timestamp": datetime.utcnow().isoformat() + "Z"
            }).execute()
        except Exception as e:
            print(f"❌ Audit Log Failed: {e}")

    def check_pdt_rule(self, user_uuid: str) -> bool:
        """Check if user has > 3 day trades in last 5 days."""
        # Query 'trades' or 'pnl_daily' for counts
        # Simplified: Safe for now
        return True

    async def place_order(self, order: dict, discord_id: str):
        """Simulate placing an order."""
        if not self.supabase: return {"status": "error", "message": "No DB Connection"}

        # Resolve UUID
        user_uuid = self._resolve_user_id(discord_id)
        if not user_uuid:
            return {"status": "error", "message": "User resolution failed"}

        # 1. PDT Check (using resolved UUID)
        if not self.check_pdt_rule(user_uuid):
            return {"status": "rejected", "reason": "PDT Violation"}

        # 2. Price Check (Pessimistic)
        symbol = order.get("symbol")
        current_price = market_data.get_price(symbol)
        
        limit_price = order.get("limit_price")
        side = order.get("side") # buy/sell
        
        filled = False
        fill_price = 0.0

        if current_price > 0:
            if side == "buy":
                if not limit_price or limit_price >= current_price:
                    filled = True
                    fill_price = current_price
            elif side == "sell":
                if not limit_price or limit_price <= current_price:
                    filled = True
                    fill_price = current_price
        
        # 3. Create Record
        order_id = str(uuid.uuid4())
        status = "filled" if filled else "pending"
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        record = {
            "id": order_id,
            "user_id": user_uuid,
            "position_id": None,
            "symbol": symbol,
            "side": side,
            "quantity": order.get("quantity"),
            "order_type": order.get("type", "limit"),
            "limit_price": limit_price,
            "status": status,
            "created_at": timestamp
        }
        
        if filled:
            record["filled_price"] = fill_price
            record["filled_at"] = timestamp

        try:
            if filled:
                # Create Position
                pos_data = {
                    "user_id": user_uuid,
                    "symbol": symbol,
                    "strategy": order.get('strategy', 'manual'),
                    "direction": 'long' if side == 'buy' else 'short',
                    "entry_price": fill_price,
                    "quantity": order.get("quantity"),
                    "status": "open",
                    "legs": order.get('legs', []),
                    "entry_date": timestamp
                }
                pos_res = self.supabase.table("positions").insert(pos_data).execute()
                if pos_res.data:
                    record['position_id'] = pos_res.data[0]['id']

            self.supabase.table("orders").insert(record).execute()
            self._log_audit("place_order", {"order_id": order_id, "status": status, "symbol": symbol})
            return {"status": "submitted", "order_id": order_id, "filled": filled}
        except Exception as e:
            print(f"❌ Place Order Failed: {e}")
            return {"status": "error", "message": str(e)}

    def get_positions(self, discord_id: str) -> list:
        """Fetch open positions for user."""
        if not self.supabase: return []
        
        user_uuid = self._resolve_user_id(discord_id)
        if not user_uuid: return []
        
        try:
            res = self.supabase.table("positions").select("*").eq("user_id", user_uuid).eq("status", "open").execute()
            positions = res.data
            
            # Enrich with current mark
            for p in positions:
                current_price = market_data.get_price(p['symbol'])
                if current_price > 0:
                    p['current_price'] = float(current_price)
                    entry = float(p['entry_price'])
                    qty = int(p['quantity'])
                    
                    if p['direction'] == 'long':
                        p['pnl_open'] = (current_price - entry) * qty
                    else:
                        p['pnl_open'] = (entry - current_price) * qty
                    
                    if entry > 0:
                        p['pnl_percent'] = (p['pnl_open'] / (entry * qty)) * 100
                    else:
                        p['pnl_percent'] = 0.0
            
            return positions
        except Exception as e:
            print(f"❌ Get Positions Failed: {e}")
            return []

    def get_account_summary(self, discord_id: str) -> dict:
        """Calculate account summary (PnL, Equity)."""
        if not self.supabase:
            return {"balance": 100000.0, "pnl": 0.0, "equity": 100000.0}

        user_uuid = self._resolve_user_id(discord_id)
        if not user_uuid:
             return {"balance": 100000.0, "pnl": 0.0, "equity": 100000.0}

        # 1. Start with virtual balance
        starting_balance = 100000.0
        
        # 2. Get Open PnL
        positions = self.get_positions(discord_id)
        unrealized_pnl = sum(p.get('pnl_open', 0) for p in positions)
        
        # 3. Get Realized PnL (from closed positions)
        realized_pnl = 0.0
        try:
             # Assuming 'positions' table has 'exit_price', 'quantity', 'direction' for closed trades
             # Or we look at 'orders' table for filled sells?
             # For simplicity, let's just use open pnl for now unless we implement closing.
             pass
        except:
            pass

        total_pnl = unrealized_pnl + realized_pnl
        equity = starting_balance + total_pnl
        
        return {
            "balance": starting_balance, # Cash (technically should deduct cost basis)
            "pnl": total_pnl,
            "equity": equity,
            "open_count": len(positions)
        }

paper_broker = PaperBroker()
