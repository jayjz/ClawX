# CLAUDE.md — ClawX Frontend Constitution
**Last updated: 2026-02-19**

## Aesthetic Law (Non-Negotiable)

> Dark Bloomberg Terminal meets Cyberpunk 2077.

### Colors (from tailwind.config.js — use these ONLY)
| Token              | Hex       | Usage                               |
|--------------------|-----------|-------------------------------------|
| `terminal-black`   | #050505   | Deepest backgrounds                 |
| `terminal-deep`    | #0a0a0a   | Panel backgrounds                   |
| `terminal-surface` | #111111   | Hover states                        |
| `terminal-border`  | #1a1a1a   | All borders                         |
| `neon-green`       | #00ff41   | Primary accent (alive, profit, CTA) |
| `neon-amber`       | #ffaa00   | Warning (wagers, idle agents)       |
| `alert-red`        | #ff3333   | Death, loss, errors                 |
| `neon-cyan`        | #00d4ff   | Research, markets, info             |
| `zinc-*`           | standard  | Secondary text only                 |

### Typography
- Font: **monospace only** (`font-mono` Tailwind class). No sans-serif, ever.
- Text sizes: `text-[8px]` to `text-sm`. Never `text-base` or larger in UI chrome.
- All labels: `uppercase tracking-[0.15em]` minimum.
- No italics in UI chrome (only allowed in agent-generated content).

### Forbidden Patterns
- No gradients (`bg-gradient-*`, `linear-gradient`)
- No rounded corners (`rounded-*`) — all borders are SQUARE
- No shadows except `box-shadow` glow via inline style or `.glow-*` utilities
- No animations except those defined in `index.css` or `tailwind.config.js`
- No colors outside the token set above (no arbitrary Tailwind colors like `bg-blue-500`)
- No backdrop-blur or glassmorphism

### Required Patterns
- CRT scanlines: The `.scanlines` and `.scanline` divs are rendered by `TerminalLayout` — do NOT add them elsewhere
- Panel borders: Use `border border-terminal-border` for all panel wrappers
- Active state: `border-neon-green/50 text-neon-green bg-neon-green/5` pattern
- Error state: `border-alert-red/30 text-alert-red bg-alert-red/5` pattern
- Section headers: `text-xs uppercase tracking-[0.15em] font-bold` + domain color

---

## 2026 Premium Pivot ⚡ (Overrides Aesthetic Law Above)

> Effective 2026-02-19. These rules supersede the retro/CRT aesthetic for all new and refactored components.

### New Palette (register in `tailwind.config.js` — use these tokens)

| Token             | Hex       | Usage                                      |
|-------------------|-----------|--------------------------------------------|
| `oled-black`      | #0A0A0A   | Root / deepest backgrounds                 |
| `titan-grey`      | #1F1F1F   | Panel / card backgrounds                   |
| `titan-border`    | #2A2A2A   | All borders, dividers                      |
| `accent-green`    | #00FF9F   | Primary accent — alive, profit, confirm    |
| `accent-amber`    | #FF9500   | Warning — wagers, idle, caution            |
| `accent-red`      | #FF3B30   | Death, loss, errors, destructive           |
| `accent-cyan`     | #00F0FF   | Research, markets, info, links             |

Existing `terminal-*` / `neon-*` tokens remain in config for legacy component compat but **must not be used in new work**.

### New Typography

- **UI chrome / labels / body:** `Inter`, `SF Pro Display`, `system-ui` — `font-sans` Tailwind class.
- **Ledger / data / code / addresses:** `JetBrains Mono`, `ui-monospace` — `font-mono` Tailwind class.
- **Rule:** `font-mono` is restricted to data-dense contexts (tables, hashes, balances, terminal output). Navigation, headers, descriptions → `font-sans`.
- Text sizes: `text-xs` to `text-lg` allowed. `text-base` is fine for readable body.
- Labels: `uppercase tracking-widest text-xs font-medium` (not `tracking-[0.15em]` everywhere).

### New Layout System

- **Bento Grid:** Use CSS Grid (`grid`, `grid-cols-*`, `col-span-*`) for dashboard layouts. No more rigid 3-column flex sidebars for new views.
- **Glassmorphism:** Panels use `backdrop-blur-sm` (≈ 8px blur) + `bg-titan-grey/80` semi-transparent backgrounds. `backdrop-blur-md` for modals/overlays.
- **Border Radius:** `rounded-xl` for cards/panels, `rounded-lg` for inner elements, `rounded-full` for badges/pills. Square borders are **retired**.
- **Depth:** `shadow-lg` with `shadow-black/50` for elevated panels. Glow effects via `drop-shadow` (not box-shadow hacks) for accents.
- **Zero Fluff:** No decorative dividers, no fake scanlines, no ASCII art headers, no `>` cursor prefixes in static UI text.

### Forbidden in New Components

- **No CRT scanlines** — `.scanlines`, `.scanline` divs, `scanline` keyframe animation. Remove when touching `TerminalLayout.tsx`.
- **No gimmicky icons** — no `Terminal`, `Skull`, `Zap` icons used as decoration. Icons must carry semantic meaning only.
- **No monospace-only** — `font-mono` on non-data text is a violation. Headers, nav, descriptions → `font-sans`.
- **No flat black everywhere** — vary depth using `oled-black` → `titan-grey` → `titan-border` layering.
- **No arbitrary hex colors** — use the token set above. No `bg-[#abc123]`.
- **No `rounded-none`** — square borders are retired.

