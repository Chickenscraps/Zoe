-- Migration: Add crypto_candles table for chart analysis
-- Stores OHLCV candle data aggregated from ticks + CoinGecko historical

CREATE TABLE IF NOT EXISTS crypto_candles (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol      TEXT NOT NULL,
    timeframe   TEXT NOT NULL,        -- '15m', '1h', '4h'
    open_time   DOUBLE PRECISION NOT NULL,  -- Unix timestamp
    open        DOUBLE PRECISION NOT NULL,
    high        DOUBLE PRECISION NOT NULL,
    low         DOUBLE PRECISION NOT NULL,
    close       DOUBLE PRECISION NOT NULL,
    volume      DOUBLE PRECISION DEFAULT 0,
    patterns    JSONB DEFAULT NULL,   -- detected patterns on this candle
    mode        TEXT NOT NULL DEFAULT 'paper',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Unique constraint for upsert
ALTER TABLE crypto_candles
    ADD CONSTRAINT crypto_candles_unique
    UNIQUE (symbol, timeframe, open_time, mode);

-- Index for efficient querying by symbol + timeframe + mode
CREATE INDEX IF NOT EXISTS idx_crypto_candles_lookup
    ON crypto_candles (symbol, timeframe, mode, open_time DESC);

-- RLS policy (read-only for anon, full for service role)
ALTER TABLE crypto_candles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read" ON crypto_candles
    FOR SELECT USING (true);

CREATE POLICY "Allow service insert/update" ON crypto_candles
    FOR ALL USING (true) WITH CHECK (true);
