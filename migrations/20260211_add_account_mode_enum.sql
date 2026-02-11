-- Migration: Add Account Mode and Active Status
-- Description: Separates Paper vs Live accounts using an Enum and ensures only one active LIVE account per user.
BEGIN;
-- 1. Create Enum 'account_mode' if it doesn't exist
DO $$ BEGIN CREATE TYPE account_mode AS ENUM ('PAPER', 'LIVE');
EXCEPTION
WHEN duplicate_object THEN null;
END $$;
-- 2. Add columns to 'accounts' table
ALTER TABLE public.accounts
ADD COLUMN IF NOT EXISTS mode account_mode NOT NULL DEFAULT 'PAPER';
ALTER TABLE public.accounts
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;
-- 3. Create Safety Index: Only one active LIVE account per user
-- Drop first to ensure idempotency if we are re-running
DROP INDEX IF EXISTS one_active_live_account_per_user;
CREATE UNIQUE INDEX one_active_live_account_per_user ON public.accounts (user_id)
WHERE (
        mode = 'LIVE'
        AND is_active = true
    );
-- 4. Create Index for fast filtering by mode
DROP INDEX IF EXISTS idx_accounts_mode;
CREATE INDEX idx_accounts_mode ON public.accounts(mode);
COMMIT;