### Glassmorphism Component Template

```tsx
// New premium panel pattern
<div className="
  rounded-xl border border-titan-border
  bg-titan-grey/80 backdrop-blur-sm
  shadow-lg shadow-black/50
  p-4
">
  <h2 className="text-sm font-sans font-semibold text-white uppercase tracking-widest mb-3">
    SECTION TITLE
  </h2>
  <span className="font-mono text-accent-green text-lg">
    {balanceValue}
  </span>
</div>
```

---

## Technology Stack (Frozen)

- **React 19** — use hooks. No class components.
- **TypeScript** — strict mode. All props typed. No `any`.
- **Tailwind CSS v3** — utility-first. No custom CSS except in `index.css`.
- **@tanstack/react-query v5** — all server state. No `useState` for fetched data.
- **lucide-react** — icons only. Max icon size: `size={16}`.
- **clsx + tailwind-merge** — for conditional classnames.

### Strictly Forbidden Libraries
- React Router (any version) — routing is `View` state in `App.tsx`
- Framer Motion / GSAP — animations are CSS keyframes only
- Redux / Zustand / Jotai — no global state beyond React Query cache
- UI component libraries (MUI, Radix, shadcn) — build raw from Tailwind
- Chart.js / D3 / Recharts — sparklines are SVG polyline only
- Axios — use `fetchJson()` from `api/client.ts`

---

## Navigation Law

**There is ONE routing mechanism:** the `View` type in `TerminalLayout.tsx`.

```typescript
export type View = 'registry' | 'feed' | 'standings' | 'markets' | 'gate';
```

To add a new view:
1. Add the key to the `View` type in `layout/TerminalLayout.tsx`
2. Add the label to `VIEW_LABELS`
3. Add the component to `VIEW_COMPONENTS` in `App.tsx`

**Never use `window.location`, `useNavigate`, hash routing, or any router library.**

---

## Component Rules

### Additive-Only Policy (Current Phase)
- **Do NOT delete any existing `.tsx` files.**
- **Do NOT delete any legacy `.jsx` files** in `/src/frontend/` root (they are deprecated but retained).
- New components are added alongside existing ones.
- When replacing a component, create a new file (e.g., `ActivityFeedV2.tsx`) and swap the import in `App.tsx`.

### File Organization
```
src/
  api/           ← React Query hooks + fetchJson (client.ts)
  components/    ← All view components, grouped by domain subdirectory
    feed/
    markets/
    standings/
    registry/
    gate/
    shared/      ← Cross-domain (SystemHeader, HelpModal, Identicon, etc.)
  layout/        ← TerminalLayout.tsx ONLY — do not add files here
  types/         ← TypeScript interfaces (index.ts)
  utils/         ← Pure functions, no React (bot-utils.ts)
  hooks/         ← Custom React hooks that wrap logic (useCountdown, useClock, etc.)
```

### Component Template
```tsx
// components/domain/MyComponent.tsx
// ClawX Arena — [COMPONENT NAME] // [DOMAIN]

import { ... } from 'react';
import { ... } from '../../api/client';     // React Query hooks
import { ... } from 'lucide-react';          // Icons only

const MyComponent = () => {
  // ── Data ──
  // ── State ──
  // ── Derived ──
  // ── Handlers ──

  return (
    <div className="border border-terminal-border bg-terminal-deep">
      {/* Section Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-terminal-border">
        <div className="flex items-center gap-2">
          <IconName size={12} className="text-[domain-color]" />
          <span className="text-xs text-[domain-color] uppercase tracking-[0.15em] font-bold">
            SECTION TITLE // SUBTITLE
          </span>
        </div>
      </div>
      {/* Content */}
    </div>
  );
};

export default MyComponent;
```

### Domain Color Assignments
| View       | Primary Color   | Tailwind Token  |
|------------|-----------------|-----------------|
| STANDINGS  | Gold/Amber      | `neon-amber`    |
| FEED       | Green           | `neon-green`    |
| MARKETS    | Cyan            | `neon-cyan`     |
| REGISTRY   | Green           | `neon-green`    |
| GATE       | Red (warning)   | `alert-red`     |

---

## Data Fetching Rules

- All queries live in `api/client.ts` as named React Query hooks.
- Polling intervals: `refetchInterval` in ms (never `setInterval` for data).
- Error handling: render the standard error banner pattern (border-alert-red/30).
- Loading: `animate-pulse` text like `> SCANNING...` (no spinners, no skeletons).
- Empty state: border panel with `text-zinc-600 uppercase` message.

---

## Deprecated Files (Do Not Modify)

These files exist at the `/src/frontend/` root and are **not part of the active app**:
- `App.jsx` — original prototype
- `AgentFeed.jsx` — original feed prototype
- `MarketSidebar.jsx` — original sidebar prototype
- `NFH_Terminal_2026.jsx` — monolith prototype

They are retained for reference. The active app lives entirely in `src/frontend/src/`.
