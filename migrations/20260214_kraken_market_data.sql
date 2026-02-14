-- Kraken market data tables: catalog, focus snapshots, scout snapshots.
-- Phase 1 of Kraken migration.

-- ── Market catalog (all tradeable pairs with metadata) ──

CREATE TABLE IF NOT EXISTS public.market_catalog (
  symbol TEXT PRIMARY KEY,              -- "BTC/USD"
  base_asset TEXT NOT NULL,
  quote_asset TEXT NOT NULL,
  lot_decimals INT NOT NULL DEFAULT 8,
  pair_decimals INT NOT NULL DEFAULT 1,
  lot_min NUMERIC NOT NULL DEFAULT 0,
  cost_min NUMERIC NOT NULL DEFAULT 0,
  tick_size NUMERIC,
  status TEXT NOT NULL DEFAULT 'online',
  ordermin NUMERIC,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Focus snapshots (high-priority symbols, updated sub-second) ──

CREATE TABLE IF NOT EXISTS public.market_snapshot_focus (
  symbol TEXT PRIMARY KEY,
  bid NUMERIC,
  ask NUMERIC,
  mid NUMERIC,
  last_price NUMERIC,
  volume_24h NUMERIC,
  change_pct_24h NUMERIC,
  spread_bps NUMERIC,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Scout snapshots (broad universe, updated every ~10s) ──

CREATE TABLE IF NOT EXISTS public.market_snapshot_scout (
  symbol TEXT PRIMARY KEY,
  mid NUMERIC,
  volume_24h NUMERIC,
  change_pct_24h NUMERIC,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Relax source CHECK constraints to support Kraken ──

ALTER TABLE public.crypto_cash_snapshots
  DROP CONSTRAINT IF EXISTS crypto_cash_snapshots_source_check;
ALTER TABLE public.crypto_cash_snapshots
  ADD CONSTRAINT crypto_cash_snapshots_source_check
  CHECK (source IN ('robinhood', 'kraken'));

ALTER TABLE public.crypto_holdings_snapshots
  DROP CONSTRAINT IF EXISTS crypto_holdings_snapshots_source_check;
ALTER TABLE public.crypto_holdings_snapshots
  ADD CONSTRAINT crypto_holdings_snapshots_source_check
  CHECK (source IN ('robinhood', 'kraken'));

-- ── RLS: anon can read, service_role has full access ──

ALTER TABLE public.market_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.market_snapshot_focus ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.market_snapshot_scout ENABLE ROW LEVEL SECURITY;

CREATE POLICY market_catalog_anon_read ON public.market_catalog
  FOR SELECT TO anon USING (true);
CREATE POLICY market_catalog_service_all ON public.market_catalog
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY market_snapshot_focus_anon_read ON public.market_snapshot_focus
  FOR SELECT TO anon USING (true);
CREATE POLICY market_snapshot_focus_service_all ON public.market_snapshot_focus
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY market_snapshot_scout_anon_read ON public.market_snapshot_scout
  FOR SELECT TO anon USING (true);
CREATE POLICY market_snapshot_scout_service_all ON public.market_snapshot_scout
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ── Grants ──

GRANT SELECT ON public.market_catalog TO anon;
GRANT ALL ON public.market_catalog TO service_role;

GRANT SELECT ON public.market_snapshot_focus TO anon;
GRANT ALL ON public.market_snapshot_focus TO service_role;

GRANT SELECT ON public.market_snapshot_scout TO anon;
GRANT ALL ON public.market_snapshot_scout TO service_role;

-- Reload PostgREST schema cache
NOTIFY pgrst, 'reload schema';
