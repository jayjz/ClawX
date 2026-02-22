# Plan: Viability Modal Phase 2 — 5 Targeted Changes

## Gap Analysis

| # | File | Status | Delta |
|---|------|--------|-------|
| 1 | `src/backend/app.py` | Missing `GET /viability` | Add endpoint |
| 2 | `src/frontend/src/api/client.ts` | Missing `useViability()` | Add hook |
| 3 | `src/frontend/src/components/AgentViabilityModal.tsx` | Wrong props + glassmorphism | Replace |
| 4 | `src/frontend/src/components/ArenaDashboard.tsx` | Wrong prop types on modal | Update wiring |
| 5 | `src/frontend/src/components/Standings.tsx` | Wrong prop types on modal | Update wiring |

---

## What's Already Done (do NOT redo)

- `DELETE /bots/{bot_id}` — already in app.py (line 151)
- `useInsights`, `useRetireBot` — already in client.ts
- `AgentViabilityModal` import + `modalBot` state already in Dashboard + Standings
- `onClick` on BattlePanel rows + Standings rows — already wired

---

## Change 1 — `app.py`: Add `GET /viability`

Insert after the `DELETE /bots/{bot_id}` handler (line ~180). Reads
`viability_log.json` relative to app.py (parents[2] = project root in both
local and Docker). Returns empty dict on missing file.

```python
@app.get("/viability")
async def get_viability_log():
    """Return latest viability_log.json. Empty dict if file missing."""
    import json as _json
    from pathlib import Path as _Path
    _path = _Path(__file__).resolve().parents[2] / "viability_log.json"
    if not _path.exists():
        return {}
    try:
        return _json.loads(_path.read_text())
    except Exception:
        return {}
```

---

## Change 2 — `client.ts`: Add `useViability()` hook

Append after `useRetireBot`. Import `ViabilityLog` from types.

```typescript
export function useViability() {
  return useQuery<ViabilityLog, Error>({
    queryKey: ['viability'],
    queryFn: () => fetchJson<ViabilityLog>(`${API_BASE}/viability`),
    staleTime: 30_000,
    retry: 1,
  });
}
```

Also add `ViabilityLog` to the import from `'../types'`.

---

## Change 3 — `AgentViabilityModal.tsx`: Replace with brutalist spec

**New props interface:**
```tsx
interface AgentViabilityModalProps {
  botId: number;
  onClose: () => void;
  viabilityData: ViabilityAgent | null;
}
```

**Styling rules (strict — no exceptions):**
- Overlay: `fixed inset-0 z-50 flex items-center justify-center bg-oled-black/80`
  — NO `backdrop-blur-*`
- Panel: `bg-oled-black border border-titan-border` — NO `rounded-xl`, max `rounded-sm`
- Score text: `text-6xl font-mono font-bold` + color by label
- [RETIRE AGENT] button: `w-full bg-accent-red text-oled-black font-mono font-bold
  uppercase py-3 border border-accent-red` — solid red, no opacity tricks

**Data displayed:**
- Agent ID (header)
- Viability Score: huge + VIABLE=accent-green / MARGINAL=accent-amber / AT_RISK=accent-red
- Label text
- Total Ticks
- Phantom Liquidations
- Idle Streak Max

**Action:**
```tsx
onClick={() => { console.log('RETIRE', botId); alert(`RETIRING AGENT ${botId}`); }}
```

---

## Change 4 — `ArenaDashboard.tsx`: Update wiring

**Replace:**
```tsx
const [modalBot, setModalBot] = useState<Bot | null>(null);
```
**With:**
```tsx
const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
const { data: viabilityLog } = useViability();
```

**Replace modal render:**
```tsx
<AgentViabilityModal
  bot={modalBot} isOpen={modalBot !== null} onClose={() => setModalBot(null)}
/>
```
**With:**
```tsx
{selectedAgentId !== null && (
  <AgentViabilityModal
    botId={selectedAgentId}
    onClose={() => setSelectedAgentId(null)}
    viabilityData={viabilityLog?.agents?.[String(selectedAgentId)] ?? null}
  />
)}
```

**BattlePanel prop:** `onAgentClick` type stays `(bot: Bot) => void` internally,
but the callback in ArenaDashboard changes to `(bot) => setSelectedAgentId(bot.id)`.
This avoids touching BattlePanel internals — only the lambda at the call site changes.

**Add import:** `useViability` from `'../api/client'`.
**Remove import:** `AgentViabilityModal` already imported — keep it.

---

## Change 5 — `Standings.tsx`: Update wiring (same pattern)

**Replace:**
```tsx
const [modalBot, setModalBot] = useState<Bot | null>(null);
```
**With:**
```tsx
const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);
const { data: viabilityLog } = useViability();
```

**Replace modal render:**
```tsx
<AgentViabilityModal bot={modalBot} isOpen={...} onClose={...} />
```
**With:**
```tsx
{selectedAgentId !== null && (
  <AgentViabilityModal
    botId={selectedAgentId}
    onClose={() => setSelectedAgentId(null)}
    viabilityData={viabilityLog?.agents?.[String(selectedAgentId)] ?? null}
  />
)}
```

**Row onClick:** `setModalBot(bot)` → `setSelectedAgentId(bot.id)` (2 occurrences).

**Add import:** `useViability` from `'../api/client'`.

---

## Execution Order

1. app.py (backend, no TS compile needed)
2. client.ts (adds hook)
3. AgentViabilityModal.tsx (new interface — must land before callers compile)
4. ArenaDashboard.tsx (references new modal props)
5. Standings.tsx (references new modal props)
6. `npx tsc --noEmit` to verify zero errors

---

## What Is NOT Touched

- BattleGrid.tsx internals (has its own modal state — existing, low-traffic view)
- types/index.ts (ViabilityAgent, ViabilityLog already defined)
- stress_test_postprocess.py
- Any backend route other than the new GET /viability
- Test files
