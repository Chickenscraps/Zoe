-- Phase 3: Accounting overhaul — new tables + column extensions
-- Run after 20260213_market_data_tables.sql

-- ============================================================
-- 1. Extend crypto_fills with broker-specific fields
-- ============================================================
ALTER TABLE crypto_fills ADD COLUMN IF NOT EXISTS broker_fee NUMERIC(20,8) DEFAULT 0;
ALTER TABLE crypto_fills ADD COLUMN IF NOT EXISTS fee_currency TEXT DEFAULT 'USD';
ALTER TABLE crypto_fills ADD COLUMN IF NOT EXISTS broker_fill_id TEXT;
ALTER TABLE crypto_fills ADD COLUMN IF NOT EXISTS exchange TEXT DEFAULT 'kraken';

-- ============================================================
-- 2. Cash events (deposits / withdrawals) — NOT P&L
-- ============================================================
CREATE TABLE IF NOT EXISTS cash_events (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    event_type  TEXT NOT NULL CHECK (event_type IN ('deposit', 'withdrawal', 'transfer_in', 'transfer_out')),
    amount      NUMERIC(20,8) NOT NULL,
    currency    TEXT DEFAULT 'USD',
    description TEXT DEFAULT '',
    external_ref TEXT DEFAULT '',
    created_at  TIMESTAMPTZ DEFAULT now(),
    mode        TEXT DEFAULT 'paper' CHECK (mode IN ('paper', 'live'))
);

CREATE INDEX IF NOT EXISTS idx_cash_events_mode_created
    ON cash_events (mode, created_at DESC);

-- ============================================================
-- 3. Fee ledger — per-fill fee tracking
-- ============================================================
CREATE TABLE IF NOT EXISTS fee_ledger (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    fill_id     TEXT NOT NULL,
    order_id    TEXT DEFAULT '',
    symbol      TEXT NOT NULL,
    fee_amount  NUMERIC(20,8) NOT NULL DEFAULT 0,
    fee_currency TEXT DEFAULT 'USD',
    fee_type    TEXT DEFAULT 'trading' CHECK (fee_type IN ('trading', 'withdrawal', 'deposit', 'other')),
    created_at  TIMESTAMPTZ DEFAULT now(),
    mode        TEXT DEFAULT 'paper' CHECK (mode IN ('paper', 'live')),
    CONSTRAINT uq_fee_ledger_fill UNIQUE (fill_id)
);

CREATE INDEX IF NOT EXISTS idx_fee_ledger_mode_created
    ON fee_ledger (mode, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_fee_ledger_symbol
    ON fee_ledger (symbol);

-- ============================================================
-- 4. Extend pnl_daily with richer columns
-- ============================================================
ALTER TABLE pnl_daily ADD COLUMN IF NOT EXISTS fees_paid NUMERIC(20,8) DEFAULT 0;
ALTER TABLE pnl_daily ADD COLUMN IF NOT EXISTS gross_equity NUMERIC(20,8);
ALTER TABLE pnl_daily ADD COLUMN IF NOT EXISTS net_equity NUMERIC(20,8);
ALTER TABLE pnl_daily ADD COLUMN IF NOT EXISTS net_deposits NUMERIC(20,8) DEFAULT 0;
ALTER TABLE pnl_daily ADD COLUMN IF NOT EXISTS crypto_value NUMERIC(20,8) DEFAULT 0;
ALTER TABLE pnl_daily ADD COLUMN IF NOT EXISTS cash_usd NUMERIC(20,8) DEFAULT 0;

-- ============================================================
-- 5. RLS policies (anon read for dashboard)
-- ============================================================
ALTER TABLE cash_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_cash_events" ON cash_events
    FOR SELECT USING (true);

ALTER TABLE fee_ledger ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_fee_ledger" ON fee_ledger
    FOR SELECT USING (true);

-- ============================================================
-- Notes:
-- - cash_events tracks deposits/withdrawals separately from trading P&L
-- - fee_ledger provides per-fill fee attribution for cost analysis
-- - pnl_daily now carries fees_paid, crypto_value, cash_usd for proper MTM equity
-- - broker_fee on crypto_fills captures the exact Kraken fee per fill
-- ============================================================
