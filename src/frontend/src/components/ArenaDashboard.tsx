// ClawX Arena — ARENA DASHBOARD // BENTO LAYOUT
// 2026 Premium Pivot: flat OLED black, 1px titanium borders, accent palette.
// Left: BattlePanel (Order Book table). Center: stat bento + topology + markets. Right: ledger stream.
// Polish v2: StatCard flash · AgentTopology tooltips + kb-nav · LedgerStream intensity + auto-scroll
// v5 Bloat Purge: stripped glassmorphism, spatial drift, particle sparks, explosion rings, graveyard row
// v6 Institutional Grid: BattlePanel → flat monospace table (rank/handle/balance/ticks/status)
// v7 HF Pipeline: useArenaStream wired — WS deltas → cache invalidation + live EVT column + live pulse ledger

import { useState, useEffect, useMemo, useCallback, useRef, memo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useBots, useMarkets, useActivityFeed } from '../api/client';
import { useArenaStream, type StreamEvent } from '../hooks';
import { Users, DollarSign, Search, Skull, Clock, ArrowRight } from 'lucide-react';
import { formatCountdown } from '../utils/bot-utils';
import CommandPalette, { type CommandId } from './CommandPalette';
import AgentViabilityModal from './AgentViabilityModal';
import TickerBar from './TickerBar';
import type { Bot, ActivityEntry, Market } from '../types';

// ── Types ──────────────────────────────────────────────────────────────────────

type StatVariant = 'green' | 'amber' | 'cyan' | 'red';

const STAT_CONFIG: Record<StatVariant, {
  icon: string;
  value: string;
  border: string;
  shadow: string;
  shadowFlash: string;
}> = {
  green: {
    icon:        'bg-accent-green/10 text-accent-green rounded-lg',
    value:       'text-accent-green',
    border:      'border-accent-green/20',
    shadow:      '0 0 32px rgba(0,255,159,0.06)',
    shadowFlash: '0 0 56px rgba(0,255,159,0.28), 0 0 16px rgba(0,255,159,0.16)',
  },
  amber: {
    icon:        'bg-accent-amber/10 text-accent-amber rounded-lg',
    value:       'text-accent-amber',
    border:      'border-accent-amber/20',
    shadow:      '0 0 32px rgba(255,149,0,0.06)',
    shadowFlash: '0 0 56px rgba(255,149,0,0.28), 0 0 16px rgba(255,149,0,0.16)',
  },
  cyan: {
    icon:        'bg-accent-cyan/10 text-accent-cyan rounded-lg',
    value:       'text-accent-cyan',
    border:      'border-accent-cyan/20',
    shadow:      '0 0 32px rgba(0,240,255,0.06)',
    shadowFlash: '0 0 56px rgba(0,240,255,0.28), 0 0 16px rgba(0,240,255,0.16)',
  },
  red: {
    icon:        'bg-accent-red/10 text-accent-red rounded-lg',
    value:       'text-accent-red',
    border:      'border-accent-red/20',
    shadow:      '0 0 32px rgba(255,59,48,0.06)',
    shadowFlash: '0 0 56px rgba(255,59,48,0.28), 0 0 16px rgba(255,59,48,0.16)',
  },
};

const SOURCE_BADGE: Record<string, string> = {
  RESEARCH: 'border-accent-cyan/40 text-accent-cyan bg-accent-cyan/5',
  GITHUB:   'border-accent-green/30 text-accent-green bg-accent-green/5',
  NEWS:     'border-accent-amber/30 text-accent-amber bg-accent-amber/5',
  WEATHER:  'border-zinc-600/30 text-zinc-400 bg-zinc-700/5',
};

// ── Helpers ────────────────────────────────────────────────────────────────────

/** Survival ticks since bot creation (10s per tick) */
function survivalTicks(createdAt: string, now: number): number {
  return Math.max(0, Math.floor((now - new Date(createdAt).getTime()) / 10_000));
}

// ── Top Bar ────────────────────────────────────────────────────────────────────

const TopBar = ({ aliveCount, deadCount, marketCount, onCommandOpen, wsConnected }: {
  aliveCount: number;
  deadCount: number;
  marketCount: number;
  onCommandOpen: () => void;
  wsConnected: boolean;
}) => (
  <div className="flex items-center justify-between px-5 h-12 rounded-xl border border-white/10 bg-black/70 backdrop-blur-xl shrink-0" style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)' }}>
    <div className="flex items-center gap-5">
      <span className="text-sm font-sans font-bold text-white tracking-tight">CLAWX ARENA</span>
      <span className="text-[10px] font-sans text-zinc-500 uppercase tracking-widest hidden lg:block">
        ENTROPY 0.50c/TICK · SHA256 LEDGER · DECIMAL PURITY
      </span>
    </div>

    <div className="flex items-center gap-5">
      <div className="flex items-center gap-4 text-[10px] font-sans uppercase tracking-widest">
        <span className="flex items-center gap-1.5 text-accent-green">
          <span className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse" />
          {aliveCount} ALIVE
        </span>
        <span className="flex items-center gap-1.5 text-accent-red/70">
          <span className="w-1.5 h-1.5 rounded-full bg-accent-red/60" />
          {deadCount} DEAD
        </span>
        <span className="flex items-center gap-1.5 text-accent-cyan">
          <span className="w-1.5 h-1.5 rounded-full bg-accent-cyan" />
          {marketCount} MARKETS
        </span>
        <span className={`flex items-center gap-1.5 ${wsConnected ? 'text-accent-green' : 'text-zinc-600'}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${wsConnected ? 'bg-accent-green animate-pulse' : 'bg-zinc-700'}`} />
          WS
        </span>
      </div>

      <button
        onClick={onCommandOpen}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-zinc-700 bg-oled-black hover:border-accent-green/50 hover:bg-titan-grey transition-all"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-accent-green/70 animate-pulse shrink-0" />
        <kbd className="text-xs font-mono text-accent-green font-bold leading-none">⌘K</kbd>
        <span className="text-[9px] font-sans text-zinc-400 uppercase tracking-widest leading-none">CMD</span>
      </button>
    </div>
  </div>
);

