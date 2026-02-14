"""Scout/Focus market data service backed by Kraken WS v2.

Two tiers:
  - Focus (~10-50 symbols): Subscribed to ticker+book+trade, coalesced every 500ms,
    flushed to `market_snapshot_focus`. Drives trading logic and dashboard.
  - Scout (~200 USD+stablecoin pairs): Subscribed to ticker only, coalesced every 10s,
    flushed to `market_snapshot_scout`. Used for mover detection and promotion.

Promotion logic: volume spike > 2x, price move > 0.5%, spread < 0.2% → promote to focus.
Demotion: after 10 min of inactivity (no trades, no signal), demote back to scout.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .kraken_client import KrakenRestClient, AssetPairInfo
from .kraken_ws_manager import KrakenWsManager
from .symbol_map import is_usd_or_stablecoin_quoted

logger = logging.getLogger(__name__)

# Default focus symbols (major USD pairs)
DEFAULT_FOCUS = [
    "BTC/USD", "ETH/USD", "SOL/USD", "LTC/USD",
    "XRP/USD", "ADA/USD", "DOGE/USD",
]

FOCUS_FLUSH_INTERVAL_S = 0.5
SCOUT_FLUSH_INTERVAL_S = 10.0
PROMOTION_COOLDOWN_S = 600  # 10 min in focus before eligible for demotion


@dataclass
class TickerSnapshot:
    """In-memory buffer for a single symbol's latest ticker data."""
    symbol: str
    bid: float = 0.0
    ask: float = 0.0
    mid: float = 0.0
    last_price: float = 0.0
    volume_24h: float = 0.0
    change_pct_24h: float = 0.0
    spread_bps: float = 0.0
    updated_at: float = 0.0  # time.time()

    # For promotion detection
    prev_volume_1h: float = 0.0
    prev_mid_5m: float = 0.0


@dataclass
class CatalogEntry:
    """Cached pair metadata from Kraken AssetPairs."""
    symbol: str
    base: str
    quote: str
    lot_decimals: int
    pair_decimals: int
    lot_min: float
    cost_min: float
    ordermin: float
    tick_size: float | None
    status: str


