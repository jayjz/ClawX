// ClawX Arena — DARK FOREST ENTROPY GRINDER // v3.3
// 2026-02-23: Single SVG canvas. Zero panels. Pure game-theory consequence.
// Center entropy well · orbital agents · betrayal lines · graveyard debris · PD heatmap
// v3.3: Slide-in battleground panel · sparklines · floating ⌘K event bridge

import { useState, useEffect, useMemo, useCallback, useRef, memo } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useBots, useMarkets, useActivityFeed } from '../api/client';
import { useArenaStream, type StreamEvent } from '../hooks';
import CommandPalette, { type CommandId } from './CommandPalette';
import AgentViabilityModal from './AgentViabilityModal';
import TickerBar from './TickerBar';
import type { Bot, ActivityEntry } from '../types';

// ── Constants ─────────────────────────────────────────────────────────────────

const INITIAL_BALANCE    = 1000;
const MAX_WELL_RAD_FRAC  = 0.20;
const ORBIT_RADII        = [105, 185, 265] as const;
const ORBIT_SPEEDS       = [22, 13, 7]    as const; // deg/s
const GOLDEN_ANGLE       = 137.508;
const GRAVEYARD_Y_FRAC   = 0.80;
const NODE_R_MIN         = 6;
const NODE_R_MAX         = 16;
const LINE_MAX_DIST      = 210;
const ENTROPY_DANGER     = 36;
const MAX_SPARK          = 30; // 30 × 10s = 5-min sparkline window

// ── Types ─────────────────────────────────────────────────────────────────────

interface AgentPos {
  bot:    Bot;
  x:      number;
  y:      number;
  ring:   0 | 1 | 2;
  orbitR: number;
  nodeR:  number;
}

interface GraveyardShard {
  botId:   number;
  handle:  string;
  xFrac:   number;
  yFrac:   number;
  rot:     number;
  opacity: number;
}

interface SparkPt { t: number; v: number; }

// ── Helpers ───────────────────────────────────────────────────────────────────

function nodeRadius(balance: number, maxBal: number): number {
  const frac = maxBal > 0 ? balance / maxBal : 0.5;
  return NODE_R_MIN + frac * (NODE_R_MAX - NODE_R_MIN);
}

// ── Entropy Well ──────────────────────────────────────────────────────────────

const EntropyWell = memo(({ cx, cy, r }: { cx: number; cy: number; r: number }) => (
  <g>
    <defs>
      <radialGradient id="ewg" cx="50%" cy="50%" r="50%">
        <stop offset="0%"   stopColor="#000000" stopOpacity="1" />
        <stop offset="55%"  stopColor="#1a0000" stopOpacity="0.95" />
        <stop offset="80%"  stopColor="#3d0000" stopOpacity="0.55" />
        <stop offset="100%" stopColor="#FF3B30"  stopOpacity="0" />
      </radialGradient>
      <filter id="ewf" x="-50%" y="-50%" width="200%" height="200%">
        <feGaussianBlur stdDeviation="10" result="blur" />
        <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
      </filter>
    </defs>

    {/* Outer glow halos */}
    <circle cx={cx} cy={cy} r={r * 1.9} fill="none" stroke="#FF3B30" strokeWidth={0.8} opacity={0.07}>
      <animate attributeName="r"       values={`${r*1.75};${r*2.1};${r*1.75}`} dur="4.5s" repeatCount="indefinite" />
      <animate attributeName="opacity" values="0.07;0.16;0.07"                  dur="4.5s" repeatCount="indefinite" />
    </circle>
    <circle cx={cx} cy={cy} r={r * 1.35} fill="none" stroke="#FF3B30" strokeWidth={0.5} opacity={0.18}>
      <animate attributeName="r" values={`${r*1.25};${r*1.5};${r*1.25}`} dur="2.9s" repeatCount="indefinite" />
    </circle>

    {/* Event horizon */}
    <circle cx={cx} cy={cy} r={r} fill="url(#ewg)" filter="url(#ewf)" />

    {/* Singularity */}
    <circle cx={cx} cy={cy} r={r * 0.32} fill="#000" opacity={0.98} />
    <circle cx={cx} cy={cy} r={r * 0.32} fill="none" stroke="#FF3B30" strokeWidth={0.9} opacity={0.5}>
      <animate attributeName="opacity" values="0.5;0.9;0.5" dur="1.4s" repeatCount="indefinite" />
    </circle>

    {/* Label */}
    <text x={cx} y={cy + 4} textAnchor="middle" fill="#FF3B30" fontSize={8}
      fontFamily='"JetBrains Mono","Courier New",monospace' opacity={0.45} letterSpacing="2">
      ENTROPY
    </text>
  </g>
));

// ── Orbit Rings ───────────────────────────────────────────────────────────────

const OrbitRings = memo(({ cx, cy }: { cx: number; cy: number }) => (
  <g opacity={0.055}>
    {ORBIT_RADII.map((r, i) => (
      <circle key={i} cx={cx} cy={cy} r={r} fill="none" stroke="#00FF9F"
        strokeWidth={0.5} strokeDasharray="3,8" />
    ))}
  </g>
));

// ── Betrayal Lines ────────────────────────────────────────────────────────────

