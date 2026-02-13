"""Boot reconciliation orchestrator."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from typing import Any as _ExchangeClient
from ..config import CryptoTraderConfig
from ..repository import CryptoRepository
from .state_rebuilder import rebuild_state_from_db
from .broker_reconciler import fetch_broker_state, compute_diffs
from .integrity_checks import run_integrity_checks
from .resume_policy import determine_resume_policy, ResumeDecision


@dataclass
class BootResult:
    action: str  # "normal", "safe_mode", "halt"
    safe_mode_seconds: int = 0
    reason: str = ""
    run_id: str = ""
    duration_ms: int = 0


async def run_boot_reconciliation(
    client: Any,
    repo: CryptoRepository,
    config: CryptoTraderConfig,
) -> BootResult:
    """Run full boot reconciliation sequence. Returns a BootResult."""
    mode = config.mode
    run_id = f"boot-{uuid.uuid4().hex[:8]}"
    start = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()

    print(f"[BOOT] Starting boot reconciliation (mode={mode}, run_id={run_id})")

    # Record boot_audit start
    try:
        repo.insert_boot_audit({
            "run_id": run_id,
            "mode": mode,
            "instance_id": "default",
            "started_at": started_at,
            "status": "running",
        })
    except Exception as e:
        print(f"[BOOT] Warning: could not write boot_audit start: {e}")

    try:
        # 1. Rebuild state from DB snapshots
        db_state = rebuild_state_from_db(repo, mode)
        print(f"[BOOT] DB state: cash=${db_state.cash_available:.2f}, "
              f"holdings={len(db_state.holdings)}, "
              f"open_orders={len(db_state.open_orders)}, "
              f"daily_notional=${db_state.daily_notional_used:.2f}")

        # 2. Fetch broker state (live=API, paper=no-op)
        broker_state = await fetch_broker_state(client, config)
        if mode == "live":
            print(f"[BOOT] Broker state: cash=${broker_state.cash_available:.2f}, "
                  f"holdings={len(broker_state.holdings)}")

        # 3. Compute diffs
        diffs = compute_diffs(db_state, broker_state, mode)
        if mode == "live":
            print(f"[BOOT] Diffs: cash_diff=${diffs.cash_diff:.2f}, "
                  f"holding_diffs={len(diffs.holdings_diffs)}")

        # 4. Run integrity checks
        integrity = run_integrity_checks(db_state, diffs, config)
        for check in integrity.checks:
            status_str = "PASS" if check.passed else "FAIL"
            print(f"[BOOT]   {check.name}: {status_str} {check.detail}")

        # 5. Determine resume policy
        decision = determine_resume_policy(mode, diffs, integrity)
        print(f"[BOOT] Resume policy: {decision.action} -- {decision.reason}")

        # 6. Save agent_state snapshot
        try:
            repo.save_agent_state(mode, "default", {
                "boot_run_id": run_id,
                "db_cash": db_state.cash_available,
                "db_holdings": db_state.holdings,
                "open_orders": [o.get("id", "") for o in db_state.open_orders],
                "daily_notional_used": db_state.daily_notional_used,
                "resume_action": decision.action,
                "booted_at": started_at,
            })
        except Exception:
            pass

        elapsed_ms = int((time.monotonic() - start) * 1000)
        audit_status = "ok" if decision.action == "normal" else decision.action

        # 7. Finalize boot_audit
        try:
            repo.update_boot_audit(run_id, {
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": elapsed_ms,
                "status": audit_status,
                "diffs": {
                    "cash_diff": diffs.cash_diff,
                    "holdings_diffs": diffs.holdings_diffs,
                    "missing_orders": diffs.missing_orders,
                },
                "integrity_checks": integrity.to_dict(),
                "resume_policy": decision.action,
            })
        except Exception as e:
            print(f"[BOOT] Warning: could not finalize boot_audit: {e}")

        print(f"[BOOT] Boot reconciliation complete in {elapsed_ms}ms")

        return BootResult(
            action=decision.action,
            safe_mode_seconds=decision.safe_mode_seconds,
            reason=decision.reason,
            run_id=run_id,
            duration_ms=elapsed_ms,
        )

    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        print(f"[BOOT] Boot reconciliation ERROR: {e}")

        try:
            repo.update_boot_audit(run_id, {
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": elapsed_ms,
                "status": "error",
                "error_message": str(e),
            })
        except Exception:
            pass

        return BootResult(action="halt", reason=f"Boot error: {e}", run_id=run_id, duration_ms=elapsed_ms)
