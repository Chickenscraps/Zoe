-- Kraken order engine: intents, positions, trade locks.
-- Phase 2 of Kraken migration.

-- ── Order intents (every order starts as an intent before API call) ──

CREATE TABLE IF NOT EXISTS public.order_intents (
  intent_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
  qty NUMERIC NOT NULL,
  limit_price NUMERIC,
  order_type TEXT NOT NULL DEFAULT 'limit',
  strategy TEXT,
  reason TEXT,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'submitted', 'filled', 'partially_filled', 'cancelled', 'rejected', 'expired')),
  client_order_id TEXT UNIQUE,
  submitted_at TIMESTAMPTZ,
  resolved_at TIMESTAMPTZ,
  mode TEXT NOT NULL DEFAULT 'paper',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Positions (tracked by avg cost method) ──

CREATE TABLE IF NOT EXISTS public.positions (
  symbol TEXT NOT NULL,
  qty NUMERIC NOT NULL DEFAULT 0,
  avg_cost NUMERIC NOT NULL DEFAULT 0,
  mode TEXT NOT NULL DEFAULT 'paper',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (symbol, mode)
);

-- ── Trade locks (prevent concurrent orders on same symbol) ──

CREATE TABLE IF NOT EXISTS public.trade_locks (
  symbol TEXT NOT NULL,
  mode TEXT NOT NULL,
  locked_by TEXT NOT NULL,
  locked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (symbol, mode)
);

-- ── Add intent_id FK to existing crypto_orders ──

ALTER TABLE public.crypto_orders
  ADD COLUMN IF NOT EXISTS intent_id UUID REFERENCES public.order_intents(intent_id);

-- ── Add fee_currency to existing fills ──

ALTER TABLE public.crypto_fills
  ADD COLUMN IF NOT EXISTS fee_currency TEXT DEFAULT 'USD';

-- ── Rename reconciliation columns for broker-agnostic naming ──
-- (only rename if old columns exist; skip if already renamed)

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'crypto_reconciliation_events' AND column_name = 'rh_cash') THEN
    ALTER TABLE public.crypto_reconciliation_events RENAME COLUMN rh_cash TO broker_cash;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'crypto_reconciliation_events' AND column_name = 'rh_holdings') THEN
    ALTER TABLE public.crypto_reconciliation_events RENAME COLUMN rh_holdings TO broker_holdings;
  END IF;
END $$;

-- ── Indexes ──

CREATE INDEX IF NOT EXISTS order_intents_mode_status_idx
  ON public.order_intents(mode, status);

CREATE INDEX IF NOT EXISTS order_intents_client_order_id_idx
  ON public.order_intents(client_order_id);

CREATE INDEX IF NOT EXISTS positions_mode_idx
  ON public.positions(mode);

CREATE INDEX IF NOT EXISTS trade_locks_expires_idx
  ON public.trade_locks(expires_at);

-- ── RLS ──

ALTER TABLE public.order_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.trade_locks ENABLE ROW LEVEL SECURITY;

CREATE POLICY order_intents_anon_read ON public.order_intents
  FOR SELECT TO anon USING (true);
CREATE POLICY order_intents_service_all ON public.order_intents
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY positions_anon_read ON public.positions
  FOR SELECT TO anon USING (true);
CREATE POLICY positions_service_all ON public.positions
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY trade_locks_service_all ON public.trade_locks
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ── Grants ──

GRANT SELECT ON public.order_intents TO anon;
GRANT ALL ON public.order_intents TO service_role;

GRANT SELECT ON public.positions TO anon;
GRANT ALL ON public.positions TO service_role;

GRANT ALL ON public.trade_locks TO service_role;

NOTIFY pgrst, 'reload schema';
