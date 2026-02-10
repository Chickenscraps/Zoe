import pandas as pd
import pandas_ta as ta
from datetime import datetime, timedelta
from market_data import market_data

class MarketRegime:
    """Detects market conditions: Volatility (IVR) and Trend (ADX/SMA)."""
    
    def get_regime(self, symbol: str) -> dict:
        """
        Determine if regime is High/Low Vol and Bull/Bear/Neutral.
        """
        # Fetch history (last 100 days)
        data = market_data.get_history(symbol, limit=100)
        if not data or len(data) < 60:
            return None # Not enough data
            
        df = pd.DataFrame(data)
        # Sort ascending for TA
        df = df.sort_values('timestamp')
        
        # Calculate Indicators
        # ADX (14)
        try:
            adx_df = df.ta.adx(high=df['high'], low=df['low'], close=df['close'], length=14)
            adx = adx_df['ADX_14'].iloc[-1]
        except:
            adx = 20.0 # Default/Error
            
        # SMA (50)
        try:
            sma_50 = df.ta.sma(close=df['close'], length=50).iloc[-1]
            current_close = df['close'].iloc[-1]
        except:
            sma_50 = 0
            current_close = 0
            
        # Direction
        if current_close > sma_50:
            direction = "bullish"
        elif current_close < sma_50:
            direction = "bearish"
        else:
            direction = "neutral"
            
        # Volatility Regime (Mock IVR for now, or use ATR/HV)
        # Real IVR requires 52w IV range. We don't have that yet.
        # We'll use a placeholder driven by recent volatility?
        # Or just random for dev? No, be deterministic.
        # Use simple ATR relative to price?
        # atr = df.ta.atr(length=14).iloc[-1]
        # For now, we assume "Market Data" provides current IV.
        # We will classify based on absolute IV for prototype (e.g. > 30% is high)
        # This is inaccurate but functional for testing pipeline.
        
        return {
            "adx": adx,
            "direction": direction,
            "sma_50": sma_50,
            "close": current_close,
            "timestamp": datetime.now()
        }

class ScoringEngine:
    """Calculates trade quality score (0-100)."""
    
    def calculate_score(self, regime: dict, ivr: float, liquidity_score: float = 80) -> float:
        """
        S = 0.3V + 0.25T + 0.25L + 0.2E (Efficiency ignored for now)
        """
        # V (Volatility Score)
        # If Credit Strategy: V = IVR
        v_score = ivr
        
        # T (Trend Score)
        # If Bullish and Trend Strong (ADX>25) -> High
        adx = regime.get('adx', 0)
        t_score = 50.0
        if adx > 25: t_score = 90.0
        elif adx < 20: t_score = 10.0
        
        l_score = liquidity_score
        e_score = 50.0 # Placeholder
        
        score = (0.3 * v_score) + (0.25 * t_score) + (0.25 * l_score) + (0.20 * e_score)
        return min(max(score, 0), 100)

class SignalGenerator:
    """Generates trade candidates based on strategies."""
    
    def __init__(self, regime_engine: MarketRegime, scoring_engine: ScoringEngine):
        self.regime = regime_engine
        self.scoring = scoring_engine
    
    def scan(self, symbols: list):
        """Scan list of symbols for setups."""
        candidates = []
        for sym in symbols:
            print(f"Scanning {sym}...")
            regime = self.regime.get_regime(sym)
            if not regime: continue
            
            # Fetch Option Chain
            chain = market_data.get_option_chain_snapshot(sym)
            if not chain: continue
            
            # 1. Calculate IVR (Mock from chain average IV)
            # Filter valid IVs
            ivs = [opt['implied_volatility'] for opt in chain if opt['implied_volatility']]
            avg_iv = (sum(ivs)/len(ivs) * 100) if ivs else 30.0
            ivr = min(avg_iv * 1.5, 100) # Pseudo-IVR (Current IV scaled)
            
            # 2. Determine Strategy based on Regime
            setup_type = None
            if regime['direction'] == 'bullish' and ivr > 30:
                setup_type = 'bull_put_credit_spread'
            elif regime['direction'] == 'bearish' and ivr > 30:
                setup_type = 'bear_call_credit_spread'
            else:
                continue # Skip low IV or uncertain logic for now
                
            # 3. Find Strikes (Delta ~ 0.30)
            target_dte_min, target_dte_max = 30, 45
            
            # Filter by DTE
            valid_opts = []
            now = datetime.now()
            for opt in chain:
                if not opt['expiry']: continue
                expiry = datetime.strptime(opt['expiry'], "%Y-%m-%d")
                dte = (expiry - now).days
                if target_dte_min <= dte <= target_dte_max:
                    valid_opts.append(opt)
            
            if not valid_opts: continue
            
            # Select Short Leg (Delta ~ 0.30)
            # Bull Put: Sell Put (Delta -0.30?), Buy Put (Lower strike)
            # Bear Call: Sell Call (Delta 0.30), Buy Call (Higher strike)
            
            legs = []
            score = 0
            
            if setup_type == 'bull_put_credit_spread':
                # Puts have negative delta. Target -0.30
                puts = [o for o in valid_opts if o['type'] == 'put' and o['delta'] is not None]
                # Sort by distance to -0.30
                puts.sort(key=lambda x: abs(float(x['delta'] or 0) - (-0.30)))
                
                if not puts: continue
                short_leg = puts[0]
                
                # Long leg: Strike < Short Strike (e.g. $5 wide)
                short_strike = short_leg['strike']
                target_long = short_strike - 5 # Simple $5 width logic
                
                # Find closest match
                long_candidates = [o for o in valid_opts if o['type'] == 'put' and o['strike'] < short_strike]
                long_candidates.sort(key=lambda x: abs(x['strike'] - target_long))
                
                if long_candidates:
                    long_leg = long_candidates[0]
                    legs = [short_leg, long_leg]
                    
            elif setup_type == 'bear_call_credit_spread':
                # Calls have positive delta. Target 0.30
                calls = [o for o in valid_opts if o['type'] == 'call' and o['delta'] is not None]
                calls.sort(key=lambda x: abs(float(x['delta'] or 0) - 0.30))
                
                if not calls: continue
                short_leg = calls[0]
                
                # Long leg: Strike > Short Strike
                short_strike = short_leg['strike']
                target_long = short_strike + 5
                
                long_candidates = [o for o in valid_opts if o['type'] == 'call' and o['strike'] > short_strike]
                long_candidates.sort(key=lambda x: abs(x['strike'] - target_long))
                
                if long_candidates:
                    long_leg = long_candidates[0]
                    legs = [short_leg, long_leg]
            
            if legs:
                # Calculate Score
                score = self.scoring.calculate_score(regime, ivr)
                
                candidates.append({
                    "symbol": sym,
                    "strategy": setup_type,
                    "score": round(score, 1),
                    "legs": legs,
                    "reason": f"Regime: {regime['direction'].upper()}, IVR: {round(ivr)}, ADX: {round(regime['adx'],1)}"
                })
                
        return candidates

trade_engine = SignalGenerator(MarketRegime(), ScoringEngine())
