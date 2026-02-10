// ZOE V4 DASHBOARD - API EXAMPLES
// Pass this file to the Dashboard Agent / Frontend Developer.

import { createClient } from '@supabase/supabase-js'

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

/**
 * 1. GET ACCOUNT HEADER
 * Returns: { equity, cash, buying_power, day_pnl, ... }
 */
async function getHeader() {
  const { data, error } = await supabase.rpc('get_account_overview', { 
    p_discord_id: '292890243852664855' // specific user
    // or leave empty for default
  })
  if (error) console.error(error)
  return data?.[0] || {}
}

/**
 * 2. GET OPEN POSITIONS
 * Returns: [ { symbol: 'SPY', quantity: 1, unrealized_pnl: 50.00, ... }, ... ]
 */
async function getPositions() {
  const { data, error } = await supabase.rpc('get_positions_report')
  if (error) console.error(error)
  return data || []
}

/**
 * 3. GET ACTIVITY FEED
 * Returns: [ { type: 'TRADE', details: 'buy 1 @ $500', event_ts: '...' }, ... ]
 */
async function getFeed() {
  const { data, error } = await supabase.rpc('get_activity_feed', { p_limit: 20 })
  if (error) console.error(error)
  return data || []
}

// USAGE
/*
const header = await getHeader()
document.getElementById('equity').innerText = `$${header.equity}`

const positions = await getPositions()
positions.forEach(p => renderPositionRow(p))

const feed = await getFeed()
feed.forEach(item => renderFeedItem(item))
*/
