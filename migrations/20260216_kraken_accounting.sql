-- Kraken accounting: fee ledger, enhanced PnL.
-- Phase 3 of Kraken migration.

-- ── Fee ledger (every fill records its fee separately for audit) ──

CREATE TABLE IF NOT EXISTS public.fee_ledger (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fill_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  fee NUMERIC NOT NULL,
  fee_currency TEXT NOT NULL DEFAULT 'USD',
  fee_usd NUMERIC NOT NULL,
  mode TEXT NOT NULL DEFAULT 'paper',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Enhance pnl_daily with new columns ──

ALTER TABLE public.pnl_daily ADD COLUMN IF NOT EXISTS gross_equity NUMERIC DEFAULT 0;
ALTER TABLE public.pnl_daily ADD COLUMN IF NOT EXISTS fees_usd NUMERIC DEFAULT 0;
ALTER TABLE public.pnl_daily ADD COLUMN IF NOT EXISTS positions_count INT DEFAULT 0;

-- ── Indexes ──

CREATE INDEX IF NOT EXISTS fee_ledger_mode_created_idx
  ON public.fee_ledger(mode, created_at DESC);

CREATE INDEX IF NOT EXISTS fee_ledger_fill_id_idx
  ON public.fee_ledger(fill_id);

-- ── RLS ──

ALTER TABLE public.fee_ledger ENABLE ROW LEVEL SECURITY;

CREATE POLICY fee_ledger_anon_read ON public.fee_ledger
  FOR SELECT TO anon USING (true);
CREATE POLICY fee_ledger_service_all ON public.fee_ledger
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- ── Grants ──

GRANT SELECT ON public.fee_ledger TO anon;
GRANT ALL ON public.fee_ledger TO service_role;

NOTIFY pgrst, 'reload schema';