// ── Battle Panel — Order Book flat table (v6) ─────────────────────────────────
// High-density monospace grid. No icons, no SVG, no CSS animations.
// Alive: accent-green bold. Dead: accent-red at 30% opacity.
// Columns: # | Handle | Balance | Ticks | Status | EVT (live WS event code)

const EVT_COLOR: Record<string, string> = {
  W: 'text-accent-amber',
  L: 'text-accent-red',
  R: 'text-accent-cyan',
  H: 'text-zinc-700',
};

// Live-pulse label: maps stream event code → short badge for LedgerStream
const EV_BADGE: Record<StreamEvent['e'], { label: string; color: string }> = {
  W: { label: 'BET', color: 'text-accent-amber' },
  L: { label: 'DIE', color: 'text-accent-red'   },
  R: { label: 'RSC', color: 'text-accent-cyan'   },
  H: { label: 'HBT', color: 'text-zinc-700'      },
};

const BattlePanel = memo(({
  bots,
  now,
  liveEventByBotId,
  onAgentClick,
}: {
  bots: Bot[];
  now: number;
  liveEventByBotId: Record<number, StreamEvent['e']>;
  onAgentClick: (bot: Bot) => void;
}) => {
  const sorted = useMemo(() => {
    const alive = [...bots]
      .filter((b) => b.status === 'ALIVE')
      .sort((a, b) => Number(b.balance) - Number(a.balance));
    const dead = [...bots]
      .filter((b) => b.status === 'DEAD')
      .sort((a, b) => b.id - a.id);
    return [...alive, ...dead];
  }, [bots]);

  const aliveCount = useMemo(() => bots.filter((b) => b.status === 'ALIVE').length, [bots]);

  return (
    <div className="flex flex-col h-full">

      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-titan-border shrink-0">
        <span className="w-1.5 h-1.5 rounded-full bg-accent-green" />
        <span className="text-[10px] font-mono font-bold text-accent-green uppercase tracking-widest">
          ORDER BOOK
        </span>
        <span className="ml-auto text-[10px] font-mono text-zinc-600 tabular-nums">
          {aliveCount} ALIVE
        </span>
      </div>

      {/* Column headers */}
      <div className="flex items-center px-3 py-1 border-b border-titan-border/50 shrink-0">
        <span className="w-6 text-[9px] font-mono text-zinc-700 shrink-0">#</span>
        <span className="flex-1 text-[9px] font-mono text-zinc-700 uppercase tracking-widest min-w-0">HANDLE</span>
        <span className="w-[66px] text-[9px] font-mono text-zinc-700 text-right uppercase tracking-widest">BAL</span>
        <span className="w-[48px] text-[9px] font-mono text-zinc-700 text-right uppercase tracking-widest">TICKS</span>
        <span className="w-[46px] text-[9px] font-mono text-zinc-700 text-right uppercase tracking-widest">ST</span>
        <span className="w-[28px] text-[9px] font-mono text-zinc-700 text-right uppercase tracking-widest">EVT</span>
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {sorted.length === 0 ? (
          <div className="h-full flex items-center justify-center text-[9px] font-mono text-zinc-700 uppercase tracking-widest">
            NO AGENTS
          </div>
        ) : (
          sorted.map((bot, i) => {
            const isAlive   = bot.status === 'ALIVE';
            const balance   = Number(bot.balance);
            const ticks     = survivalTicks(bot.created_at, now);
            const accentCls = isAlive ? 'text-accent-green' : 'text-accent-red';

            return (
              <div
                key={bot.id}
                className={`flex items-center px-3 py-[4px] border-b border-titan-border/25 hover:bg-titan-border/20 transition-colors cursor-pointer ${
                  isAlive ? '' : 'opacity-30'
                }`}
                onClick={() => onAgentClick(bot)}
              >
                {/* Rank */}
                <span className="w-6 text-[10px] font-mono text-zinc-600 tabular-nums shrink-0">
                  {i + 1}
                </span>

                {/* Handle */}
                <span className={`flex-1 text-[10px] font-mono font-bold truncate min-w-0 ${accentCls}`}>
                  {bot.handle}
                </span>

                {/* Balance */}
                <span className={`w-[66px] text-[10px] font-mono tabular-nums text-right ${accentCls}`}>
                  {balance.toFixed(2)}c
                </span>

                {/* Survival ticks */}
                <span className="w-[48px] text-[10px] font-mono text-zinc-500 tabular-nums text-right">
                  {ticks > 0 ? ticks.toLocaleString() : '—'}
                </span>

                {/* Status */}
                <span className={`w-[46px] text-[10px] font-mono font-bold text-right ${accentCls}`}>
                  {isAlive ? '● LIV' : '● DED'}
                </span>

                {/* Live WS event code */}
                {(() => {
                  const evtCode = liveEventByBotId[bot.id];
                  return (
                    <span className={`w-[28px] text-[10px] font-mono font-bold text-right shrink-0 ${EVT_COLOR[evtCode ?? ''] ?? 'text-zinc-800'}`}>
                      {evtCode ?? '·'}
                    </span>
                  );
                })()}
              </div>
            );
          })
        )}
      </div>

    </div>
  );
});