class MarketDataService:
    """Manages WS subscriptions, coalescing, and DB flushing."""

    def __init__(
        self,
        rest_client: KrakenRestClient,
        ws_manager: KrakenWsManager,
        repository: Any,  # SupabaseCryptoRepository
        focus_symbols: list[str] | None = None,
    ):
        self.rest = rest_client
        self.ws = ws_manager
        self.repo = repository

        # Symbol sets
        self._focus_set: set[str] = set(focus_symbols or DEFAULT_FOCUS)
        self._scout_set: set[str] = set()

        # In-memory coalescing buffers
        self._focus_buffer: dict[str, TickerSnapshot] = {}
        self._scout_buffer: dict[str, TickerSnapshot] = {}

        # Catalog cache
        self._catalog: dict[str, CatalogEntry] = {}

        # Promotion tracking: symbol → time promoted
        self._promotion_times: dict[str, float] = {}

        # Flush timing
        self._last_focus_flush: float = 0.0
        self._last_scout_flush: float = 0.0

        # Running state
        self._running = False
        self._tasks: list[asyncio.Task] = []

    # ── Startup ──

    async def initialize(self) -> None:
        """Load catalog from REST, set up scout universe, wire WS callbacks."""
        logger.info("MarketDataService initializing...")

        # 1. Fetch all pairs from Kraken
        pairs = await self.rest.get_asset_pairs()
        for p in pairs:
            self._catalog[p.symbol] = CatalogEntry(
                symbol=p.symbol,
                base=p.base,
                quote=p.quote,
                lot_decimals=p.lot_decimals,
                pair_decimals=p.pair_decimals,
                lot_min=p.lot_min,
                cost_min=p.cost_min,
                ordermin=p.ordermin,
                tick_size=p.tick_size,
                status=p.status,
            )

        # Persist catalog to DB
        catalog_rows = [
            {
                "symbol": c.symbol,
                "base_asset": c.base,
                "quote_asset": c.quote,
                "lot_decimals": c.lot_decimals,
                "pair_decimals": c.pair_decimals,
                "lot_min": c.lot_min,
                "cost_min": c.cost_min,
                "ordermin": c.ordermin,
                "tick_size": c.tick_size,
                "status": c.status,
            }
            for c in self._catalog.values()
        ]
        self.repo.upsert_market_catalog(catalog_rows)
        logger.info("Catalog loaded: %d pairs total", len(self._catalog))

        # 2. Build scout universe: USD + USDT + USDC quoted, online, not in focus
        for sym, entry in self._catalog.items():
            if entry.status != "online":
                continue
            if not is_usd_or_stablecoin_quoted(sym):
                continue
            if sym not in self._focus_set:
                self._scout_set.add(sym)

        logger.info("Focus: %d symbols, Scout: %d symbols", len(self._focus_set), len(self._scout_set))

        # 3. Register WS callbacks
        self.ws.on_ticker(self._handle_ticker)
        self.ws.on_book(self._handle_book)
        self.ws.on_trade(self._handle_trade)

    async def start(self) -> None:
        """Subscribe to WS channels and start flush loops."""
        self._running = True

        # Subscribe focus: ticker + book + trade
        focus_list = sorted(self._focus_set)
        if focus_list:
            await self.ws.subscribe_ticker(focus_list)
            await self.ws.subscribe_book(focus_list, depth=10)
            await self.ws.subscribe_trade(focus_list)

        # Subscribe scout: ticker only
        scout_list = sorted(self._scout_set)
        if scout_list:
            # Subscribe in batches of 100 to avoid overwhelming
            for i in range(0, len(scout_list), 100):
                batch = scout_list[i:i+100]
                await self.ws.subscribe_ticker(batch)

        # Start flush loops
        self._tasks.append(asyncio.create_task(self._focus_flush_loop()))
        self._tasks.append(asyncio.create_task(self._scout_flush_loop()))
        self._tasks.append(asyncio.create_task(self._promotion_loop()))

        logger.info("MarketDataService started: focus=%d scout=%d", len(focus_list), len(scout_list))

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()

    # ── WS message handlers ──

    async def _handle_ticker(self, data: dict[str, Any]) -> None:
        """Process incoming ticker (Level-1) message."""
        msg_data = data.get("data", [])
        for tick in msg_data if isinstance(msg_data, list) else [msg_data]:
            symbol = tick.get("symbol", "")
            if not symbol:
                continue

            bid = float(tick.get("bid", 0))
            ask = float(tick.get("ask", 0))
            last = float(tick.get("last", 0))
            volume = float(tick.get("volume", 0))
            change_pct = float(tick.get("change_pct", tick.get("change", 0)))

            mid = (bid + ask) / 2 if bid > 0 and ask > 0 else last
            spread_bps = ((ask - bid) / mid * 10000) if mid > 0 else 0

            snap = TickerSnapshot(
                symbol=symbol,
                bid=bid,
                ask=ask,
                mid=mid,
                last_price=last,
                volume_24h=volume,
                change_pct_24h=change_pct,
                spread_bps=spread_bps,
                updated_at=time.time(),
            )

            if symbol in self._focus_set:
                existing = self._focus_buffer.get(symbol)
                if existing:
                    snap.prev_volume_1h = existing.prev_volume_1h
                    snap.prev_mid_5m = existing.prev_mid_5m
                self._focus_buffer[symbol] = snap
            else:
                existing = self._scout_buffer.get(symbol)
                if existing:
                    snap.prev_volume_1h = existing.prev_volume_1h
                    snap.prev_mid_5m = existing.prev_mid_5m
                self._scout_buffer[symbol] = snap

    async def _handle_book(self, data: dict[str, Any]) -> None:
        """Process book updates — extract best bid/ask for focus snapshots."""
        msg_data = data.get("data", [])
        for update in msg_data if isinstance(msg_data, list) else [msg_data]:
            symbol = update.get("symbol", "")
            if not symbol or symbol not in self._focus_set:
                continue

            bids = update.get("bids", [])
            asks = update.get("asks", [])

            if bids and asks:
                best_bid = float(bids[0].get("price", 0))
                best_ask = float(asks[0].get("price", 0))
                if best_bid > 0 and best_ask > 0:
                    snap = self._focus_buffer.get(symbol)
                    if snap:
                        snap.bid = best_bid
                        snap.ask = best_ask
                        snap.mid = (best_bid + best_ask) / 2
                        snap.spread_bps = (best_ask - best_bid) / snap.mid * 10000 if snap.mid > 0 else 0
                        snap.updated_at = time.time()

    async def _handle_trade(self, data: dict[str, Any]) -> None:
        """Process trade events — update last price for focus symbols."""
        msg_data = data.get("data", [])
        for trade in msg_data if isinstance(msg_data, list) else [msg_data]:
            symbol = trade.get("symbol", "")
            price = float(trade.get("price", 0))
            if symbol and price > 0 and symbol in self._focus_set:
                snap = self._focus_buffer.get(symbol)
                if snap:
                    snap.last_price = price
                    snap.updated_at = time.time()

    # ── Flush loops ──

    async def _focus_flush_loop(self) -> None:
        """Flush focus buffer to DB every FOCUS_FLUSH_INTERVAL_S."""
        while self._running:
            try:
                await asyncio.sleep(FOCUS_FLUSH_INTERVAL_S)
                await self._flush_focus()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Focus flush error: %s", e)

    async def _scout_flush_loop(self) -> None:
        """Flush scout buffer to DB every SCOUT_FLUSH_INTERVAL_S."""
        while self._running:
            try:
                await asyncio.sleep(SCOUT_FLUSH_INTERVAL_S)
                await self._flush_scout()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Scout flush error: %s", e)

    async def _flush_focus(self) -> None:
        """Write focus snapshots to market_snapshot_focus."""
        if not self._focus_buffer:
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        rows = [
            {
                "symbol": s.symbol,
                "bid": s.bid,
                "ask": s.ask,
                "mid": s.mid,
                "last_price": s.last_price,
                "volume_24h": s.volume_24h,
                "change_pct_24h": s.change_pct_24h,
                "spread_bps": s.spread_bps,
                "updated_at": now_iso,
            }
            for s in self._focus_buffer.values()
            if s.updated_at > 0
        ]
        if rows:
            self.repo.upsert_market_snapshot_focus(rows)

    async def _flush_scout(self) -> None:
        """Write scout snapshots to market_snapshot_scout."""
        if not self._scout_buffer:
            return
        now_iso = datetime.now(timezone.utc).isoformat()
        rows = [
            {
                "symbol": s.symbol,
                "mid": s.mid,
                "volume_24h": s.volume_24h,
                "change_pct_24h": s.change_pct_24h,
                "updated_at": now_iso,
            }
            for s in self._scout_buffer.values()
            if s.updated_at > 0
        ]
        if rows:
            self.repo.upsert_market_snapshot_scout(rows)

    # ── Promotion / Demotion ──

    async def _promotion_loop(self) -> None:
        """Periodically check scout symbols for promotion criteria."""
        while self._running:
            try:
                await asyncio.sleep(30.0)  # check every 30s
                await self._check_promotions()
                await self._check_demotions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Promotion loop error: %s", e)

    async def _check_promotions(self) -> None:
        """Promote scout symbols to focus if they meet criteria."""
        now = time.time()
        to_promote: list[str] = []

        for symbol, snap in self._scout_buffer.items():
            if symbol in self._focus_set:
                continue
            if snap.updated_at == 0:
                continue

            # Criteria: volume spike > 2x, price move > 0.5%, spread < 20 bps (0.2%)
            score = 0
            if snap.prev_volume_1h > 0 and snap.volume_24h > snap.prev_volume_1h * 2:
                score += 2
            if snap.prev_mid_5m > 0:
                price_move = abs(snap.mid / snap.prev_mid_5m - 1)
                if price_move > 0.005:
                    score += 1
            if 0 < snap.spread_bps < 20:
                score += 1

            if score >= 3:
                to_promote.append(symbol)

        for sym in to_promote:
            await self._promote(sym)

    async def _check_demotions(self) -> None:
        """Demote focus symbols back to scout after inactivity."""
        now = time.time()
        default_focus = set(DEFAULT_FOCUS)
        to_demote: list[str] = []

        for sym, promoted_at in list(self._promotion_times.items()):
            if sym in default_focus:
                continue  # never demote defaults
            if now - promoted_at > PROMOTION_COOLDOWN_S:
                snap = self._focus_buffer.get(sym)
                if snap and now - snap.updated_at > 60:
                    # No recent data — demote
                    to_demote.append(sym)

        for sym in to_demote:
            await self._demote(sym)

    async def _promote(self, symbol: str) -> None:
        """Move a symbol from scout to focus."""
        if symbol in self._focus_set:
            return
        logger.info("PROMOTE %s: scout → focus", symbol)
        self._focus_set.add(symbol)
        self._scout_set.discard(symbol)
        self._promotion_times[symbol] = time.time()

        # Move buffer entry
        if symbol in self._scout_buffer:
            self._focus_buffer[symbol] = self._scout_buffer.pop(symbol)

        # Subscribe to book + trade (ticker already subscribed)
        await self.ws.subscribe_book([symbol], depth=10)
        await self.ws.subscribe_trade([symbol])

    async def _demote(self, symbol: str) -> None:
        """Move a symbol from focus back to scout."""
        if symbol not in self._focus_set:
            return
        if symbol in DEFAULT_FOCUS:
            return  # never demote core symbols
        logger.info("DEMOTE %s: focus → scout", symbol)
        self._focus_set.discard(symbol)
        self._scout_set.add(symbol)
        self._promotion_times.pop(symbol, None)

        # Move buffer entry
        if symbol in self._focus_buffer:
            self._scout_buffer[symbol] = self._focus_buffer.pop(symbol)

    # ── Public API ──

    def get_focus_snapshot(self, symbol: str) -> TickerSnapshot | None:
        """Get the latest in-memory snapshot for a focus symbol."""
        return self._focus_buffer.get(symbol)

    def get_all_focus_snapshots(self) -> dict[str, TickerSnapshot]:
        return dict(self._focus_buffer)

    def get_scout_snapshot(self, symbol: str) -> TickerSnapshot | None:
        return self._scout_buffer.get(symbol)

    @property
    def focus_symbols(self) -> set[str]:
        return set(self._focus_set)

    @property
    def scout_symbols(self) -> set[str]:
        return set(self._scout_set)

    @property
    def catalog(self) -> dict[str, CatalogEntry]:
        return dict(self._catalog)

    def is_data_stale(self, threshold_s: float = 5.0) -> bool:
        """Check if any focus symbol has stale data (older than threshold)."""
        now = time.time()
        for sym in self._focus_set:
            snap = self._focus_buffer.get(sym)
            if snap is None or snap.updated_at == 0:
                continue  # never received data — might be new
            if now - snap.updated_at > threshold_s:
                return True
        return False

    def stale_symbols(self, threshold_s: float = 5.0) -> list[str]:
        """List focus symbols with data older than threshold."""
        now = time.time()
        stale: list[str] = []
        for sym in self._focus_set:
            snap = self._focus_buffer.get(sym)
            if snap and snap.updated_at > 0 and now - snap.updated_at > threshold_s:
                stale.append(sym)
        return stale