interface BLine {
  key: string;
  x1: number; y1: number; x2: number; y2: number;
  defection: boolean;
  opacity: number;
  sw: number;
}

const BetrayalLines = memo(({
  positions, eventCountsByBot,
}: {
  positions: AgentPos[];
  eventCountsByBot: Map<number, { W: number; total: number }>;
}) => {
  const lines = useMemo<BLine[]>(() => {
    const out: BLine[] = [];
    for (let i = 0; i < positions.length; i++) {
      for (let j = i + 1; j < positions.length; j++) {
        const a = positions[i];
        const b = positions[j];
        if (!a || !b) continue;
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist > LINE_MAX_DIST) continue;
        const as = eventCountsByBot.get(a.bot.id) ?? { W: 0, total: 1 };
        const bs = eventCountsByBot.get(b.bot.id) ?? { W: 0, total: 1 };
        const defRate = (as.W + bs.W) / (as.total + bs.total + 1);
        const defection = defRate > 0.35;
        const df = 1 - dist / LINE_MAX_DIST;
        out.push({
          key: `${a.bot.id}-${b.bot.id}`,
          x1: a.x, y1: a.y, x2: b.x, y2: b.y,
          defection,
          opacity: df * (defection ? 0.55 : 0.22),
          sw: df * (defection ? 1.5 : 0.7),
        });
      }
    }
    return out;
  }, [positions, eventCountsByBot]);

  return (
    <g>
      {lines.map((l) => (
        <line
          key={l.key}
          x1={l.x1} y1={l.y1} x2={l.x2} y2={l.y2}
          stroke={l.defection ? '#FF3B30' : '#00FF9F'}
          strokeWidth={l.sw}
          opacity={l.opacity}
          strokeDasharray={l.defection ? '3,5' : undefined}
        >
          {l.defection && (
            <animate attributeName="opacity"
              values={`${l.opacity};${l.opacity * 0.2};${l.opacity}`}
              dur="1.3s" repeatCount="indefinite" />
          )}
        </line>
      ))}
    </g>
  );
});

// ── Graveyard Debris ──────────────────────────────────────────────────────────

const GraveyardDebris = memo(({ shards, W, H }: {
  shards: GraveyardShard[];
  W: number;
  H: number;
}) => {
  const yStart = H * GRAVEYARD_Y_FRAC;
  const yRange = H * (1 - GRAVEYARD_Y_FRAC) - 24;
  return (
    <g>
      <line x1={0} y1={yStart} x2={W} y2={yStart}
        stroke="#FF3B30" strokeWidth={0.4} opacity={0.10} strokeDasharray="5,10" />
      <text x={10} y={yStart + 12} fill="#FF3B30" fontSize={7}
        fontFamily='"JetBrains Mono","Courier New",monospace'
        opacity={0.18} letterSpacing="2">
        GRAVEYARD
      </text>
      {shards.map((s) => {
        const x = s.xFrac * W;
        const y = yStart + s.yFrac * yRange;
        const r = 3.5;
        return (
          <g key={s.botId}
            transform={`translate(${x.toFixed(1)},${y.toFixed(1)}) rotate(${s.rot})`}
            opacity={s.opacity}>
            <line x1={-r} y1={-r} x2={r} y2={r} stroke="#FF3B30" strokeWidth={1.2} />
            <line x1={r}  y1={-r} x2={-r} y2={r} stroke="#FF3B30" strokeWidth={1.2} />
            <text x={0} y={r + 10} textAnchor="middle" fill="#FF3B30" fontSize={7}
              fontFamily='"JetBrains Mono","Courier New",monospace' opacity={0.55}>
              {s.handle.slice(0, 8)}
            </text>
          </g>
        );
      })}
    </g>
  );
});

// ── Agent Node ────────────────────────────────────────────────────────────────

interface AgentNodeProps {
  pos:         AgentPos;
  isDominant:  boolean;
  isHovered:   boolean;
  recentEvent: StreamEvent['e'] | undefined;
  onHover:     (bot: Bot | null) => void;
  onHoverPos:  (x: number, y: number) => void;
  onClick:     (bot: Bot) => void;
}

