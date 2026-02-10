from datetime import datetime
from typing import List, Optional, Dict, Any
from .models import Market

class SignalGenerator:
    @staticmethod
    def detect_catalyst(market: Market) -> float:
        """
        Calculates a 'Catalyst Score' based on proximity to end date.
        Higher score means the market is nearing resolution with high volume.
        """
        if not market.end_date_iso:
            return 0.0
            
        try:
            end_date = datetime.fromisoformat(market.end_date_iso.replace('Z', '+00:00'))
            now = datetime.now().astimezone()
            days_to_expiry = (end_date - now).days
            
            if days_to_expiry < 0:
                return 0.0
            
            # Score: High volume + Low days to expiry
            # Example: 1.0 if < 3 days and volume > 100k
            volume_factor = min(market.volume / 100000, 1.0)
            expiry_factor = 1.0 - (min(days_to_expiry, 14) / 14.0)
            
            return volume_factor * expiry_factor
        except Exception:
            return 0.0

    @staticmethod
    def check_mispricing(market: Market) -> bool:
        """
        Basic heuristic: High liquidity but 'odd' price distribution
        (Placeholder for more complex microstructure analysis)
        """
        return market.liquidity > 50000 and (0.1 < market.current_yes_price < 0.2)

    @staticmethod
    def detect_trend_momentum(trends: Dict[str, Any], keyword: str) -> float:
        """
        Calculates momentum based on Google Trends data.
        Returns a score (ratio of recent peak vs average).
        """
        if not trends or keyword not in trends:
            return 0.0
        
        values = list(trends[keyword].values())
        if not values or len(values) < 3:
            return 0.0
            
        avg_interest = sum(values[:-1]) / len(values[:-1])
        recent_interest = values[-1]
        
        if avg_interest == 0:
            return 1.0 if recent_interest > 0 else 0.0
            
        momentum = recent_interest / avg_interest
        return momentum

    @staticmethod
    def calculate_social_sentiment(posts: List[str]) -> float:
        """
        Calculates a simple sentiment score (-1 to 1) from a list of strings.
        Note: In a research lab, we'd use a small model (like VADER or an LLM call).
        Here we use a keyword-based heuristic for performance.
        """
        if not posts:
            return 0.0
            
        positive_words = {'bullish', 'moon', 'up', 'long', 'buy', 'undervalued', 'winner'}
        negative_words = {'bearish', 'dump', 'down', 'short', 'sell', 'overvalued', 'loser'}
        
        score = 0.0
        total_words = 0
        
        for post in posts:
            words = post.lower().split()
            total_words += len(words)
            for word in words:
                if word in positive_words:
                    score += 1.0
                elif word in negative_words:
                    score -= 1.0
                    
        # Normalize by volume of mentions
        if total_words == 0:
            return 0.0
        return score / (len(posts) * 0.5) # Arbitrary scaling for signal strength
