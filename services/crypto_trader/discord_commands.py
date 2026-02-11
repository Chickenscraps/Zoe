from __future__ import annotations

from services.crypto_trader.trader import CryptoTraderService


def handle_crypto_command(service: CryptoTraderService, user_id: str, command: str, args: list[str]) -> str:
    try:
        if command == "/crypto_live_on":
            return service.set_live(user_id, True, " ".join(args))
        if command == "/crypto_live_off":
            return service.set_live(user_id, False)
        if command == "/crypto_status":
            health = service.get_health()
            return (
                f"status={health.status} live_enabled={health.live_enabled} "
                f"daily_notional={health.daily_notional_used:.2f} open_orders={health.open_orders} "
                f"last_reconcile={health.last_reconcile_at or 'never'}"
            )
        if command == "/crypto_buy":
            symbol, notional = args[0], float(args[1])
            service.place_order(initiator_id=user_id, symbol=symbol.upper(), side="buy", notional=notional)
            return f"buy submitted: {symbol} ${notional:.2f}"
        if command == "/crypto_sell":
            symbol = args[0]
            if len(args) == 3 and args[1] == "qty":
                service.place_order(initiator_id=user_id, symbol=symbol.upper(), side="sell", qty=float(args[2]))
            else:
                service.place_order(initiator_id=user_id, symbol=symbol.upper(), side="sell", notional=float(args[1]))
            return f"sell submitted: {symbol}"
        if command == "/crypto_pause":
            return service.pause(user_id)
        if command == "/crypto_resume":
            return service.resume(user_id)
        return "Unknown crypto command"
    except PermissionError:
        return "🚫 You found the shiny lever, but only admin raccoons can touch live crypto."
    except Exception as err:  # pragma: no cover
        return f"crypto command failed: {err}"
