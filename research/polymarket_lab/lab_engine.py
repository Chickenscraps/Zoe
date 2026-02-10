import asyncio
import logging
from .api_client import PolymarketClient
from .accounting import AccountingEngine
from .execution import ExecutionEngine
from .dashboard import Dashboard
from .signals import SignalGenerator
from .models import Market

logger = logging.getLogger(__name__)

class LabEngine:
    def __init__(self):
        self.api = PolymarketClient()
        self.accounting = AccountingEngine()
        self.execution = ExecutionEngine(self.accounting)
        self.dashboard = Dashboard(self.accounting)
        self.signals = SignalGenerator()

    async def run_daily_loop(self):
        """Main strategy research and execution loop."""
        logger.info("--- Starting Daily Research Loop ---")
        
        # 1. Market Scan
        markets = await self.api.fetch_active_markets(limit=50, min_liquidity=5000)
        logger.info(f"Scanned {len(markets)} liquid markets.")

        # 2. Hypothesis Filtering (Research Loop)
        candidates = self._filter_candidates(markets)
        logger.info(f"Found {len(candidates)} candidates matching simple niche criteria.")

        # 3. Paper Execution with Advanced Logic
        for market in candidates:
            catalyst_score = self.signals.detect_catalyst(market)
            
            # Fetch Trends for the market slug or keyword
            # Use slug as it's often more keyword-friendly
            kw = market.slug.replace('-', ' ')
            trends = self.api.fetch_trends([kw])
            trend_momentum = self.signals.detect_trend_momentum(trends, kw)
            
            # Fetch Social Sentiment (X.com)
            x_posts = self.api.fetch_x_posts(kw, limit=10)
            social_sentiment = self.signals.calculate_social_sentiment(x_posts)

            if trend_momentum > 1.5:
                logger.info(f"📈 Trend Momentum detected for '{kw}': {trend_momentum:.2f}x average")
            
            if abs(social_sentiment) > 0.3:
                sentiment_type = "Bullish" if social_sentiment > 0 else "Bearish"
                logger.info(f"🐦 Social Vibe ({sentiment_type}): {social_sentiment:.2f}")

            # Hypothesis 1: Buy low-priced catalysts
            if catalyst_score > 0.7:
                logger.info(f"🔥 Catalyst detected: {market.question} (Score: {catalyst_score:.2f})")
                
                # Boost probability if trend momentum or social vibe is high
                edge = 0.05
                if trend_momentum > 1.2 or social_sentiment > 0.5:
                    edge += 0.03
                    logger.info(f"   (Boosting edge due to positive metadata signals)")

                est_prob = market.current_yes_price + edge
                size = self.accounting.calculate_kelly_size(est_prob, market.current_yes_price)
                
                if size > 0:
                    result = self.execution.execute_paper_trade(market, "YES", size)
                    logger.info(result)

            # Hypothesis 2: Microstructure/Mispricing
            elif self.signals.check_mispricing(market) or trend_momentum > 2.0:
                # If search interest is doubling, worth a small speculative position even without catalyst
                size = self.accounting.total_equity * 0.02
                reason = "Microstructure" if self.signals.check_mispricing(market) else "Trend Surge"
                logger.info(f"✨ Speculative entry ({reason}): {market.question}")
                result = self.execution.execute_paper_trade(market, "YES", size)
                logger.info(result)


        # 4. Dashboard Reporting
        self.dashboard.render_cli()
        
        await self.api.close()

    def _filter_candidates(self, markets: list[Market]) -> list[Market]:
        """Apply niche criteria (e.g., liquidity, catalyst proximity)."""
        # Start broader to ensure some candidates for initial testing
        return [m for m in markets if m.liquidity > 1000]

async def main():
    logging.basicConfig(level=logging.INFO)
    engine = LabEngine()
    await engine.run_daily_loop()

if __name__ == "__main__":
    asyncio.run(main())