// ── Agent Topology — labeled center-panel node graph + tooltips + kb-nav ──────

const AG_VW      = 680;
const AG_CELL_H  = 90;
const AG_PAD_TOP = 44;
const AG_PAD_BOT = 28;

const AgentTopology = ({
  bots,
  recentActivity,
  recentBotIds,
  latestEvent,
  onAgentClick,
}: {
  bots: Bot[];
  recentActivity: Map<number, string>;
  recentBotIds: Set<number>;
  latestEvent: StreamEvent | null;
  onAgentClick?: (bot: Bot) => void;
}) => {
  const all = useMemo(() =>
    [...bots]
      .sort((a, b) => {
        if (a.status !== b.status) return a.status === 'ALIVE' ? -1 : 1;
        return Number(b.balance) - Number(a.balance);
      })
      .slice(0, 42),
  [bots]);

  const N    = all.length;
  const cols = Math.min(Math.max(N, 1), 6);
  const rows = Math.ceil(N / cols);
  const VH   = AG_PAD_TOP + rows * AG_CELL_H + AG_PAD_BOT;

  const maxBalance = useMemo(
    () => Math.max(...all.map((b) => Number(b.balance)), 1),
    [all],
  );

  const nodes = useMemo(() => {
    const cellW = AG_VW / cols;
    return all.map((bot, i) => ({
      bot,
      x: +(cellW * (i % cols) + cellW / 2).toFixed(1),
      y: +(AG_PAD_TOP + AG_CELL_H * Math.floor(i / cols) + 38).toFixed(1),
    }));
  }, [all, cols]);

  const edges = useMemo(() => {
    const links: [number, number][] = [];
    for (let i = 0; i < N; i++) {
      if (i + 1 < N && Math.floor((i + 1) / cols) === Math.floor(i / cols))
        links.push([i, i + 1]);
      if (i + cols < N) links.push([i, i + cols]);
    }
    return links;
  }, [N, cols]);

  const alive = bots.filter((b) => b.status === 'ALIVE');
  const dead  = bots.filter((b) => b.status === 'DEAD');

  const [hoveredBot, setHoveredBot] = useState<Bot | null>(null);
  const [mousePos,   setMousePos]   = useState({ x: 0, y: 0 });
  const wrapperRef = useRef<HTMLDivElement>(null);

  // ── WS flash: amber=WAGER  red=LIQUIDATION  700ms burst per bot ─────────────
  const [flashMap,    setFlashMap]   = useState<Partial<Record<number, StreamEvent['e']>>>({});
  const flashTimers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  useEffect(() => {
    if (!latestEvent || (latestEvent.e !== 'W' && latestEvent.e !== 'L')) return;
    const { b: botId, e: evtCode } = latestEvent;
    const prevTimer = flashTimers.current.get(botId);
    if (prevTimer !== undefined) clearTimeout(prevTimer);
    setFlashMap(m => ({ ...m, [botId]: evtCode }));
    flashTimers.current.set(botId, setTimeout(() => {
      setFlashMap(m => { const n = { ...m }; delete n[botId]; return n; });
      flashTimers.current.delete(botId);
    }, 700));
  }, [latestEvent]);

  useEffect(() => {
    const timers = flashTimers.current;
    return () => { timers.forEach(clearTimeout); };
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const rect = wrapperRef.current?.getBoundingClientRect();
    if (!rect) return;
    setMousePos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  }, []);

  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLDivElement>) => {
    if (N === 0) return;
    const cur = selectedIdx ?? 0;
    switch (e.key) {
      case 'ArrowRight':
        e.preventDefault();
        setSelectedIdx(Math.min(cur + 1, N - 1));
        break;
      case 'ArrowLeft':
        e.preventDefault();
        setSelectedIdx(Math.max(cur - 1, 0));
        break;
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIdx(Math.min(cur + cols, N - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIdx(Math.max(cur - cols, 0));
        break;
      case 'Escape':
        e.preventDefault();
        setSelectedIdx(null);
        break;
      case 'Enter':
        e.preventDefault();
        if (selectedIdx !== null && nodes[selectedIdx]) {
          onAgentClick?.(nodes[selectedIdx].bot);
        }
        break;
    }
  }, [N, cols, selectedIdx, nodes]);

  if (N === 0) {
    return (
      <div className="rounded-xl border border-titan-border bg-titan-grey p-10 text-center text-[10px] font-sans text-zinc-700 uppercase tracking-widest shrink-0">
        NO AGENTS DEPLOYED
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-white/10 bg-black/70 backdrop-blur-xl overflow-hidden shrink-0 outline-none focus-within:border-zinc-600 transition-colors" style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)' }}>

      <div className="flex items-center justify-between px-4 py-2.5 border-b border-titan-border">
        <div className="flex items-center gap-3">
          <span className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse" />
          <span className="text-[10px] font-sans font-semibold text-accent-green uppercase tracking-widest">
            AGENTS
          </span>
          <span className="text-[10px] font-sans text-zinc-600 uppercase tracking-widest">
            {alive.length} ALIVE · {dead.length} DEAD
          </span>
        </div>
        <span className="text-[9px] font-mono text-zinc-600 tabular-nums">
          {selectedIdx !== null
            ? `[${nodes[selectedIdx]?.bot.handle ?? '?'}]`
            : `${N} NODES · ↑↓←→`
          }
        </span>
      </div>

      <div
        ref={wrapperRef}
        className="relative"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoveredBot(null)}
        onKeyDown={handleKeyDown}
        tabIndex={0}
        role="grid"
        aria-label="Agent topology graph"
      >
        <svg
          viewBox={`0 0 ${AG_VW} ${VH}`}
          width="100%"
          height={VH}
          xmlns="http://www.w3.org/2000/svg"
          style={{ display: 'block' }}
          preserveAspectRatio="xMidYMid meet"
        >
          {Array.from({ length: Math.ceil(VH / 50) + 1 }, (_, r) =>
            Array.from({ length: Math.ceil(AG_VW / 50) + 1 }, (_, c) => (
              <circle key={`d-${r}-${c}`} cx={c * 50} cy={r * 50} r={0.8} fill="#2A2A2A" />
            ))
          )}

          {edges.map(([a, b], i) => {
            const aRecent = nodes[a]?.bot && recentBotIds.has(nodes[a].bot.id);
            const bRecent = nodes[b]?.bot && recentBotIds.has(nodes[b].bot.id);
            return (
              <line
                key={`e-${i}`}
                x1={nodes[a]?.x ?? 0} y1={nodes[a]?.y ?? 0}
                x2={nodes[b]?.x ?? 0} y2={nodes[b]?.y ?? 0}
                stroke={aRecent && bRecent ? '#00FF9F' : '#2A2A2A'}
                strokeWidth={aRecent && bRecent ? 0.6 : 0.8}
                opacity={aRecent && bRecent ? 0.25 : 1}
                strokeDasharray={
                  nodes[a]?.bot.status === 'DEAD' || nodes[b]?.bot.status === 'DEAD'
                    ? '2,3' : undefined
                }
              />
            );
          })}

          {nodes.map(({ bot, x, y }, idx) => {
            const isAlive   = bot.status === 'ALIVE';
            const isRecent  = isAlive && recentBotIds.has(bot.id);
            const isKbSel   = selectedIdx === idx;
            const balance   = Number(bot.balance);
            const r         = Math.max(6, Math.min(14, 6 + (balance / maxBalance) * 8));
            const color      = isAlive ? '#00FF9F' : '#FF3B30';
            const opacity    = isAlive ? 1 : 0.28;
            const pulseDur   = `${2.2 + (bot.id % 6) * 0.28}s`;
            const label      = bot.handle.length > 10 ? bot.handle.slice(0, 9) + '…' : bot.handle;
            const flashEvt   = flashMap[bot.id];
            const flashColor = flashEvt === 'L' ? '#FF3B30' : flashEvt === 'W' ? '#FF9500' : undefined;

            return (
              <g
                key={bot.id}
                style={{ cursor: 'pointer' }}
                onMouseEnter={() => setHoveredBot(bot)}
                onMouseLeave={() => setHoveredBot(null)}
                onClick={() => { setSelectedIdx(idx); onAgentClick?.(bot); }}
              >
                {isRecent && (
                  <circle cx={x} cy={y} r={r + 5} fill="none" stroke="#00FF9F" strokeWidth={1.2} opacity={0.3} />
                )}
                {isKbSel && (
                  <circle cx={x} cy={y} r={r + 8} fill="none"
                    stroke={isAlive ? '#00FF9F' : '#FF3B30'} strokeWidth={1.5} opacity={0.6} strokeDasharray="3,2" />
                )}
                {isAlive && (
                  <circle cx={x} cy={y} r={r} fill="none" stroke="#00FF9F" strokeWidth={1} opacity={0.15}>
                    <animate attributeName="r" values={`${r};${r + 10};${r}`} dur={pulseDur} repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.2;0.02;0.2" dur={pulseDur} repeatCount="indefinite" />
                  </circle>
                )}
                <circle cx={x} cy={y} r={r} fill={color} opacity={opacity}>
                  {isAlive && (
                    <animate attributeName="opacity" values="1;0.68;1"
                      dur={`${3 + (bot.id % 4) * 0.4}s`} repeatCount="indefinite" />
                  )}
                </circle>
                {/* WS flash overlay: amber=WAGER  red=LIQUIDATION */}
                {flashColor && (
                  <>
                    <circle cx={x} cy={y} r={r + 7} fill="none"
                      stroke={flashColor} strokeWidth="1.5" opacity="0.8" />
                    <circle cx={x} cy={y} r={r} fill={flashColor} opacity="0.45" />
                  </>
                )}
                <text x={x} y={y + r + 13} textAnchor="middle" fill={isKbSel ? (isAlive ? '#00FF9F' : '#FF3B30') : color}
                  fontSize={9} fontFamily='"JetBrains Mono","Courier New",monospace'
                  opacity={isAlive ? (isKbSel ? 1 : 0.85) : 0.32} letterSpacing="0.4">
                  {label}
                </text>
                <text x={x} y={y + r + 23} textAnchor="middle" fill={color}
                  fontSize={8} fontFamily='"JetBrains Mono","Courier New",monospace'
                  opacity={isAlive ? 0.38 : 0.14}>
                  {isAlive ? `${balance.toFixed(0)}c` : 'DEAD'}
                </text>
              </g>
            );
          })}
        </svg>

        {hoveredBot && (
          <div className="absolute z-10 pointer-events-none" style={{ left: mousePos.x + 14, top: mousePos.y - 8 }}>
            <div className="rounded-lg border border-titan-border bg-oled-black px-3 py-2.5 min-w-[160px]"
              style={{ boxShadow: '0 8px 32px rgba(0,0,0,0.8)' }}>
              <div className="flex items-center gap-2 mb-1.5">
                <span className="w-1.5 h-1.5 rounded-full shrink-0"
                  style={{ background: hoveredBot.status === 'ALIVE' ? '#00FF9F' : '#FF3B30' }} />
                <span className="text-xs font-sans font-semibold text-white truncate max-w-[120px]">
                  {hoveredBot.handle}
                </span>
              </div>
              <div className="flex flex-col gap-0.5">
                <div className="flex items-center justify-between gap-4">
                  <span className="text-[9px] font-sans text-zinc-600 uppercase tracking-wider">Balance</span>
                  <span className={`text-[10px] font-mono font-bold tabular-nums ${
                    hoveredBot.status === 'ALIVE' ? 'text-accent-green' : 'text-accent-red/60'
                  }`}>
                    {hoveredBot.status === 'ALIVE'
                      ? `${Number(hoveredBot.balance).toFixed(2)}c`
                      : 'LIQUIDATED'
                    }
                  </span>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <span className="text-[9px] font-sans text-zinc-600 uppercase tracking-wider">Status</span>
                  <span className={`text-[9px] font-mono font-semibold ${
                    hoveredBot.status === 'ALIVE' ? 'text-accent-green' : 'text-accent-red/50'
                  }`}>
                    {hoveredBot.status}
                  </span>
                </div>
                {recentActivity.has(hoveredBot.id) && (
                  <div className="mt-1.5 pt-1.5 border-t border-titan-border">
                    <span className="text-[8px] font-sans text-zinc-600 uppercase tracking-wider block mb-0.5">
                      Last Action
                    </span>
                    <p className="text-[9px] font-sans text-zinc-400 leading-snug line-clamp-2">
                      {recentActivity.get(hoveredBot.id)}
                    </p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ── Ledger Stream — maximum density, institutional brutalism (v6) ─────────────
// Columns (single line, 9px mono): TIME | HANDLE | BADGE | CONTENT | AMOUNT
// Filter input row. All entries shown (no cap). Auto-scroll to newest on arrival.
// Intensity opacity kept: HBT fades to 28%, DIE/PAY burn at full opacity.

function deriveBadge(content: string): { label: string; color: string } {
  const c = content.toLowerCase();
  if (c.includes('liquidat') || c.includes('eliminated')) return { label: 'DIE', color: 'text-accent-red' };
  if (c.includes('payout')   || c.includes('reward'))     return { label: 'PAY', color: 'text-accent-green' };
  if (c.includes('research') || c.includes('bounty'))     return { label: 'RSC', color: 'text-accent-cyan' };
  if (c.includes('wagered')  || c.includes('market'))     return { label: 'BET', color: 'text-accent-amber' };
  return { label: 'HBT', color: 'text-zinc-600' };
}

function extractAmount(content: string): number {
  const m = content.match(/(\d+(?:\.\d+)?)\s*c\b/i);
  return m ? parseFloat(m[1] ?? '0') : 0;
}

function entryIntensity(label: string, amount: number, maxAmount: number): number {
  const max = maxAmount || 1;
  switch (label) {
    case 'DIE': return 1.0;
    case 'PAY': return 0.90;
    case 'RSC': return Math.max(0.68, 0.68 + (amount / max) * 0.32);
    case 'BET': return Math.max(0.52, 0.52 + (amount / max) * 0.38);
    default:    return 0.28;
  }
}

const LedgerStream = memo(({ entries, streamEvents, botsById }: {
  entries: ActivityEntry[];
  streamEvents: StreamEvent[];
  botsById: Map<number, string>;
}) => {
  const scrollRef             = useRef<HTMLDivElement>(null);
  const topId                 = entries[0]?.id ?? null;
  const [newEntryId,  setNew] = useState<number | null>(null);
  const [filter,   setFilter] = useState('');

  // Auto-scroll to top (newest) when a new entry arrives
  useEffect(() => {
    if (topId == null) return;
    setNew(topId);
    if (!filter) scrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
    const t = setTimeout(() => setNew(null), 1200);
    return () => clearTimeout(t);
  }, [topId, filter]);

  // Filter by handle or content (case-insensitive)
  const visible = useMemo(() => {
    if (!filter.trim()) return entries;
    const q = filter.toLowerCase();
    return entries.filter(
      (e) => e.author_handle.toLowerCase().includes(q) || e.content.toLowerCase().includes(q),
    );
  }, [entries, filter]);

  const maxAmount = useMemo(() => {
    let max = 0;
    for (const e of visible) {
      const badge = deriveBadge(e.content);
      if (badge.label !== 'HBT') {
        const amt = extractAmount(e.content);
        if (amt > max) max = amt;
      }
    }
    return max;
  }, [visible]);

  // WS live-pulse: last 8 non-HEARTBEAT stream events (rendered above REST rows)
  const livePulse = useMemo(
    () => streamEvents.filter((ev) => ev.e !== 'H').slice(0, 8),
    [streamEvents],
  );

  return (
    <div className="flex flex-col h-full overflow-hidden">

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 px-2 py-1.5 border-b border-titan-border shrink-0">
        <span className="text-[10px] font-mono font-bold text-accent-cyan uppercase tracking-widest">
          LEDGER
        </span>
        <span className="ml-auto text-[10px] font-mono text-zinc-600 tabular-nums">
          {visible.length}/{entries.length}
        </span>
      </div>

      {/* ── Filter input ────────────────────────────────────────────────────── */}
      <div className="shrink-0 border-b border-titan-border">
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="FILTER HANDLE / CONTENT..."
          className="w-full bg-transparent px-2 py-1 text-[10px] font-mono text-zinc-400 placeholder:text-zinc-700 outline-none border-0"
          style={{ fontFamily: '"JetBrains Mono","Courier New",monospace' }}
          spellCheck={false}
        />
      </div>

      {/* ── Column headers ──────────────────────────────────────────────────── */}
      <div
        className="flex items-center gap-0 px-2 py-[2px] border-b border-titan-border/60 shrink-0"
        style={{ fontFamily: '"JetBrains Mono","Courier New",monospace', fontSize: '9px' }}
      >
        <span className="w-[54px] text-zinc-700 shrink-0">TIME</span>
        <span className="w-[58px] text-zinc-700 shrink-0">HANDLE</span>
        <span className="w-[30px] text-zinc-700 shrink-0">TYPE</span>
        <span className="flex-1 text-zinc-700 min-w-0">CONTENT</span>
        <span className="w-[42px] text-zinc-700 text-right shrink-0">AMT</span>
      </div>

      {/* ── WS Live Pulse (non-HBT stream events, newest first) ─────────────── */}
      {livePulse.length > 0 && (
        <div className="shrink-0 border-b border-[#1f1f1f]">
          {livePulse.map((ev, i) => {
            const badge   = EV_BADGE[ev.e];
            const handle  = botsById.get(ev.b) ?? `#${ev.b}`;
            const t       = new Date(ev.t * 1000).toLocaleTimeString('en', {
              hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit',
            });
            return (
              <div
                key={`ws-${ev.t}-${ev.b}-${i}`}
                className="flex items-center gap-0 px-2 border-b border-[#181818] bg-[#0e1a14]/60"
                style={{
                  height:     '20px',
                  fontFamily: '"JetBrains Mono","Courier New",monospace',
                  fontSize:   '10px',
                  lineHeight: '20px',
                  opacity:    i === 0 ? 1 : Math.max(0.35, 1 - i * 0.1),
                }}
              >
                <span className="w-[54px] text-zinc-600 tabular-nums shrink-0 truncate">{t}</span>
                <span className="w-[58px] text-accent-green/60 truncate shrink-0">{handle}</span>
                <span className={`w-[30px] font-bold shrink-0 ${badge.color}`}>{badge.label}</span>
                <span className="flex-1 text-zinc-700 truncate min-w-0 italic">
                  {ev.e === 'L' ? 'liquidated'
                    : ev.e === 'W' ? 'wager placed'
                    : ev.e === 'R' ? 'research/portfolio'
                    : 'heartbeat'}
                </span>
                <span className="w-[42px] text-zinc-600 tabular-nums text-right shrink-0">
                  {ev.a != null ? `${ev.a.toFixed(2)}c` : '—'}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* ── Rows ────────────────────────────────────────────────────────────── */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto min-h-0">
        {visible.length === 0 ? (
          <div className="px-2 py-4 text-center text-[9px] font-mono text-zinc-700 uppercase tracking-widest">
            {filter ? 'NO MATCH' : 'AWAITING ENTRIES...'}
          </div>
        ) : (
          visible.map((entry) => {
            const badge     = deriveBadge(entry.content);
            const amount    = extractAmount(entry.content);
            const intensity = entryIntensity(badge.label, amount, maxAmount);
            const isNew     = entry.id === newEntryId;
            const t         = new Date(entry.created_at).toLocaleTimeString('en', {
              hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit',
            });

            return (
              <div
                key={entry.id}
                className="flex items-center gap-0 px-2 border-b border-[#1f1f1f] hover:bg-[#131313]"
                style={{
                  opacity:    intensity,
                  background: isNew ? 'rgba(0,240,255,0.035)' : undefined,
                  transition: 'background 900ms ease',
                  height:     '20px',
                  fontFamily: '"JetBrains Mono","Courier New",monospace',
                  fontSize:   '10px',
                  lineHeight: '20px',
                }}
              >
                {/* TIME */}
                <span className="w-[54px] text-zinc-600 tabular-nums shrink-0 truncate">
                  {t}
                </span>

                {/* HANDLE */}
                <span className="w-[58px] text-accent-green/80 truncate shrink-0">
                  {entry.author_handle}
                </span>

                {/* BADGE */}
                <span className={`w-[30px] font-bold shrink-0 ${badge.color}`}>
                  {badge.label}
                </span>

                {/* CONTENT */}
                <span className="flex-1 text-zinc-500 truncate min-w-0">
                  {entry.content}
                </span>

                {/* AMOUNT */}
                <span className="w-[42px] text-zinc-600 tabular-nums text-right shrink-0">
                  {amount > 0 ? `${amount.toFixed(2)}c` : '—'}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
});

// ── Stat Card — with value-change flash ───────────────────────────────────────

const StatCard = ({ icon: Icon, label, value, variant, sub }: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  variant: StatVariant;
  sub?: string;
}) => {
  const cfg       = STAT_CONFIG[variant];
  const prevValue = useRef(value);
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    if (String(prevValue.current) !== String(value)) {
      prevValue.current = value;
      setFlash(true);
      const t = setTimeout(() => setFlash(false), 500);
      return () => clearTimeout(t);
    }
  }, [value]);

  return (
    <div
      className={`rounded-xl border bg-black/60 backdrop-blur-xl p-4 flex items-center gap-3.5 ${cfg.border}`}
      style={{
        boxShadow:  flash ? cfg.shadowFlash : cfg.shadow,
        transform:  flash ? 'scale(1.015)' : 'scale(1)',
        transition: 'box-shadow 300ms ease, transform 300ms ease',
      }}
    >
      <div className={`w-10 h-10 flex items-center justify-center shrink-0 ${cfg.icon}`}>
        <Icon size={17} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-[10px] font-sans text-zinc-500 uppercase tracking-widest mb-1">{label}</div>
        <div className={`text-2xl font-sans font-bold tabular-nums leading-none ${cfg.value}`}>{value}</div>
        {sub && <div className="text-[9px] font-sans text-zinc-600 mt-1 uppercase tracking-wide">{sub}</div>}
      </div>
    </div>
  );
};

// ── Market Snapshot Card ──────────────────────────────────────────────────────

const MarketSnapshotCard = ({ market, now }: { market: Market; now: number }) => {
  const deadlineMs  = new Date(market.deadline).getTime();
  const secondsLeft = Math.max(0, (deadlineMs - now) / 1000);
  const isExpired   = secondsLeft <= 0;
  const isUrgent    = secondsLeft > 0 && secondsLeft < 60;
  const isWarning   = secondsLeft > 0 && secondsLeft < 180;
  const isResearch  = market.source_type === 'RESEARCH';

  const badgeColor     = SOURCE_BADGE[market.source_type] ?? 'border-zinc-600/30 text-zinc-400 bg-zinc-700/5';
  const countdownColor = isExpired  ? 'text-zinc-600'
    : isUrgent  ? 'text-accent-red'
    : isWarning ? 'text-accent-amber'
    : 'text-zinc-500';

  return (
    <div
      className={`rounded-xl border bg-black/70 backdrop-blur-xl p-4 flex flex-col transition-all ${
        isExpired
          ? 'opacity-40 border-titan-border'
          : isResearch
            ? 'border-accent-cyan/30'
            : 'border-titan-border hover:border-zinc-700'
      }`}
      style={isResearch && !isExpired ? { boxShadow: '0 0 24px rgba(0,240,255,0.08)' } : undefined}
    >
      <div className="flex items-center justify-between mb-2.5">
        <span className={`text-[8px] px-2 py-0.5 rounded-full border font-sans font-semibold uppercase tracking-widest ${badgeColor}`}>
          {market.source_type}
        </span>
        <span className={`font-mono font-bold text-base ${isResearch ? 'text-accent-cyan' : 'text-accent-green'}`}>
          {Number(market.bounty).toFixed(0)}c
        </span>
      </div>

      <p className="text-xs font-sans text-zinc-400 mb-3 leading-relaxed line-clamp-2 flex-1">
        {market.description}
      </p>

      <div className="space-y-1.5">
        <div className="flex items-center justify-between">
          <span className={`text-[9px] font-mono flex items-center gap-1 ${countdownColor}`}>
            <Clock size={9} className={isUrgent ? 'animate-pulse' : ''} />
            {isExpired ? 'EXPIRED' : formatCountdown(secondsLeft)}
          </span>
          {!isExpired && (
            <span className={`text-[9px] font-mono tabular-nums font-bold ${countdownColor}`}>
              {Math.ceil(secondsLeft)}s
            </span>
          )}
        </div>
        {!isExpired && (
          <div className="w-full h-1 rounded-full bg-oled-black overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-1000 ${
                isUrgent ? 'bg-accent-red' : isWarning ? 'bg-accent-amber' : 'bg-accent-cyan'
              }`}
              style={{ width: `${Math.min((secondsLeft / 300) * 100, 100)}%` }}
            />
          </div>
        )}
        {!isExpired && (
          <button
            onClick={() => console.log('BET', market.id, market.description)}
            className={`w-full mt-1 py-1.5 rounded-lg text-[9px] font-sans font-semibold uppercase tracking-widest border transition-colors ${
              isResearch
                ? 'border-accent-cyan/30 text-accent-cyan hover:bg-accent-cyan/10'
                : 'border-accent-green/30 text-accent-green hover:bg-accent-green/10'
            }`}
          >
            Place Bet
          </button>
        )}
      </div>
    </div>
  );
};

// ── Main Dashboard ────────────────────────────────────────────────────────────

const ArenaDashboard = () => {
  const queryClient = useQueryClient();
  const { data: bots,    refetch: refetchBots    } = useBots();
  const { data: markets, refetch: refetchMarkets } = useMarkets();
  const { data: feed,    refetch: refetchFeed    } = useActivityFeed();
  const { events: streamEvents, lastEvent, connected: wsConnected } = useArenaStream();
  const [now, setNow]               = useState(Date.now());
  const [isCommandOpen, setCommand] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState<number | null>(null);

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const toggleCommand = useCallback(() => setCommand((v) => !v), []);
  const closeCommand  = useCallback(() => setCommand(false), []);

  const handleCommandAction = useCallback((id: CommandId) => {
    if (id === 'system:refresh') {
      void refetchBots();
      void refetchMarkets();
      void refetchFeed();
    }
  }, [refetchBots, refetchMarkets, refetchFeed]);

  const allBots      = bots ?? [];
  const alive        = allBots.filter((b) => b.status === 'ALIVE');
  const dead         = allBots.filter((b) => b.status === 'DEAD');
  const totalEconomy = allBots.reduce((sum, b) => sum + b.balance, 0);
  const openMarkets  = markets ?? [];
  const feedEntries  = feed ?? [];

  // ── WS-derived: latest event code per bot_id (for BattlePanel EVT column) ──
  const liveEventByBotId = useMemo(() => {
    const map: Record<number, StreamEvent['e']> = {};
    for (const ev of streamEvents) {
      if (!(ev.b in map)) map[ev.b] = ev.e; // first occurrence = most recent (newest-first)
    }
    return map;
  }, [streamEvents]);

  // ── WS-derived: bot id → handle map (for LedgerStream live rows) ────────────
  const botsById = useMemo(() => {
    const map = new Map<number, string>();
    for (const b of allBots) map.set(b.id, b.handle);
    return map;
  }, [allBots]);

  // ── Cache invalidation: WS events trigger immediate REST refetches ───────────
  useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.e === 'L') {
      // LIQUIDATION → bots list needs immediate update (DEAD status)
      void queryClient.invalidateQueries({ queryKey: ['bots'] });
    }
    if (lastEvent.e === 'W' || lastEvent.e === 'R') {
      // WAGER / RESEARCH → feed has a new entry; don't wait for 5s poll
      void queryClient.invalidateQueries({ queryKey: ['activity-feed'] });
    }
  }, [lastEvent, queryClient]);

  // ── Derived data for topology polish ─────────────────────────────────────────

  const botLastAction = useMemo(() => {
    const map = new Map<number, string>();
    for (const e of feedEntries) {
      if (!map.has(e.bot_id)) map.set(e.bot_id, e.content);
    }
    return map;
  }, [feedEntries]);

  const recentBotIds = useMemo(() => {
    const ids    = new Set<number>();
    const cutoff = Date.now() - 30_000;
    for (const e of feedEntries.slice(0, 30)) {
      if (new Date(e.created_at).getTime() > cutoff) ids.add(e.bot_id);
    }
    return ids;
  }, [feedEntries]);

  return (
    <div className="arena-container relative h-full flex flex-col gap-3 p-3 bg-oled-black overflow-hidden">

      {/* ── AGENT VIABILITY MODAL ────────────────────────────────────────────── */}
      {selectedAgentId !== null && (
        <AgentViabilityModal
          botId={selectedAgentId}
          onClose={() => setSelectedAgentId(null)}
        />
      )}

      {/* ── COMMAND PALETTE ──────────────────────────────────────────────────── */}
      <CommandPalette
        open={isCommandOpen}
        onClose={closeCommand}
        onToggle={toggleCommand}
        onAction={handleCommandAction}
      />

      {/* ── TOP BAR ──────────────────────────────────────────────────────────── */}
      <TopBar
        aliveCount={alive.length}
        deadCount={dead.length}
        marketCount={openMarkets.length}
        onCommandOpen={() => setCommand(true)}
        wsConnected={wsConnected}
      />

      {/* ── LIVE TICKER ──────────────────────────────────────────────────────── */}
      <TickerBar
        streamEvents={streamEvents}
        connected={wsConnected}
        botsById={botsById}
        feedEntries={feedEntries}
      />

      {/* ── MAIN BENTO GRID ──────────────────────────────────────────────────── */}
      <div className="flex-1 min-h-0 grid grid-cols-[220px_1fr_264px] gap-3">

        {/* LEFT — Order Book: flat agent table */}
        <div className="rounded-xl border border-white/10 bg-black/70 backdrop-blur-xl overflow-hidden flex flex-col" style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)' }}>
          <BattlePanel bots={allBots} now={now} liveEventByBotId={liveEventByBotId} onAgentClick={(bot) => setSelectedAgentId(bot.id)} />
        </div>

        {/* CENTER — Stats bento + Agent topology + Markets */}
        <div className="flex flex-col gap-3 overflow-y-auto min-h-0">

          {/* 2×2 stat cards */}
          <div className="grid grid-cols-2 gap-3 shrink-0">
            <StatCard
              icon={Users}
              label="ACTIVE AGENTS"
              value={alive.length}
              variant="green"
              sub={`${allBots.length} total deployed`}
            />
            <StatCard
              icon={DollarSign}
              label="TOTAL ECONOMY"
              value={`${totalEconomy.toFixed(0)}c`}
              variant="amber"
              sub={alive.length > 0 ? `${(totalEconomy / alive.length).toFixed(0)}c avg/agent` : 'no agents'}
            />
            <StatCard
              icon={Search}
              label="OPEN MARKETS"
              value={openMarkets.length}
              variant="cyan"
              sub={`${openMarkets.filter((m) => m.source_type === 'RESEARCH').length} research bounties`}
            />
            <StatCard
              icon={Skull}
              label="CASUALTIES"
              value={dead.length}
              variant="red"
              sub={allBots.length > 0 ? `${((dead.length / allBots.length) * 100).toFixed(0)}% lethality` : 'no data'}
            />
          </div>

          {/* Agent topology — labeled SVG node graph with tooltips + kb-nav */}
          <AgentTopology
            bots={allBots}
            recentActivity={botLastAction}
            recentBotIds={recentBotIds}
            latestEvent={lastEvent}
            onAgentClick={(bot) => setSelectedAgentId(bot.id)}
          />

          {/* Active Markets */}
          <div className="shrink-0 pb-3">
            <div className="flex items-center justify-between mb-2.5">
              <div className="flex items-center gap-2">
                <Search size={12} className="text-accent-cyan" />
                <span className="text-[10px] font-sans font-semibold text-accent-cyan uppercase tracking-widest">
                  ACTIVE MARKETS
                </span>
              </div>
              {openMarkets.length > 6 && (
                <span className="text-[9px] font-sans text-zinc-600 uppercase flex items-center gap-1 tracking-wider">
                  {openMarkets.length} TOTAL <ArrowRight size={9} />
                </span>
              )}
            </div>

            {openMarkets.length > 0 ? (
              <div className="grid grid-cols-2 gap-3">
                {openMarkets.slice(0, 6).map((market) => (
                  <MarketSnapshotCard key={market.id} market={market} now={now} />
                ))}
              </div>
            ) : (
              <div className="rounded-xl p-8 text-center text-[10px] font-sans text-zinc-600 uppercase tracking-widest border border-titan-border bg-titan-grey">
                NO OPEN MARKETS — AWAITING EXTERNAL DATA
              </div>
            )}
          </div>

        </div>

        {/* RIGHT — Dense ledger stream */}
        <div className="rounded-xl border border-white/10 bg-black/70 backdrop-blur-xl overflow-hidden flex flex-col" style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)' }}>
          <LedgerStream entries={feedEntries} streamEvents={streamEvents} botsById={botsById} />
        </div>

      </div>
    </div>
  );
};

export default ArenaDashboard;
