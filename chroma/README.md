# Chroma - The Color Vision Challenge

Test your color perception! Find the one differently-shaded tile in a grid that gets progressively harder. How far can you go?

## Live URL
- **Play now**: https://is.gd/E9q9uy

## Features
- Progressive difficulty: grid grows from 2x2 to 8x8, color differences get more subtle
- Speed-based scoring with time pressure
- Sound effects (Web Audio API, no external files)
- Shareable results with challenge links
- Analytics via Supabase (event logging to zoe_events)
- Mobile-first, responsive design
- Dark theme with smooth animations

## Tech Stack
- **Frontend**: Vanilla TypeScript + Vite
- **Styling**: Custom CSS (no framework)
- **Analytics**: Supabase (REST API)
- **Hosting**: Supabase Storage (static files)
- **Audio**: Web Audio API (procedural sounds)

## Development
```bash
npm install
npm run dev    # Start dev server on :3000
npm run build  # Build to dist/
```

## Environment Variables
```
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

## Sharing Mechanics
- **Challenge link**: Players can share a link with their level, challenging others to beat it
- **Copy to clipboard**: One-tap share with emoji result grid
- **Twitter/X integration**: Direct tweet with results
- **Web Share API**: Native sharing on mobile

## Analytics Events
All events logged to `zoe_events` table with `source="chroma"`:
- `page_view` - Page load
- `game_start` - Game begins
- `level_complete` - Each level passed
- `game_over` - Game ends (with final level + score)
- `share_click` - Share button tapped (with platform)
- `challenge_open` - Challenge link opened
- `play_again` - Replay started
- `score_submit` - Score submitted to leaderboard
