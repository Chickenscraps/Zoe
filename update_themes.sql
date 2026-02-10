-- 5. Themes (Social Archetypes)
create table if not exists themes (
    id uuid default gen_random_uuid() primary key,
    content text not null,
    -- The theme (e.g., "tools that feel like rituals")
    type text default 'social_archetype',
    -- "social_archetype" or "user_specific"
    embedding vector(1536),
    -- For semantic matching
    created_at timestamp with time zone default now(),
    last_used timestamp with time zone -- To avoid repetition
);
-- Seed some initial themes from the user's prompt
insert into themes (content)
values ('tools that feel like thoughts'),
    ('false memories'),
    ('friendly recursion'),
    ('hyperfocus rituals'),
    ('paranoid design'),
    ('failing beautifully');
