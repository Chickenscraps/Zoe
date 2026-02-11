-- FIX USERS SCHEMA & SEED DATA
-- Run this in Supabase SQL Editor
BEGIN;
-- 1. Add missing columns expected by the application
ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS discord_id text;
ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS last_seen timestamptz DEFAULT now();
-- 2. Add Unique Constraint to discord_id
-- (Safe to do even if empty)
DO $$ BEGIN IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'users_discord_id_key'
) THEN
ALTER TABLE public.users
ADD CONSTRAINT users_discord_id_key UNIQUE (discord_id);
END IF;
END $$;
-- 3. Run Seed Data (Now that columns exist)
-- Create/Ensure User
INSERT INTO public.users (discord_id, username, password_hash)
VALUES (
        '292890243852664855',
        'Chickenscraps',
        'placeholder_hash_managed_by_bot'
    ) ON CONFLICT (discord_id) DO
UPDATE
SET username = EXCLUDED.username;
-- Create/Ensure Account
DO $$
DECLARE v_user_id uuid;
BEGIN
SELECT id INTO v_user_id
FROM public.users
WHERE discord_id = '292890243852664855';
IF v_user_id IS NOT NULL THEN
INSERT INTO public.accounts (user_id, instance_id, equity, cash, buying_power)
VALUES (v_user_id, 'default', 2000.00, 2000.00, 2000.00) ON CONFLICT DO NOTHING;
END IF;
END $$;
COMMIT;