const AgentNodeFixed = memo(({
  pos, isDominant, isHovered, recentEvent, onHover, onHoverPos, onClick,
}: AgentNodeProps) => {
  const { bot, x, y, nodeR } = pos;
  const balance  = Number(bot.balance);
  const isDanger = balance < ENTROPY_DANGER;
  const color    = isDanger ? '#FF3B30' : '#00FF9F';
  const pulseDur = `${2.2 + (bot.id % 5) * 0.28}s`;
  const flashCol = recentEvent === 'L' ? '#FF3B30' : recentEvent === 'W' ? '#FF9500' : null;
  const label    = bot.handle.length > 10 ? bot.handle.slice(0, 9) + '…' : bot.handle;

  return (
    <g
      style={{ cursor: 'pointer' }}
      onMouseEnter={(e) => { onHover(bot); onHoverPos(e.clientX, e.clientY); }}
      onMouseLeave={() => onHover(null)}
      onClick={() => onClick(bot)}
    >
      {isDominant && (
        <g>
          <circle cx={x} cy={y} r={nodeR + 15} fill="none"
            stroke="#00FF9F" strokeWidth={1.2} opacity={0.5} strokeDasharray="4,3">
            <animateTransform attributeName="transform" type="rotate"
              from={`0 ${x} ${y}`} to={`360 ${x} ${y}`}
              dur="7s" repeatCount="indefinite" />
          </circle>
          <text x={x} y={y - nodeR - 8} textAnchor="middle" fill="#00FF9F"
            fontSize={11} fontFamily='"JetBrains Mono","Courier New",monospace' opacity={0.9}>
            ♛
          </text>
        </g>
      )}

      {isDanger && (
        <circle cx={x} cy={y} r={nodeR + 6} fill="none"
          stroke="#FF3B30" strokeWidth={1.1} opacity={0.55}>
          <animate attributeName="opacity" values="0.55;0.1;0.55" dur="1s" repeatCount="indefinite" />
        </circle>
      )}

      {isHovered && (
        <circle cx={x} cy={y} r={nodeR + 9} fill="none"
          stroke={color} strokeWidth={1.4} opacity={0.7} strokeDasharray="3,2" />
      )}

      {flashCol && (
        <circle cx={x} cy={y} r={nodeR + 7} fill="none"
          stroke={flashCol} strokeWidth={1.5} opacity={0.85} />
      )}

      <circle cx={x} cy={y} r={nodeR} fill="none" stroke={color} strokeWidth={1} opacity={0.18}>
        <animate attributeName="r"
          values={`${nodeR};${nodeR + 11};${nodeR}`} dur={pulseDur} repeatCount="indefinite" />
        <animate attributeName="opacity"
          values="0.18;0.02;0.18" dur={pulseDur} repeatCount="indefinite" />
      </circle>

      <circle cx={x} cy={y} r={nodeR} fill={color} opacity={0.88}>
        <animate attributeName="opacity" values="0.88;0.62;0.88"
          dur={`${3 + (bot.id % 4) * 0.4}s`} repeatCount="indefinite" />
      </circle>

      <text x={x} y={y + nodeR + 13} textAnchor="middle" fill={color} fontSize={9}
        fontFamily='"JetBrains Mono","Courier New",monospace'
        opacity={isHovered ? 1 : 0.82} letterSpacing="0.3">
        {label}
      </text>
      <text x={x} y={y + nodeR + 22} textAnchor="middle" fill={color} fontSize={8}
        fontFamily='"JetBrains Mono","Courier New",monospace' opacity={0.38}>
        {balance.toFixed(0)}c
      </text>
    </g>
  );
});

// ── Prisoner's Dilemma Heatmap ────────────────────────────────────────────────

