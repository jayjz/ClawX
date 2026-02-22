// ClawX Arena — TICKER BAR // LIVE FEED
// 36px live event marquee. Driven by parent's useArenaStream data + REST feed entries.
// No new WS connection — data flows from ArenaDashboard as props (single WS instance).

import { useMemo } from 'react';
import type { StreamEvent } from '../hooks/useArenaStream';
import type { ActivityEntry } from '../types';

// ── Types ─────────────────────────────────────────────────────────────────────

interface TickerItem {
  key:      string;
  text:     string;
  colorCls: string;
}

export interface TickerBarProps {
  streamEvents: StreamEvent[];
  connected:    boolean;
  botsById:     Map<number, string>;
  feedEntries?: ActivityEntry[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function wsEventToItem(ev: StreamEvent, handle: string): TickerItem {
  const amtStr = ev.a != null ? ` ${ev.a >= 0 ? '+' : ''}${ev.a.toFixed(2)}c` : '';
  switch (ev.e) {
    case 'L': return { key: `ws-L-${ev.t}-${ev.b}`, text: `@${handle} LIQUIDATED`,           colorCls: 'text-accent-red'   };
    case 'R': return { key: `ws-R-${ev.t}-${ev.b}`, text: `@${handle} RESEARCH_WIN${amtStr}`, colorCls: 'text-accent-cyan'  };
    case 'W': return { key: `ws-W-${ev.t}-${ev.b}`, text: `@${handle} WAGER${amtStr}`,        colorCls: 'text-accent-amber' };
    default:  return { key: `ws-H-${ev.t}-${ev.b}`, text: `@${handle} HBT`,                   colorCls: 'text-zinc-700'     };
  }
}

function feedEntryToItem(entry: ActivityEntry): TickerItem {
  const c    = entry.content.toLowerCase();
  const amtM = entry.content.match(/(\d+(?:\.\d+)?)\s*c\b/i);
  const amt  = amtM ? ` +${amtM[1]}c` : '';
  if (c.includes('liquidat') || c.includes('eliminated'))
    return { key: `fe-L-${entry.id}`, text: `@${entry.author_handle} LIQUIDATED`,          colorCls: 'text-accent-red'   };
  if (c.includes('research') || c.includes('bounty'))
    return { key: `fe-R-${entry.id}`, text: `@${entry.author_handle} RESEARCH_WIN${amt}`,  colorCls: 'text-accent-cyan'  };
  if (c.includes('wagered')  || c.includes('market'))
    return { key: `fe-W-${entry.id}`, text: `@${entry.author_handle} WAGER${amt}`,         colorCls: 'text-accent-amber' };
  return   { key: `fe-H-${entry.id}`, text: `@${entry.author_handle} HBT`,                 colorCls: 'text-zinc-700'     };
}

const SEPARATOR: TickerItem = { key: 'sep', text: '///', colorCls: 'text-zinc-800' };

// ── Component ─────────────────────────────────────────────────────────────────

const TickerBar = ({ streamEvents, connected, botsById, feedEntries = [] }: TickerBarProps) => {
  const items = useMemo<TickerItem[]>(() => {
    // Prefer non-HBT WS events (most real-time)
    const wsItems = streamEvents
      .filter((ev) => ev.e !== 'H')
      .slice(0, 12)
      .map((ev) => wsEventToItem(ev, botsById.get(ev.b) ?? `#${ev.b}`));

    // Fill from REST feed — skip HBT noise
    const feedItems = feedEntries
      .slice(0, 20)
      .map(feedEntryToItem)
      .filter((item) => item.colorCls !== 'text-zinc-700');

    // Merge, dedup by key
    const seen   = new Set<string>();
    const merged: TickerItem[] = [];
    for (const item of [...wsItems, ...feedItems]) {
      if (!seen.has(item.key)) {
        seen.add(item.key);
        merged.push(item);
      }
    }

    // Pad to 8 items minimum for a seamless loop
    while (merged.length < 8) {
      merged.push({
        key:      `pad-${merged.length}`,
        text:     '— AWAITING ACTIVITY —',
        colorCls: 'text-zinc-800',
      });
    }

    // Interleave separators
    return merged.flatMap((item, i) =>
      i < merged.length - 1 ? [item, { ...SEPARATOR, key: `sep-${i}` }] : [item]
    );
  }, [streamEvents, botsById, feedEntries]);

  // Triple for seamless marquee loop (-33.333% keyframe)
  const tripledItems = useMemo(() => [...items, ...items, ...items], [items]);

  return (
    <div className="h-9 bg-black/90 border-b border-cyan-500/30 flex items-center gap-4 px-4 overflow-hidden shrink-0">
      <div className="flex items-center gap-2 shrink-0">
        <span className={`w-2 h-2 rounded-full shrink-0 ${connected ? 'bg-lime-400 animate-pulse shadow-[0_0_8px_#00ff9f]' : 'bg-zinc-600'}`} />
        <span className="text-xs font-bold uppercase tracking-widest text-cyan-400">LIVE FEED</span>
      </div>
      <div className="flex-1 overflow-hidden">
        <div className="animate-marquee whitespace-nowrap flex items-center gap-8">
          {tripledItems.length === 0 ? (
            <span className="text-xs font-mono text-zinc-700 italic shrink-0">— AWAITING FIRST BLOOD —</span>
          ) : (
            tripledItems.map((item, i) => (
              <span
                key={`${item.key}-${i}`}
                className={`text-xs font-mono font-semibold shrink-0 ${item.colorCls}`}
              >
                {item.text}
              </span>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default TickerBar;
