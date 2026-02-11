"""Boot integrity checks — validate state consistency before resuming."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config import CryptoTraderConfig
from .state_rebuilder import DBState
from .broker_reconciler import StateDiffs


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class IntegrityResult:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failed_checks(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "checks": [
                {"name": c.name, "passed": c.passed, "detail": c.detail}
                for c in self.checks
            ],
        }


def run_integrity_checks(
    db_state: DBState,
    diffs: StateDiffs,
    config: CryptoTraderConfig,
) -> IntegrityResult:
    checks: list[CheckResult] = []

    # 1. Cash tolerance
    cash_ok = abs(diffs.cash_diff) <= 1.0
    checks.append(CheckResult(
        name="cash_tolerance",
        passed=cash_ok,
        detail=f"Cash diff: ${diffs.cash_diff:.2f}" if not cash_ok else "OK",
    ))

    # 2. No phantom positions (holdings in DB but not at broker)
    phantom = [sym for sym, diff in diffs.holdings_diffs.items() if diff > 0]
    checks.append(CheckResult(
        name="no_phantom_positions",
        passed=len(phantom) == 0,
        detail=f"Phantom positions: {phantom}" if phantom else "OK",
    ))

    # 3. Daily notional within limits
    notional_ok = db_state.daily_notional_used <= config.max_daily_notional
    checks.append(CheckResult(
        name="daily_notional_limit",
        passed=notional_ok,
        detail=f"Used ${db_state.daily_notional_used:.2f} / ${config.max_daily_notional:.2f}" if not notional_ok else "OK",
    ))

    # 4. Position count within max
    open_positions = [sym for sym, qty in db_state.holdings.items() if qty > 0]
    pos_ok = len(open_positions) <= config.max_open_positions
    checks.append(CheckResult(
        name="position_count_limit",
        passed=pos_ok,
        detail=f"{len(open_positions)} positions / max {config.max_open_positions}" if not pos_ok else "OK",
    ))

    # 5. No missing orders
    missing_ok = len(diffs.missing_orders) == 0
    checks.append(CheckResult(
        name="no_missing_orders",
        passed=missing_ok,
        detail=f"Missing: {diffs.missing_orders}" if not missing_ok else "OK",
    ))

    return IntegrityResult(checks=checks)
