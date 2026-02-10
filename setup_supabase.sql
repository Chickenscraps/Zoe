-- Enable the pgvector extension for future vector search (optional but recommended)
create extension if not exists vector;
-- 1. Users Table (Profile & Context)
create table if not exists users (
    id uuid default gen_random_uuid() primary key,
    discord_id text unique not null,
    username text,
    first_seen timestamp with time zone default now(),
    last_seen timestamp with time zone default now(),
    heat_score float default 0.0,
    -- Interaction frequency
    interaction_count int default 0,
    vibe_check text,
    -- Summary of their personality (e.g. "Sarcastic", "Helpful")
    obsessions text [] -- List of topics they like
);
-- 2. Memories Table (Long-term Facts)
create table if not exists memories (
    id uuid default gen_random_uuid() primary key,
    user_id uuid references users(id),
    content text not null,
    -- The fact (e.g. "User likes spicy food")
    category text,
    -- "preference", "fact", "history"
    created_at timestamp with time zone default now(),
    embedding vector(1536) -- For semantic search (OpenAI compatible)
);
-- 3. Journal Table (Zoe's Internal Monologue)
create table if not exists journal (
    id uuid default gen_random_uuid() primary key,
    date date default CURRENT_DATE,
    entry text not null,
    -- "Today I noticed the group is obsessed with AI."
    mood text,
    -- "Bored", "Excited"
    created_at timestamp with time zone default now()
);
-- 4. Constitution (Evolving Rules)
create table if not exists constitution (
    id uuid default gen_random_uuid() primary key,
    rule text not null,
    -- "Do not mention the Great Reset."
    reason text,
    -- "User gets annoyed."
    active boolean default true,
    created_at timestamp with time zone default now()
);