const PDHeatmap = memo(({
  hoveredBot, allBots, eventCountsByBot, screenX, screenY,
}: {
  hoveredBot:       Bot;
  allBots:          Bot[];
  eventCountsByBot: Map<number, { W: number; total: number }>;
  screenX:          number;
  screenY:          number;
}) => {
  const others = allBots.filter(b => b.status === 'ALIVE' && b.id !== hoveredBot.id).slice(0, 8);
  const hs     = eventCountsByBot.get(hoveredBot.id) ?? { W: 0, total: 1 };
  const hCoop  = 1 - (hs.W / Math.max(hs.total, 1));

  const boxW = 224;
  const boxH = 82 + others.length * 22;
  const bx   = Math.min(screenX + 16, (typeof window !== 'undefined' ? window.innerWidth : 1200) - boxW - 16);
  const by   = Math.min(screenY - 20, (typeof window !== 'undefined' ? window.innerHeight : 700) - boxH - 16);

  return (
    <div className="fixed z-50 pointer-events-none" style={{ left: bx, top: by, width: boxW }}>
      <div className="rounded-xl border border-zinc-700 bg-black/96 backdrop-blur-xl p-3"
        style={{ boxShadow: '0 8px 40px rgba(0,0,0,0.95), 0 0 24px rgba(255,59,48,0.08)' }}>

        {/* Header */}
        <div className="flex items-center gap-2 mb-2 pb-2 border-b border-zinc-800">
          <span className="w-2 h-2 rounded-full shrink-0"
            style={{ background: hoveredBot.status === 'ALIVE' ? '#00FF9F' : '#FF3B30' }} />
          <span className="text-xs font-sans font-bold text-white truncate">{hoveredBot.handle}</span>
          <span className="ml-auto text-[10px] font-mono text-zinc-500">
            {Number(hoveredBot.balance).toFixed(0)}c
          </span>
        </div>

        {/* Self cooperation bar */}
        <div className="flex items-center justify-between mb-2">
          <span className="text-[9px] font-sans text-zinc-500 uppercase tracking-wider">Cooperation</span>
          <div className="flex items-center gap-1.5">
            <div className="w-16 h-1.5 rounded-full bg-zinc-800 overflow-hidden">
              <div className="h-full rounded-full transition-all duration-500"
                style={{ width: `${hCoop * 100}%`, background: hCoop > 0.5 ? '#00FF9F' : '#FF3B30' }} />
            </div>
            <span className="text-[9px] font-mono text-zinc-400">{(hCoop * 100).toFixed(0)}%</span>
          </div>
        </div>

        {/* PD matrix */}
        <div className="text-[8px] font-sans text-zinc-600 uppercase tracking-wider mb-1.5">
          DILEMMA vs FIELD
        </div>
        {others.map(other => {
          const os    = eventCountsByBot.get(other.id) ?? { W: 0, total: 1 };
          const oCoop = 1 - (os.W / Math.max(os.total, 1));
          const out   = hCoop > 0.5 && oCoop > 0.5 ? 'CC'
            : hCoop <= 0.5 && oCoop <= 0.5          ? 'DD'
            : hCoop > 0.5                            ? 'CD' : 'DC';
          const outCol = out === 'CC' ? '#00FF9F' : out === 'DD' ? '#FF3B30' : '#FF9500';
          return (
            <div key={other.id} className="flex items-center gap-1.5 py-[2px]">
              <span className="text-[9px] font-mono text-zinc-400 w-20 truncate">
                {other.handle.slice(0, 10)}
              </span>
              <div className="flex-1 h-1 rounded-full bg-zinc-800 overflow-hidden">
                <div className="h-full rounded-full"
                  style={{ width: `${oCoop * 100}%`, background: oCoop > 0.5 ? '#00FF9F' : '#FF3B30' }} />
              </div>
              <span className="text-[9px] font-mono font-bold w-6 text-right"
                style={{ color: outCol }}>{out}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
});

// ── Metrics Bar ───────────────────────────────────────────────────────────────

const MetricsBar = memo(({
  aliveCount, deadCount, lethality, totalEconomy,
  wellRadius, maxWellRadius, wsConnected, kiaFlash, onCommandOpen,
}: {
  aliveCount:    number;
  deadCount:     number;
  lethality:     number;
  totalEconomy:  number;
  wellRadius:    number;
  maxWellRadius: number;
  wsConnected:   boolean;
  kiaFlash:      boolean;
  onCommandOpen: () => void;
}) => (
  <div
    className="flex items-center justify-between px-4 h-10 rounded-xl border border-white/10 bg-black/80 backdrop-blur-xl shrink-0"
    style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)' }}
  >
    <div className="flex items-center gap-1.5">
      <span className="text-[9px] font-sans font-bold text-white tracking-tight mr-2">DARK FOREST</span>

      <span className="px-2 py-0.5 rounded-full border border-accent-green/30 bg-accent-green/10 text-[9px] font-mono text-accent-green">
        {aliveCount} ALIVE
      </span>

      <span className={`px-2 py-0.5 rounded-full border text-[9px] font-mono ${
        lethality > 50
          ? 'border-accent-red/50 bg-accent-red/15 text-accent-red animate-pulse'
          : 'border-accent-red/30 bg-accent-red/5 text-accent-red/80'
      }`}>
        {lethality.toFixed(0)}% LETHALITY
      </span>

      <span className={`px-2 py-0.5 rounded-full border text-[9px] font-mono transition-colors ${
        kiaFlash
          ? 'border-accent-red/60 bg-accent-red/20 text-accent-red animate-pulse'
          : 'border-zinc-700/50 bg-zinc-800/30 text-zinc-500'
      }`}>
        ☠ {deadCount} KIA
      </span>

      <span className="px-2 py-0.5 rounded-full border border-accent-amber/30 bg-accent-amber/5 text-[9px] font-mono text-accent-amber">
        {totalEconomy.toFixed(0)}c ECONOMY
      </span>
    </div>

    <div className="flex items-center gap-3">
      {/* Well drain indicator */}
      <div className="flex items-center gap-1.5">
        <span className="text-[8px] font-sans text-zinc-600 uppercase tracking-wider">WELL</span>
        <div className="w-14 h-1 rounded-full bg-zinc-800 overflow-hidden">
          <div
            className="h-full rounded-full bg-accent-red/70 transition-all duration-1000"
            style={{ width: `${maxWellRadius > 0 ? (wellRadius / maxWellRadius) * 100 : 0}%` }}
          />
        </div>
      </div>

      <span className={`flex items-center gap-1 text-[9px] font-mono ${wsConnected ? 'text-accent-green' : 'text-zinc-600'}`}>
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${wsConnected ? 'bg-accent-green animate-pulse' : 'bg-zinc-700'}`} />
        WS
      </span>

      <button
        onClick={onCommandOpen}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-zinc-700 bg-oled-black hover:border-accent-green/50 transition-all"
      >
        <kbd className="text-[10px] font-mono text-accent-green font-bold leading-none">⌘K</kbd>
      </button>
    </div>
  </div>
));

// ── Sparkline ─────────────────────────────────────────────────────────────────

const Sparkline = memo(({ data, H, color }: {
  data: SparkPt[]; H: number; color: string;
}) => {
  const VW = 192;
  if (data.length < 2) {
    return (
      <svg viewBox={`0 0 ${VW} ${H}`} preserveAspectRatio="none"
           width="100%" height={H} style={{ display: 'block' }}>
        <line x1={0} y1={H * 0.5} x2={VW} y2={H * 0.5}
          stroke={color} strokeWidth={0.6} opacity={0.15} strokeDasharray="4,5" />
      </svg>
    );
  }
  const vals  = data.map(p => p.v);
  const lo    = Math.min(...vals);
  const hi    = Math.max(...vals);
  const span  = hi - lo || 1;
  const inner = H - 6;
  const pts   = data.map((p, i) => {
    const x = (i / (data.length - 1)) * VW;
    const y = 3 + inner - ((p.v - lo) / span) * inner;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  return (
    <svg viewBox={`0 0 ${VW} ${H}`} preserveAspectRatio="none"
         width="100%" height={H} style={{ display: 'block' }}>
      <polyline points={pts} fill="none" stroke={color}
        strokeWidth={1.4} strokeLinejoin="round" strokeLinecap="round" opacity={0.88} />
    </svg>
  );
});

// ── Battleground Panel ────────────────────────────────────────────────────────

const BattlegroundPanel = memo(({
  aliveCount, deadCount, totalEconomy,
  aliveSpark, deathsSpark, econSpark, rschSpark,
  deathsPerMin, rschPerMin, entropyBurn,
}: {
  aliveCount:    number;
  deadCount:     number;
  totalEconomy:  number;
  aliveSpark:    SparkPt[];
  deathsSpark:   SparkPt[];
  econSpark:     SparkPt[];
  rschSpark:     SparkPt[];
  deathsPerMin:  number;
  rschPerMin:    number;
  entropyBurn:   number;
}) => (
  <div className="bg-panel">
    <div className="bg-panel__header">
      <span className="bg-live-tag">● LIVE</span>
      <span className="bg-panel__title">AGENT BATTLEGROUND</span>
      <span className="bg-panel__meta">5-MIN · 10s SAMPLE</span>
    </div>

    <div className="bg-stats">
      <div className="bg-stat">
        <div className="bg-stat__row">
          <span className="bg-stat__label">ALIVE</span>
          <span className="bg-stat__sub">AGENTS</span>
        </div>
        <span className="bg-stat__val" style={{ color: '#00FF9F' }}>{aliveCount}</span>
        <Sparkline data={aliveSpark} H={28} color="#00FF9F" />
      </div>

      <div className="bg-stat bg-stat--accent">
        <div className="bg-stat__row">
          <span className="bg-stat__label">DEATHS</span>
          <span className="bg-stat__sub">{deathsPerMin}/MIN</span>
        </div>
        <span className="bg-stat__val" style={{ color: '#FF3B30' }}>{deadCount}</span>
        <Sparkline data={deathsSpark} H={28} color="#FF3B30" />
      </div>

      <div className="bg-stat">
        <div className="bg-stat__row">
          <span className="bg-stat__label">RESEARCH</span>
          <span className="bg-stat__sub">{rschPerMin}/MIN</span>
        </div>
        <span className="bg-stat__val" style={{ color: '#00F0FF' }}>{rschPerMin}</span>
        <Sparkline data={rschSpark} H={28} color="#00F0FF" />
      </div>

      <div className="bg-stat">
        <div className="bg-stat__row">
          <span className="bg-stat__label">ECONOMY</span>
          <span className="bg-stat__sub">TOTAL BALANCE</span>
        </div>
        <span className="bg-stat__val" style={{ color: '#FF9500' }}>
          {totalEconomy.toFixed(0)}<span style={{ fontSize: '0.5rem', opacity: 0.5 }}>c</span>
        </span>
        <Sparkline data={econSpark} H={28} color="#FF9500" />
      </div>

      <div className="bg-stat">
        <div className="bg-stat__row">
          <span className="bg-stat__label">ENTROPY BURN</span>
          <span className="bg-stat__sub">COUNTERFACTUAL/MIN</span>
        </div>
        <span className="bg-stat__val" style={{ color: '#FF3B30', fontSize: '0.875rem' }}>
          {entropyBurn.toFixed(2)}<span style={{ fontSize: '0.5rem', opacity: 0.5 }}>c</span>
        </span>
      </div>
    </div>
  </div>
));

// ── Main Arena Dashboard ──────────────────────────────────────────────────────

const ArenaDashboard = () => {
  const queryClient = useQueryClient();
  const { data: bots,    refetch: refetchBots    } = useBots();
  const { data: markets, refetch: refetchMarkets } = useMarkets();
  const { data: feed,    refetch: refetchFeed    } = useActivityFeed();
  const { events: streamEvents, lastEvent, connected: wsConnected } = useArenaStream();

  // ── UI state ────────────────────────────────────────────────────────────────
  const [isCommandOpen,  setCommand]      = useState(false);
  const [selectedAgentId, setAgentId]    = useState<number | null>(null);
  const [hoveredBot,    setHoveredBot]   = useState<Bot | null>(null);
  const [hoverPos,      setHoverPos]     = useState({ x: 0, y: 0 });
  const [animTick,      setAnimTick]     = useState(0);
  const [kiaFlash,      setKiaFlash]     = useState(false);
  const [dims,          setDims]         = useState({ w: 1200, h: 700 });
  const [graveyardShards, setGraveyard] = useState<GraveyardShard[]>([]);
  const [sidePanel,     setSidePanel]   = useState<'ledger' | 'orderbook' | 'battleground' | null>(null);
  const [bgSpark,       setBgSpark]     = useState<{
    alive: SparkPt[]; deaths: SparkPt[]; economy: SparkPt[]; research: SparkPt[];
  }>({ alive: [], deaths: [], economy: [], research: [] });

  // ── Refs ─────────────────────────────────────────────────────────────────────
  const containerRef  = useRef<HTMLDivElement>(null);
  const prevDeadRef   = useRef<number | null>(null);
  const seenDeadIds   = useRef<Set<number>>(new Set());
  const bgEvtLog      = useRef<Array<{ t: number; e: string }>>([]);
  const bgCurRef      = useRef({ alive: 0, deaths: 0, economy: 0 });

  // ── Canvas resize ───────────────────────────────────────────────────────────
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver((entries) => {
      const r = entries[0]?.contentRect;
      if (r) setDims({ w: Math.floor(r.width), h: Math.floor(r.height) });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // ── Orbital animation ────────────────────────────────────────────────────────
  useEffect(() => {
    const id = setInterval(() => setAnimTick((t) => t + 1), 120);
    return () => clearInterval(id);
  }, []);

  // ── Data ─────────────────────────────────────────────────────────────────────
  const allBots:   Bot[]           = bots ?? [];
  const aliveBots: Bot[]           = useMemo(() => allBots.filter(b => b.status === 'ALIVE'), [allBots]);
  const deadBots:  Bot[]           = useMemo(() => allBots.filter(b => b.status === 'DEAD'),  [allBots]);
  const feedEntries: ActivityEntry[] = feed ?? [];
  const openMarkets                = markets ?? [];

  const totalEconomy = useMemo(
    () => allBots.reduce((s, b) => s + Number(b.balance), 0),
    [allBots],
  );
  const lethality = allBots.length > 0 ? (deadBots.length / allBots.length) * 100 : 0;

  const botsById = useMemo(() => {
    const m = new Map<number, string>();
    for (const b of allBots) m.set(b.id, b.handle);
    return m;
  }, [allBots]);

  // ── Stale-closure-free ref update (during render) ────────────────────────────
  bgCurRef.current = { alive: aliveBots.length, deaths: deadBots.length, economy: totalEconomy };

  // ── WS event counts per bot (for betrayal + PD) ──────────────────────────────
  const eventCountsByBot = useMemo(() => {
    const m = new Map<number, { W: number; total: number }>();
    for (const ev of streamEvents) {
      const c = m.get(ev.b) ?? { W: 0, total: 0 };
      m.set(ev.b, { W: c.W + (ev.e === 'W' ? 1 : 0), total: c.total + 1 });
    }
    return m;
  }, [streamEvents]);

  // ── KIA flash ────────────────────────────────────────────────────────────────
  useEffect(() => {
    const dc = deadBots.length;
    if (prevDeadRef.current !== null && dc > prevDeadRef.current) {
      setKiaFlash(true);
      const t = setTimeout(() => setKiaFlash(false), 800);
      prevDeadRef.current = dc;
      return () => clearTimeout(t);
    }
    prevDeadRef.current = dc;
  }, [deadBots.length]);

  // ── Graveyard accumulation ────────────────────────────────────────────────────
  useEffect(() => {
    let changed = false;
    const next: GraveyardShard[] = [];
    for (const bot of deadBots) {
      if (!seenDeadIds.current.has(bot.id)) {
        seenDeadIds.current.add(bot.id);
        next.push({
          botId:   bot.id,
          handle:  bot.handle,
          xFrac:   0.04 + Math.random() * 0.92,
          yFrac:   0.04 + Math.random() * 0.82,
          rot:     Math.random() * 360,
          opacity: 0.3 + Math.random() * 0.3,
        });
        changed = true;
      }
    }
    if (changed) setGraveyard(prev => [...prev, ...next]);
  }, [deadBots]);

  // ── Cache invalidation ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.e === 'L') void queryClient.invalidateQueries({ queryKey: ['bots'] });
    if (lastEvent.e === 'W' || lastEvent.e === 'R')
      void queryClient.invalidateQueries({ queryKey: ['activity-feed'] });
  }, [lastEvent, queryClient]);

  // ── Battleground: event log tracker ──────────────────────────────────────────
  useEffect(() => {
    if (!lastEvent) return;
    const now = Date.now();
    bgEvtLog.current = [
      ...bgEvtLog.current.filter(x => x.t > now - 5 * 60_000),
      { t: now, e: lastEvent.e },
    ];
  }, [lastEvent]);

  // ── Battleground: 10-second sparkline sampler ─────────────────────────────────
  useEffect(() => {
    const sample = () => {
      const now     = Date.now();
      const c       = bgCurRef.current;
      const rschNow = bgEvtLog.current.filter(x => x.t > now - 60_000 && x.e === 'R').length;
      setBgSpark(prev => ({
        alive:    [...prev.alive.slice(-(MAX_SPARK - 1)),    { t: now, v: c.alive }],
        deaths:   [...prev.deaths.slice(-(MAX_SPARK - 1)),   { t: now, v: c.deaths }],
        economy:  [...prev.economy.slice(-(MAX_SPARK - 1)),  { t: now, v: c.economy }],
        research: [...prev.research.slice(-(MAX_SPARK - 1)), { t: now, v: rschNow }],
      }));
    };
    sample();
    const id = setInterval(sample, 10_000);
    return () => clearInterval(id);
  }, []);

  // ── Battleground: per-minute rates ───────────────────────────────────────────
  const bgRates = useMemo(() => {
    const now = Date.now();
    const cut = now - 60_000;
    const r1m = bgEvtLog.current.filter(x => x.t > cut);
    return {
      deathsPerMin:      r1m.filter(x => x.e === 'L').length,
      researchPerMin:    r1m.filter(x => x.e === 'R').length,
      entropyBurnPerMin: parseFloat((aliveBots.length * 0.5 * 6).toFixed(2)),
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastEvent, aliveBots.length]);

  // ── Custom event bridge (from TerminalLayout floating bar) ────────────────────
  useEffect(() => {
    const handler = () => setCommand(true);
    window.addEventListener('clawx:command-open', handler);
    return () => window.removeEventListener('clawx:command-open', handler);
  }, []);

  useEffect(() => {
    const handler = (e: Event) => {
      const panel = (e as CustomEvent<string>).detail as 'ledger' | 'orderbook' | 'battleground';
      setSidePanel(prev => prev === panel ? null : panel);
    };
    window.addEventListener('clawx:panel', handler);
    return () => window.removeEventListener('clawx:panel', handler);
  }, []);

  // ── Entropy well ──────────────────────────────────────────────────────────────
  const maxWellRadius = Math.min(dims.w, dims.h) * MAX_WELL_RAD_FRAC;
  const wellRadius = useMemo(() => {
    const genesis = aliveBots.length * INITIAL_BALANCE;
    if (genesis === 0) return maxWellRadius * 0.38;
    return maxWellRadius * Math.max(0.08, Math.min(1, totalEconomy / genesis));
  }, [totalEconomy, aliveBots.length, maxWellRadius]);

  // ── Canvas center ─────────────────────────────────────────────────────────────
  const cx = dims.w / 2;
  const cy = dims.h * 0.42;

  // ── Orbital positions ─────────────────────────────────────────────────────────
  const agentPositions = useMemo<AgentPos[]>(() => {
    const maxBal  = Math.max(...aliveBots.map(b => Number(b.balance)), 1);
    const elapsed = animTick * 0.12;
    return aliveBots.map((bot): AgentPos => {
      const balance  = Number(bot.balance);
      const balFrac  = balance / maxBal;
      const ring: 0 | 1 | 2 = balFrac > 0.66 ? 0 : balFrac > 0.33 ? 1 : 2;
      const orbitR   = ORBIT_RADII[ring];
      const speed    = ORBIT_SPEEDS[ring];
      const baseAngle = (bot.id * GOLDEN_ANGLE) % 360;
      const rad       = ((baseAngle + elapsed * speed) % 360) * (Math.PI / 180);
      return {
        bot,
        x:      cx + orbitR * Math.cos(rad),
        y:      cy + orbitR * Math.sin(rad),
        ring,
        orbitR,
        nodeR:  nodeRadius(balance, maxBal),
      };
    });
  }, [animTick, aliveBots, cx, cy]);

  // ── Dominant bot ─────────────────────────────────────────────────────────────
  const dominantId = useMemo(
    () => aliveBots.reduce<Bot | null>(
      (top, b) => (!top || Number(b.balance) > Number(top.balance)) ? b : top, null,
    )?.id ?? null,
    [aliveBots],
  );

  // ── Recent event by bot ───────────────────────────────────────────────────────
  const recentEvtByBot = useMemo(() => {
    const m: Record<number, StreamEvent['e']> = {};
    for (const ev of streamEvents) { if (!(ev.b in m)) m[ev.b] = ev.e; }
    return m;
  }, [streamEvents]);

  // ── Handlers ─────────────────────────────────────────────────────────────────
  const toggleCommand = useCallback(() => setCommand(v => !v), []);
  const closeCommand  = useCallback(() => setCommand(false), []);
  const handleAction  = useCallback((id: CommandId) => {
    if (id === 'system:refresh') {
      void refetchBots(); void refetchMarkets(); void refetchFeed();
    }
  }, [refetchBots, refetchMarkets, refetchFeed]);

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="arena-container relative h-full flex flex-col gap-1 bg-oled-black overflow-hidden">

      {/* Modals */}
      {selectedAgentId !== null && (
        <AgentViabilityModal botId={selectedAgentId} onClose={() => setAgentId(null)} />
      )}
      <CommandPalette
        open={isCommandOpen} onClose={closeCommand}
        onToggle={toggleCommand} onAction={handleAction}
      />

      {/* Metrics bar */}
      <MetricsBar
        aliveCount={aliveBots.length}
        deadCount={deadBots.length}
        lethality={lethality}
        totalEconomy={totalEconomy}
        wellRadius={wellRadius}
        maxWellRadius={maxWellRadius}
        wsConnected={wsConnected}
        kiaFlash={kiaFlash}
        onCommandOpen={() => setCommand(true)}
      />

      {/* Live ticker */}
      <TickerBar
        streamEvents={streamEvents}
        connected={wsConnected}
        botsById={botsById}
        feedEntries={feedEntries}
      />

      {/* Dark Forest SVG Arena + slide-in panel */}
      <div
        ref={containerRef}
        className="flex-1 min-h-0 relative rounded-xl border border-zinc-800/40 overflow-hidden"
        style={{ background: '#020202' }}
      >
        <svg
          width={dims.w}
          height={dims.h}
          style={{ display: 'block' }}
        >
          {/* Dot grid */}
          <defs>
            <pattern id="dg" x="0" y="0" width="40" height="40" patternUnits="userSpaceOnUse">
              <circle cx="0.5" cy="0.5" r="0.5" fill="#1a1a1a" />
            </pattern>
          </defs>
          <rect width={dims.w} height={dims.h} fill="url(#dg)" />

          {/* Orbit ring guides */}
          <OrbitRings cx={cx} cy={cy} />

          {/* Betrayal lines — rendered behind nodes */}
          <BetrayalLines positions={agentPositions} eventCountsByBot={eventCountsByBot} />

          {/* Entropy well */}
          <EntropyWell cx={cx} cy={cy} r={wellRadius} />

          {/* Agent nodes */}
          {agentPositions.map((pos) => (
            <AgentNodeFixed
              key={pos.bot.id}
              pos={pos}
              isDominant={pos.bot.id === dominantId}
              isHovered={hoveredBot?.id === pos.bot.id}
              recentEvent={recentEvtByBot[pos.bot.id]}
              onHover={setHoveredBot}
              onHoverPos={(x, y) => setHoverPos({ x, y })}
              onClick={(bot) => setAgentId(bot.id)}
            />
          ))}

          {/* Graveyard */}
          <GraveyardDebris shards={graveyardShards} W={dims.w} H={dims.h} />

          {/* Empty state */}
          {aliveBots.length === 0 && (
            <text x={cx} y={cy + 55} textAnchor="middle" fill="#2a2a2a" fontSize={11}
              fontFamily='"JetBrains Mono","Courier New",monospace' letterSpacing="3">
              NO AGENTS — DEPLOY TO ENTER THE DARK FOREST
            </text>
          )}

          {/* Market count overlay */}
          <text x={dims.w - 10} y={16} textAnchor="end" fill="#00F0FF" fontSize={8}
            fontFamily='"JetBrains Mono","Courier New",monospace' opacity={0.45}>
            {openMarkets.length} OPEN MARKETS
          </text>

          {/* Feed count overlay */}
          <text x={10} y={16} textAnchor="start" fill="#FF9500" fontSize={8}
            fontFamily='"JetBrains Mono","Courier New",monospace' opacity={0.45}>
            {feedEntries.length} FEED ENTRIES
          </text>
        </svg>

        {/* Prisoner's dilemma heatmap tooltip */}
        {hoveredBot !== null && (
          <PDHeatmap
            hoveredBot={hoveredBot}
            allBots={allBots}
            eventCountsByBot={eventCountsByBot}
            screenX={hoverPos.x}
            screenY={hoverPos.y}
          />
        )}

        {/* Slide-in panel — always in DOM, clipped by overflow:hidden above */}
        <div className={`slide-in-panel${sidePanel !== null ? ' slide-in-panel--open' : ''}`}>
          {sidePanel !== null && (
            <>
              <div className="flex items-center justify-between px-3 py-2 border-b border-white/[0.06] shrink-0">
                <span className="text-[9px] font-mono text-zinc-400 uppercase tracking-[0.15em]">
                  {sidePanel === 'ledger'
                    ? 'LEDGER'
                    : sidePanel === 'orderbook'
                    ? 'ORDER BOOK'
                    : 'BATTLEGROUND'}
                </span>
                <button
                  onClick={() => setSidePanel(null)}
                  className="text-[9px] font-mono text-zinc-600 hover:text-zinc-300 transition-colors"
                  aria-label="Close panel"
                >
                  ✕
                </button>
              </div>

              {sidePanel === 'battleground' ? (
                <div className="flex-1 overflow-y-auto">
                  <BattlegroundPanel
                    aliveCount={aliveBots.length}
                    deadCount={deadBots.length}
                    totalEconomy={totalEconomy}
                    aliveSpark={bgSpark.alive}
                    deathsSpark={bgSpark.deaths}
                    econSpark={bgSpark.economy}
                    rschSpark={bgSpark.research}
                    deathsPerMin={bgRates.deathsPerMin}
                    rschPerMin={bgRates.researchPerMin}
                    entropyBurn={bgRates.entropyBurnPerMin}
                  />
                </div>
              ) : (
                <div className="flex-1 overflow-y-auto p-3">
                  <p className="text-[8px] font-mono text-zinc-700 uppercase tracking-widest">
                    {sidePanel === 'ledger'
                      ? '// LEDGER · HASH CHAIN'
                      : '// ORDER BOOK · OPEN MARKETS'}
                  </p>
                  <p className="text-[8px] font-mono text-zinc-800 mt-2">
                    WIRE VIA GET /INSIGHTS/&#123;AGENT_ID&#125;
                  </p>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default ArenaDashboard;
