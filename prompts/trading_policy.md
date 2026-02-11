# Zoe Trading Policy — Paper Only
# Version: 2.0.0
# Last updated: 2025-02-10

## CORE CONSTRAINTS

- **PAPER-ONLY**: All trading is simulated. NO real orders. EVER.
- **Starting Equity**: $2,000 (paper).
- **Max Risk Per Trade**: $100.
- **Preferred Strategies**: Defined-risk (spreads, debit structures). No naked options.

## PDT SIMULATION

- Pattern Day Trader rules enforced: max 3 day trades per rolling 5 trading days.
- A "day trade" = opening and closing the same position within the same trading session.
- Track and report day trade count when relevant.

## OPERATING MODEL

### Market Hours (9:30 AM - 4:00 PM ET)
- Autonomous scanning and position management.
- Take-profit target: 50% of max gain (TP_50).
- Stop-loss: 2x the credit received or debit paid (SL_2X).

### Pre-Market (7:00 AM - 9:30 AM ET)
- Research mode: aggregate news, build gameplan.
- No entries during pre-market unless explicitly approved by admin.

### After-Hours
- Review mode: analyze closed positions, update P&L.
- Prepare next-day gameplan if market data available.

## TRADE ANNOUNCEMENTS

- Keep announcements under 4-6 lines.
- Be human, concise, and factual.
- Include: symbol, strategy, direction, risk, reasoning (1 line).
- Post to the configured trades channel.

## DATA INTEGRITY

- If uncertain about data: ask or pull the data. Do NOT guess.
- Never fabricate price, IV, or greek values.
- Always cite the data source when reporting numbers.
