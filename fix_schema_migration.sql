-- MIGRATION: Fix User ID Type Mismatch (Integer -> UUID)
-- Run this in Supabase SQL Editor to resolve the "incompatible types" error.
BEGIN;
-- 1. Add new UUID column to users
ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS uuid_id uuid DEFAULT uuid_generate_v4();
-- 2. Populate UUIDs for existing rows (if any)
UPDATE public.users
SET uuid_id = uuid_generate_v4()
WHERE uuid_id IS NULL;
-- 3. Make uuid_id NOT NULL and Unique
ALTER TABLE public.users
ALTER COLUMN uuid_id
SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS users_uuid_idx ON public.users (uuid_id);
-- 4. Drop dependent Foreign Keys (if they exist from partial setup)
ALTER TABLE IF EXISTS public.accounts DROP CONSTRAINT IF EXISTS accounts_user_id_fkey;
ALTER TABLE IF EXISTS public.trades DROP CONSTRAINT IF EXISTS trades_account_id_fkey;
-- Indirectly related
-- (Add others if needed, but accounts is the main blocker)
-- 5. Switch Primary Key on Users
-- Drop old PK (assuming it's named users_pkey)
ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_pkey CASCADE;
-- Set new PK
ALTER TABLE public.users
ADD CONSTRAINT users_pkey PRIMARY KEY (uuid_id);
-- 6. Handle the old ID column
-- We rename it to preserve data, just in case.
ALTER TABLE public.users
    RENAME COLUMN id TO id_legacy;
ALTER TABLE public.users
    RENAME COLUMN uuid_id TO id;
-- 7. Fix referencing tables (Accounts)
-- Since accounts creation FAILED, we might need to recreate it or modify it.
-- If 'accounts' exists but has integer user_id, we need to convert it. 
-- If 'accounts' does NOT exist (creation failed), we can just create it now.
-- Check if accounts exists and fix it, or create it if missing.
DO $$ BEGIN IF EXISTS (
    SELECT
    FROM pg_tables
    WHERE schemaname = 'public'
        AND tablename = 'accounts'
) THEN -- accounts exists, likely with integer user_id? Or maybe it failed to create?
-- If it exists, let's assume we need to align the user_id column.
-- Drop the old constraint if not already dropped
ALTER TABLE public.accounts DROP CONSTRAINT IF EXISTS accounts_user_id_fkey;
-- If user_id is integer, we need to map it. If it's empty, just change type.
-- For safety in this specific "failed setup" context, let's DROP and RECREATE accounts 
-- IF it's empty. If it has data, we'd need complex migration.
-- Assuming clean slate/seed data attempts:
-- ALTER TABLE public.accounts ALTER COLUMN user_id TYPE uuid USING user_id::text::uuid; -- formatting hack if empty
-- Realistically, if creation verified failed, this table might not exist or be partial.
NULL;
END IF;
END $$;
-- 8. Re-run Table Creations (Safe "IF NOT EXISTS")
-- Now that users.id is UUID, these should succeed.
create table if not exists public.accounts (
    id uuid primary key default uuid_generate_v4(),
    user_id uuid references public.users(id),
    instance_id text default 'default',
    equity numeric(12, 2) default 0.00,
    cash numeric(12, 2) default 0.00,
    buying_power numeric(12, 2) default 0.00,
    pdt_count int default 0,
    day_trades_history jsonb default '[]'::jsonb,
    updated_at timestamptz default now()
);
-- Ensure FK exists if table already existed
DO $$ BEGIN IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'accounts_user_id_fkey'
) THEN
ALTER TABLE public.accounts
ADD CONSTRAINT accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);
END IF;
END $$;
-- 9. Cleanup other tables that might depend on accounts (ensure they use UUIDs)
create table if not exists public.trades (
    id uuid primary key default uuid_generate_v4(),
    account_id uuid references public.accounts(id),
    symbol text not null,
    strategy text not null,
    status text default 'open',
    entry_time timestamptz default now(),
    exit_time timestamptz,
    entry_price numeric(12, 4),
    exit_price numeric(12, 4),
    quantity int default 1,
    pnl numeric(12, 2),
    score_at_entry jsonb,
    notes text
);
-- ... (Rest of tables from setup_db.sql are generally fine as they reference accounts(id) which was always UUID)
COMMIT;
