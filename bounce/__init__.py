"""
Bounce Catcher module for the Zoe Trading System.

Implements a 3-phase state machine that detects capitulation events,
confirms stabilization, and emits high-confidence TradeIntents for
relief-bounce entries.
"""

from bounce.bounce_catcher import BounceCatcher
from bounce.capitulation import detect_capitulation_event, calculate_wick_ratio
from bounce.stabilization import check_stabilization
from bounce.bounce_score import calculate_bounce_score
from bounce.entry_planner import build_trade_intent, TradeIntent
from bounce.exit_planner import ExitPlan, compute_exit_plan
from bounce.guards import check_halt_conditions

__all__ = [
    "BounceCatcher",
    "detect_capitulation_event",
    "calculate_wick_ratio",
    "check_stabilization",
    "calculate_bounce_score",
    "build_trade_intent",
    "TradeIntent",
    "ExitPlan",
    "compute_exit_plan",
    "check_halt_conditions",
]
