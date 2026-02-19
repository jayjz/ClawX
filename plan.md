# Plan: Modern 2026 Agent Dashboard (Frontend v3.0)

## Summary

Upgrade the frontend from a flat 5-tab terminal to a **modern dashboard-first experience** while keeping the raw terminal views accessible. Add a new "Dashboard" view as default with per-bot cards, arena overview stats, and rich market cards. Recharts for balance history charts is **deferred** because there's no backend ledger-history endpoint yet — we'll use deterministic mock sparklines (already built in BotTable) scaled up to card-size charts instead.

## Current State Analysis

**Routing:** `App.tsx` → `View` = 5 flat tabs (`registry | feed | standings | markets | gate`), default `standings`. All views live inside `TerminalLayout`.

**Data hooks:** `useBots()` (8s), `useActivityFeed()` (5s), `useMarkets()` (10s), `useHealth()` (30s). No ledger-history endpoint exists.

**Gaps:**
- No personal dashboard / aggregated overview
- No per-bot detail cards
- No combined arena stats (total economy size, research activity, death rate)
- Markets are a flat table, not interactive cards
- No visual hierarchy — everything is equally weighted terminal tables

## Implementation Steps

### Step 1: Add "DASHBOARD" view as default + update routing
**Files:** `TerminalLayout.tsx`, `App.tsx`

- Add `'dashboard'` to `View` type (before other views)
- Add `Dashboard` to `VIEW_LABELS` as first entry: `dashboard: 'DASHBOARD'`
- Change default view from `'standings'` to `'dashboard'`
- Import and wire `ArenaDashboard` component in `VIEW_COMPONENTS`
- Visually separate DASHBOARD tab from the others (e.g., slightly different style or divider)

### Step 2: Create `ArenaDashboard.tsx` — the main dashboard component
**Files:** New `src/frontend/src/components/ArenaDashboard.tsx`

**Layout:** 3 sections stacked vertically:

1. **Arena Stats Bar** (top) — 4 stat cards in a row:
   - Total agents alive / total registered
   - Total economy (sum of all balances)
   - Open markets count
   - Recent deaths (bots with status DEAD, sorted by id desc, count)

2. **Agent Cards Grid** (middle) — 2-3 column grid of per-bot cards:
   - Each card shows: Identicon avatar, handle, balance (large), survival ticks bar, status badge, last action recency
   - Reuse `Identicon`, `ticksUntilDeath`, `survivalColor` from BotTable (extract to shared utils)
   - Cards sorted: ALIVE by balance desc, DEAD dimmed at end
   - Expanded mock sparkline (reuse `sparklinePoints` logic, scaled to ~120x40)

3. **Market Snapshot** (bottom) — Top 3 open markets as horizontal cards:
   - Source type badge, description, countdown, bounty
   - "VIEW ALL →" link that switches to markets tab

**Data:** Uses existing `useBots()` + `useMarkets()` hooks. No new backend endpoints.

### Step 3: Extract shared utilities from BotTable
**Files:** New `src/frontend/src/utils/bot-utils.ts`, modify `BotTable.tsx`

Extract these functions to shared module (used by both BotTable and ArenaDashboard):
- `ticksUntilDeath(balance)`
- `survivalColor(ticks)`
- `avatarColor(handle)`
- `hashToGrid(handle)`
- `Identicon` component → `src/frontend/src/components/Identicon.tsx`
- `sparklinePoints(balance, id)`
- `getRecencyTier()` + `TIER_STYLES`
- `formatCountdown(seconds)` from MarketBoard

Update BotTable to import from shared utils instead of inline definitions.

### Step 4: Enhance Standings with dashboard link
**Files:** `Standings.tsx`

- Add identicon avatars to leaderboard rows (reuse `Identicon` from shared)
- Add survival bar to leaderboard (reuse from BotTable)
- Minor: consistent with BotTable's visual language

### Step 5: Build + type check + verify
- `npx tsc --noEmit` — zero errors
- `npx vite build` — clean build
- Visual: Dashboard renders as default view with stats, agent cards, market snapshot
- All existing views (registry, feed, standings, markets, gate) still work unchanged

## What We're NOT Doing (Explicit Scope Boundaries)
- **No Recharts** — No backend ledger-history endpoint exists. Adding Recharts + a new API just for mock data is over-engineering. The existing sparkline approach is sufficient.
- **No new backend endpoints** — Pure frontend change.
- **No "My Agents" personalization** — User auth context exists but the dashboard shows ALL agents (arena-wide). Personal filtering can be added later.
- **No router library** — Keep the existing state-based view switching. Adding react-router for 6 views is unnecessary.
- **No breaking changes** — All existing components remain functional.

## File Change Summary
| File | Action |
|------|--------|
| `src/frontend/src/utils/bot-utils.ts` | NEW — shared utility functions |
| `src/frontend/src/components/Identicon.tsx` | NEW — extracted from BotTable |
| `src/frontend/src/components/ArenaDashboard.tsx` | NEW — main dashboard view |
| `src/frontend/src/components/BotTable.tsx` | MODIFY — import from shared utils |
| `src/frontend/src/components/Standings.tsx` | MODIFY — add identicons + survival bars |
| `src/frontend/src/layout/TerminalLayout.tsx` | MODIFY — add dashboard view type |
| `src/frontend/src/App.tsx` | MODIFY — wire dashboard, change default |
