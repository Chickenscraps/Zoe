from __future__ import annotations

from .orchestrator import EdgeFactoryOrchestrator


def handle_edge_factory_command(
    orchestrator: EdgeFactoryOrchestrator,
    user_id: str,
    command: str,
    args: list[str],
) -> str:
    """
    Discord command handler for Edge Factory.

    Commands:
        /ef_status      Current mode, regime, positions, PnL
        /ef_regime      Current regime classification
        /ef_signals     Recent signals for a symbol
        /ef_positions   Open positions with TP/SL
        /ef_history     Closed positions with PnL
        /ef_features    Latest features for a symbol
        /ef_mode <m>    Set mode: disabled|paper|live (admin only)
        /ef_kill        Emergency kill switch (admin only)
    """
    try:
        if command == "/ef_status":
            status = orchestrator.get_status()
            regime_icon = {
                "low_vol_bull": "🟢",
                "transition": "🟡",
                "high_vol_crash": "🔴",
            }.get(status["regime"], "⚪")

            lines = [
                f"**Edge Factory** | Mode: `{status['mode']}`",
                f"Regime: {regime_icon} `{status['regime']}` (conf: {status['regime_confidence']:.0%})",
                f"Open: {status['open_positions']} pos (${status['open_exposure']:.2f})",
                f"PnL: ${status['total_pnl']:+.4f} | W/L: {status['wins']}/{status['losses']} ({status['win_rate']:.0%})",
                f"Daily: ${status['daily_notional']:.2f} / ${orchestrator.config.max_daily_notional:.2f}",
                f"Ticks: {status['tick_count']} | Errors: {status['consecutive_errors']}",
            ]
            if status["halted"]:
                lines.insert(1, "⛔ **HALTED** — Kill switch active")
            return "\n".join(lines)

        if command == "/ef_regime":
            regime = orchestrator.repo.get_latest_regime()
            if not regime:
                return "No regime detected yet. Run a tick first."
            return (
                f"Regime: `{regime.regime}` (confidence: {regime.confidence:.0%})\n"
                f"Detected: {regime.detected_at.strftime('%Y-%m-%d %H:%M UTC')}\n"
                f"Features: {_fmt_dict(regime.features_used)}"
            )

        if command == "/ef_signals":
            symbol = args[0].upper() if args else "BTC-USD"
            signals = orchestrator.repo.get_recent_signals(symbol, limit=5)
            if not signals:
                return f"No recent signals for {symbol}."
            lines = [f"**Recent Signals for {symbol}:**"]
            for sig in signals:
                lines.append(
                    f"  `{sig.direction}` str={sig.strength:.2f} "
                    f"regime={sig.regime.regime} @ {sig.generated_at.strftime('%H:%M')}"
                )
            return "\n".join(lines)

        if command == "/ef_positions":
            positions = orchestrator.repo.get_open_positions()
            if not positions:
                return "No open positions."
            lines = ["**Open Positions:**"]
            for pos in positions:
                lines.append(
                    f"  `{pos.symbol}` ${pos.size_usd:.2f} @ {pos.entry_price:.4f} "
                    f"TP={pos.tp_price:.4f} SL={pos.sl_price:.4f}"
                )
            return "\n".join(lines)

        if command == "/ef_history":
            limit = int(args[0]) if args else 10
            closed = orchestrator.repo.get_closed_positions(limit=limit)
            if not closed:
                return "No closed positions yet."
            lines = ["**Closed Positions:**"]
            for pos in closed:
                pnl = pos.pnl_usd or 0
                icon = "✅" if pnl > 0 else "❌"
                lines.append(
                    f"  {icon} `{pos.symbol}` ${pnl:+.4f} "
                    f"({pos.status}) @ {(pos.exit_time or pos.entry_time).strftime('%m-%d %H:%M')}"
                )
            total = sum(p.pnl_usd or 0 for p in closed)
            lines.append(f"\n**Total PnL:** ${total:+.4f}")
            return "\n".join(lines)

        if command == "/ef_features":
            symbol = args[0].upper() if args else "BTC-USD"
            feat_dict = orchestrator.features.get_latest_features(symbol)
            if not feat_dict:
                return f"No features computed for {symbol} yet."
            lines = [f"**Features for {symbol}:**"]
            for name, val in sorted(feat_dict.items()):
                lines.append(f"  `{name}`: {val:.6f}")
            return "\n".join(lines)

        if command == "/ef_mode":
            _require_admin(orchestrator, user_id)
            if not args:
                return f"Current mode: `{orchestrator.config.mode}`. Usage: /ef_mode <disabled|paper|live>"
            new_mode = args[0].lower()
            if new_mode not in {"disabled", "paper", "live"}:
                return "Invalid mode. Choose: disabled, paper, live"
            orchestrator.config.mode = new_mode
            orchestrator._halted = False  # Reset halt on mode change
            orchestrator.audit.write("ef_mode_change", mode=new_mode, by=user_id)
            return f"Edge Factory mode set to `{new_mode}`"

        if command == "/ef_kill":
            _require_admin(orchestrator, user_id)
            orchestrator._halted = True
            orchestrator.audit.write("ef_manual_kill", by=user_id)
            return "⛔ Edge Factory KILLED. All new trading halted. Use `/ef_mode paper` to restart."

        if command == "/ef_slippage":
            limit = int(args[0]) if args else 20
            if not hasattr(orchestrator, 'executor') or not hasattr(orchestrator.executor, 'order_manager'):
                return "Slippage tracking requires V2 execution stack."
            om = getattr(orchestrator.executor, 'order_manager', None)
            if om is None or not om.slippage_history:
                return "No slippage data recorded yet."
            recent = list(om.slippage_history)[-limit:]
            avg_mid = sum(r.slippage_vs_mid_bps for r in recent) / len(recent)
            avg_bbo = sum(r.slippage_vs_bbo_bps for r in recent) / len(recent)
            avg_spread = sum(r.spread_at_submit_bps for r in recent) / len(recent)
            lines = [
                f"**Slippage Report** (last {len(recent)} fills)",
                f"Avg vs Mid: {avg_mid:+.1f} bps",
                f"Avg vs BBO: {avg_bbo:+.1f} bps",
                f"Avg Spread: {avg_spread:.1f} bps",
            ]
            for r in recent[-5:]:
                lines.append(
                    f"  `{r.symbol}` {r.side} mid={r.slippage_vs_mid_bps:+.1f}bps "
                    f"bbo={r.slippage_vs_bbo_bps:+.1f}bps mode={r.execution_mode}"
                )
            return "\n".join(lines)

        if command == "/ef_equity":
            acct = getattr(orchestrator, 'account_state', None)
            if acct is None:
                equity = orchestrator.config.account_equity
                hwm = orchestrator.repo.get_equity_high_water_mark()
            else:
                equity = acct.equity
                hwm = orchestrator.repo.get_equity_high_water_mark()
            dd = (hwm - equity) / hwm * 100 if hwm > 0 else 0
            open_positions = orchestrator.repo.get_open_positions()
            exposure = sum(p.size_usd for p in open_positions)
            return (
                f"**Equity:** ${equity:.2f}\n"
                f"**HWM:** ${hwm:.2f} (DD: {dd:.1f}%%)\n"
                f"**Exposure:** ${exposure:.2f} ({len(open_positions)} pos)\n"
                f"**Available:** ${max(0, equity - exposure):.2f}"
            )

        return f"Unknown command: {command}. Try /ef_status"

    except PermissionError:
        return "🚫 Admin-only command."
    except Exception as e:
        return f"Error: {e}"


def _require_admin(orchestrator: EdgeFactoryOrchestrator, user_id: str) -> None:
    if user_id != orchestrator.config.admin_user_id:
        raise PermissionError("Admin only")


def _fmt_dict(d: dict) -> str:
    return ", ".join(f"{k}={v:.4f}" for k, v in d.items())
