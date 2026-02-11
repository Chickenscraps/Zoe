"""Determine resume policy based on mode, diffs, and integrity results."""
from __future__ import annotations

from dataclasses import dataclass

from .broker_reconciler import StateDiffs
from .integrity_checks import IntegrityResult


@dataclass
class ResumeDecision:
    action: str  # "normal", "safe_mode", "halt"
    safe_mode_seconds: int = 0
    reason: str = ""


def determine_resume_policy(
    mode: str,
    diffs: StateDiffs,
    integrity: IntegrityResult,
) -> ResumeDecision:
    has_diffs = bool(diffs.holdings_diffs) or abs(diffs.cash_diff) > 1.0

    if not integrity.all_passed:
        if mode == "live":
            failed = [c.name for c in integrity.failed_checks]
            return ResumeDecision(
                action="halt",
                reason=f"Live mode integrity failure: {', '.join(failed)}",
            )
        else:
            failed = [c.name for c in integrity.failed_checks]
            return ResumeDecision(
                action="safe_mode",
                safe_mode_seconds=60,
                reason=f"Paper mode integrity warning: {', '.join(failed)}",
            )

    if has_diffs:
        return ResumeDecision(
            action="safe_mode",
            safe_mode_seconds=60,
            reason="State diffs detected -- entering safe mode cooldown",
        )

    return ResumeDecision(action="normal", reason="All checks passed, no diffs")
