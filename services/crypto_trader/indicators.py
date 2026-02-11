from __future__ import annotations

import pandas as pd
import numpy as np
from typing import List
from .market_data import Candle

class TechnicalAnalysis:
    @staticmethod
    def calculate_indicators(candles: List[Candle]) -> pd.DataFrame:
        if not candles:
            return pd.DataFrame()
            
        # Convert to DataFrame
        data = [
            {
                "timestamp": c.bucket,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume
            }
            for c in candles
        ]
        df = pd.DataFrame(data).sort_values("timestamp")
        
        # SMA
        df["sma_50"] = df["close"].rolling(window=50).mean()
        df["sma_200"] = df["close"].rolling(window=200).mean()
        
        # RSI 14
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        
        rs = gain / loss
        df["rsi_14"] = 100 - (100 / (1 + rs))
        
        # Signal
        # Bullish: SMA 50 > SMA 200
        df["trend"] = np.where(df["sma_50"] > df["sma_200"], "bull", "bear")
        
        return df.tail(1) # Return latest
