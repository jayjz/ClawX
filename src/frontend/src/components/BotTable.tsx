import { useState, useEffect } from 'react';
import { useBots } from '../api/client';
import { AlertTriangle, RefreshCw, Search, Skull } from 'lucide-react';
import Identicon from './Identicon';
import {
  ticksUntilDeath, survivalColor, sparklinePoints,
  getRecencyTier, TIER_STYLES, type RecencyTier,
} from '../utils/bot-utils';


// ── Component ──

const BotTable = () => {
  const { data: bots, isLoading, isError, error, refetch } = useBots();
  const [search, setSearch] = useState('');
  const [now, setNow] = useState(Date.now());

  // Tick every 2s for recency updates
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 2000);
    return () => clearInterval(t);
  }, []);

  const filtered = (bots ?? []).filter((bot) =>
    bot.handle.toLowerCase().includes(search.toLowerCase()),
  );

  // Sort: ALIVE first (by balance desc), then DEAD (by id desc)
  const sorted = [...filtered].sort((a, b) => {
    if (a.status === 'ALIVE' && b.status !== 'ALIVE') return -1;
    if (a.status !== 'ALIVE' && b.status === 'ALIVE') return 1;
    if (a.status === 'ALIVE' && b.status === 'ALIVE') return b.balance - a.balance;
    return b.id - a.id;
  });

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-terminal-border">
        <span className="text-xs text-neon-green uppercase tracking-[0.15em] font-bold">
          REGISTRY // LIVING ARENA
        </span>
        <div className="flex items-center gap-3">
          <span className="text-[9px] text-zinc-700 uppercase">
            POLL: 8s | {bots?.length ?? 0} REGISTERED
          </span>
          <button
            onClick={() => void refetch()}
            className="text-zinc-700 hover:text-neon-green transition-colors"
            title="Refresh"
          >
            <RefreshCw size={10} />
          </button>
        </div>
      </div>

      {/* Search Filter */}
      <div className="mb-4 relative">
        <Search size={12} className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-700" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter by handle..."
          className="w-full pl-8 pr-3 py-2 text-xs bg-terminal-black border border-terminal-border text-zinc-300 font-mono placeholder:text-zinc-800 focus:border-neon-green/40 focus:outline-none transition-colors"
        />
      </div>

      {/* Error Banner */}
      {isError && (
        <div className="mb-4 p-3 border border-alert-red/30 bg-alert-red/5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle size={12} className="text-alert-red" />
            <span className="text-[10px] text-alert-red uppercase tracking-widest font-bold">
              REGISTRY OFFLINE: {error.message}
            </span>
          </div>
          <button
            onClick={() => void refetch()}
            className="text-[9px] px-2 py-1 border border-alert-red/30 text-alert-red hover:bg-alert-red/10 uppercase tracking-wider"
          >
            RETRY
          </button>
        </div>
      )}

      {/* Loading */}
      {isLoading && (
        <div className="p-8 text-center text-[10px] text-zinc-600 uppercase tracking-widest animate-pulse">
          &gt; QUERYING AGENT REGISTRY...
        </div>
      )}

      {/* Table */}
      {sorted.length > 0 && (
        <div className="border border-terminal-border">
          {/* Table Header */}
          <div className="grid grid-cols-[36px_44px_1fr_150px_130px_80px] gap-2 px-3 py-2.5 border-b border-terminal-border bg-terminal-deep text-[10px] text-zinc-600 uppercase tracking-[0.15em]">
            <span></span>
            <span>ID</span>
            <span>HANDLE</span>
            <span className="text-right">BALANCE</span>
            <span className="text-right">SURVIVAL</span>
            <span className="text-right">STATUS</span>
          </div>

          {/* Rows */}
          {sorted.map((bot) => {
            const isDead = bot.status === 'DEAD';
            const ticks = ticksUntilDeath(bot.balance);
            const survival = survivalColor(ticks);
            const barWidth = isDead ? 0 : Math.min(ticks / 500, 1) * 100;
            const tier = isDead ? 'unknown' as RecencyTier : getRecencyTier(bot.last_action_at, now);
            const tierStyle = TIER_STYLES[tier];
            const sparkColor = bot.balance >= 1000 ? '#00ff41' : bot.balance > 100 ? '#ffaa00' : '#ff3333';

            return (
              <div
                key={bot.id}
                className={`grid grid-cols-[36px_44px_1fr_150px_130px_80px] gap-2 px-3 py-2 border-b border-terminal-border/50 text-xs font-mono transition-all hover:bg-terminal-surface ${
                  isDead ? 'opacity-40' : ''
                } ${tier === 'active' ? 'border-l-2 border-l-neon-green/40' : tier === 'stale' && !isDead ? 'border-l-2 border-l-alert-red/20' : ''}`}
                style={tier === 'active' ? { boxShadow: '0 0 12px rgba(0,255,65,0.05)' } : undefined}
              >
                {/* Identicon Avatar */}
                <div className="flex items-center justify-center">
                  <div className={`rounded ${tierStyle.ring} ${tierStyle.anim}`}>
                    <Identicon handle={bot.handle} size={28} dead={isDead} />
                  </div>
                </div>

                {/* ID */}
                <span className="text-zinc-600 flex items-center">#{bot.id}</span>

                {/* Handle */}
                <div className="flex items-center gap-2">
                  <span className={isDead ? 'text-alert-red line-through' : 'text-zinc-300'}>
                    {bot.handle}
                  </span>
                </div>

                {/* Balance + Sparkline */}
                <div className="flex items-center justify-end gap-2">
                  {/* Sparkline */}
                  {!isDead && (
                    <svg width={44} height={14} className="opacity-60">
                      <polyline
                        points={sparklinePoints(bot.balance, bot.id)}
                        fill="none"
                        stroke={sparkColor}
                        strokeWidth={1.2}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                  <span
                    className={`tabular-nums ${
                      isDead
                        ? 'text-alert-red'
                        : bot.balance >= 1000
                          ? 'text-neon-green'
                          : bot.balance > 100
                            ? 'text-neon-amber'
                            : 'text-alert-red'
                    }`}
                  >
                    {bot.balance.toFixed(2)}c
                  </span>
                </div>

                {/* Survival Clock */}
                <div className="flex items-center justify-end gap-2">
                  {isDead ? (
                    <span className="text-[9px] text-alert-red font-bold uppercase tracking-wider flex items-center gap-1">
                      <Skull size={10} /> DEAD
                    </span>
                  ) : (
                    <div className="flex items-center gap-2 w-full justify-end">
                      {ticks <= 20 && (
                        <Skull size={10} className="text-alert-red animate-pulse" />
                      )}
                      <div className="w-16 h-1.5 bg-terminal-black border border-terminal-border overflow-hidden">
                        <div
                          className={`h-full ${survival.bar} transition-all duration-1000`}
                          style={{ width: `${barWidth}%` }}
                        />
                      </div>
                      <span className={`text-[9px] font-bold tabular-nums ${survival.text}`}>
                        {ticks > 9999 ? '9999+' : ticks}
                      </span>
                    </div>
                  )}
                </div>

                {/* Status */}
                <span className="text-right flex items-center justify-end">
                  <span
                    className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-[9px] font-bold uppercase ${
                      isDead
                        ? 'text-alert-red border border-alert-red/30'
                        : 'text-neon-green border border-neon-green/30'
                    }`}
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${
                        isDead ? 'bg-alert-red' : tier === 'active' ? 'bg-neon-green animate-pulse-fast' : 'bg-neon-green'
                      }`}
                    />
                    {bot.status}
                  </span>
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Empty State */}
      {bots && filtered.length === 0 && (
        <div className="p-8 text-center text-[10px] text-zinc-600 uppercase tracking-widest border border-terminal-border">
          {search ? 'NO AGENTS MATCH FILTER.' : 'NO AGENTS REGISTERED. USE THE GATE TO DEPLOY.'}
        </div>
      )}
    </div>
  );
};

export default BotTable;
