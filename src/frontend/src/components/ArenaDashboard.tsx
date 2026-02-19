import { useState, useEffect } from 'react';
import { useBots, useMarkets } from '../api/client';
import { Users, DollarSign, Search, Skull, Clock, Zap, Trophy, ArrowRight } from 'lucide-react';
import Identicon from './Identicon';
import {
  ticksUntilDeath, survivalColor, sparklinePoints,
  getRecencyTier, TIER_STYLES, formatCountdown,
  type RecencyTier,
} from '../utils/bot-utils';

// ── Stat Card ──

const StatCard = ({ icon: Icon, label, value, color, sub }: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  color: string;
  sub?: string;
}) => (
  <div className="border border-terminal-border bg-terminal-deep p-4 flex items-center gap-3">
    <div className={`w-10 h-10 border flex items-center justify-center shrink-0 ${color}`}>
      <Icon size={16} />
    </div>
    <div>
      <div className="text-[9px] text-zinc-600 uppercase tracking-[0.15em]">{label}</div>
      <div className={`text-lg font-bold tabular-nums ${color.includes('green') ? 'text-neon-green' : color.includes('cyan') ? 'text-neon-cyan' : color.includes('amber') ? 'text-neon-amber' : 'text-alert-red'}`}>
        {value}
      </div>
      {sub && <div className="text-[9px] text-zinc-700">{sub}</div>}
    </div>
  </div>
);

// ── Agent Card ──

const AgentCard = ({ bot, now }: { bot: { id: number; handle: string; balance: number; status: string; last_action_at: string | null; created_at: string }; now: number }) => {
  const isDead = bot.status === 'DEAD';
  const ticks = ticksUntilDeath(bot.balance);
  const survival = survivalColor(ticks);
  const barWidth = isDead ? 0 : Math.min(ticks / 500, 1) * 100;
  const tier = isDead ? 'unknown' as RecencyTier : getRecencyTier(bot.last_action_at, now);
  const tierStyle = TIER_STYLES[tier];
  const sparkColor = bot.balance >= 1000 ? '#00ff41' : bot.balance > 100 ? '#ffaa00' : '#ff3333';

  return (
    <div
      className={`border border-terminal-border bg-terminal-deep p-4 transition-all hover:border-grid-line ${
        isDead ? 'opacity-40' : ''
      } ${tier === 'active' ? 'border-l-2 border-l-neon-green/40' : ''}`}
      style={tier === 'active' ? { boxShadow: '0 0 12px rgba(0,255,65,0.05)' } : undefined}
    >
      {/* Top: Avatar + Handle + Status */}
      <div className="flex items-center gap-3 mb-3">
        <div className={`rounded ${tierStyle.ring} ${tierStyle.anim}`}>
          <Identicon handle={bot.handle} size={36} dead={isDead} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`text-sm font-bold truncate ${isDead ? 'text-alert-red line-through' : 'text-zinc-200'}`}>
              {bot.handle}
            </span>
            <span className="text-[8px] text-zinc-700">#{bot.id}</span>
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 text-[8px] font-bold uppercase border ${
              isDead ? 'text-alert-red border-alert-red/30' : 'text-neon-green border-neon-green/30'
            }`}>
              <span className={`w-1 h-1 rounded-full ${
                isDead ? 'bg-alert-red' : tier === 'active' ? 'bg-neon-green animate-pulse-fast' : 'bg-neon-green'
              }`} />
              {bot.status}
            </span>
            {tier !== 'unknown' && !isDead && (
              <span className={`text-[8px] ${tier === 'active' ? 'text-neon-green' : tier === 'recent' ? 'text-neon-amber' : 'text-alert-red'}`}>
                {tierStyle.label}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Balance + Sparkline */}
      <div className="flex items-end justify-between mb-3">
        <span className={`text-xl font-bold tabular-nums ${
          isDead ? 'text-alert-red' : bot.balance >= 1000 ? 'text-neon-green' : bot.balance > 100 ? 'text-neon-amber' : 'text-alert-red'
        }`}>
          {bot.balance.toFixed(2)}<span className="text-xs opacity-60">c</span>
        </span>
        {!isDead && (
          <svg width={80} height={24} className="opacity-70">
            <polyline
              points={sparklinePoints(bot.balance, bot.id, 80, 24, 8)}
              fill="none"
              stroke={sparkColor}
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </div>

      {/* Survival Bar */}
      {isDead ? (
        <div className="flex items-center gap-1 text-[9px] text-alert-red font-bold uppercase">
          <Skull size={10} /> LIQUIDATED
        </div>
      ) : (
        <div className="flex items-center gap-2">
          {ticks <= 20 && <Skull size={10} className="text-alert-red animate-pulse" />}
          <div className="flex-1 h-1.5 bg-terminal-black border border-terminal-border overflow-hidden">
            <div
              className={`h-full ${survival.bar} transition-all duration-1000`}
              style={{ width: `${barWidth}%` }}
            />
          </div>
          <span className={`text-[9px] font-bold tabular-nums ${survival.text}`}>
            {ticks > 9999 ? '9999+' : ticks} ticks
          </span>
        </div>
      )}
    </div>
  );
};

// ── Market Card ──

const MarketSnapshotCard = ({ market, now }: { market: { id: string; description: string; source_type: string; bounty: number; deadline: string }; now: number }) => {
  const deadlineMs = new Date(market.deadline).getTime();
  const secondsLeft = Math.max(0, (deadlineMs - now) / 1000);
  const isExpired = secondsLeft <= 0;
  const isUrgent = secondsLeft > 0 && secondsLeft < 60;
  const isResearch = market.source_type === 'RESEARCH';

  const SOURCE_COLORS: Record<string, string> = {
    RESEARCH: 'border-neon-cyan/30 text-neon-cyan',
    GITHUB: 'border-neon-green/30 text-neon-green',
    NEWS: 'border-neon-amber/30 text-neon-amber',
    WEATHER: 'border-zinc-500/30 text-zinc-400',
  };
  const badgeColor = SOURCE_COLORS[market.source_type] ?? 'border-zinc-500/30 text-zinc-400';

  return (
    <div
      className={`border border-terminal-border bg-terminal-deep p-3 transition-all hover:border-grid-line ${
        isExpired ? 'opacity-40' : ''
      } ${isResearch && !isExpired ? 'border-l-2 border-l-neon-cyan bg-neon-cyan/[0.02]' : ''}`}
      style={isResearch && !isExpired ? { boxShadow: '0 0 12px rgba(0,212,255,0.06)' } : undefined}
    >
      <div className="flex items-center justify-between mb-2">
        <span className={`text-[8px] px-1.5 py-0.5 border uppercase font-bold ${badgeColor}`}>
          {market.source_type}
        </span>
        <div className="flex items-center gap-1">
          {isResearch && !isExpired && <Zap size={10} className="text-neon-cyan animate-pulse" />}
          <span className={`font-bold text-sm ${isResearch ? 'text-neon-cyan' : 'text-neon-green'}`}>
            {Number(market.bounty).toFixed(0)}c
          </span>
        </div>
      </div>
      <p className="text-xs text-zinc-400 truncate mb-2" title={market.description}>
        {market.description}
      </p>
      <div className="flex items-center justify-between">
        <span className={`text-[9px] flex items-center gap-1 ${
          isExpired ? 'text-zinc-600' : isUrgent ? 'text-alert-red animate-pulse' : 'text-zinc-500'
        }`}>
          <Clock size={9} />
          {isExpired ? 'EXPIRED' : formatCountdown(secondsLeft)}
        </span>
        {!isExpired && (
          <div className="w-16 h-1 bg-terminal-black border border-terminal-border/50 overflow-hidden">
            <div
              className={`h-full transition-all duration-1000 ${
                isUrgent ? 'bg-alert-red' : 'bg-neon-cyan'
              }`}
              style={{ width: `${Math.min((secondsLeft / 300) * 100, 100)}%` }}
            />
          </div>
        )}
      </div>
    </div>
  );
};

// ── Main Dashboard ──

const ArenaDashboard = () => {
  const { data: bots } = useBots();
  const { data: markets } = useMarkets();
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 2000);
    return () => clearInterval(t);
  }, []);

  const allBots = bots ?? [];
  const alive = allBots.filter((b) => b.status === 'ALIVE');
  const dead = allBots.filter((b) => b.status === 'DEAD');
  const totalEconomy = allBots.reduce((sum, b) => sum + b.balance, 0);
  const openMarkets = markets ?? [];

  // Sort: ALIVE by balance desc, then DEAD
  const sortedBots = [...allBots].sort((a, b) => {
    if (a.status === 'ALIVE' && b.status !== 'ALIVE') return -1;
    if (a.status !== 'ALIVE' && b.status === 'ALIVE') return 1;
    if (a.status === 'ALIVE' && b.status === 'ALIVE') return b.balance - a.balance;
    return b.id - a.id;
  });

  return (
    <div className="space-y-6">
      {/* Section: Arena Stats */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Trophy size={12} className="text-neon-amber" />
          <span className="text-[10px] text-neon-amber uppercase tracking-[0.15em] font-bold">
            ARENA OVERVIEW
          </span>
        </div>
        <div className="grid grid-cols-4 gap-3">
          <StatCard
            icon={Users}
            label="AGENTS"
            value={alive.length}
            color="border-neon-green/30 text-neon-green"
            sub={`${allBots.length} total`}
          />
          <StatCard
            icon={DollarSign}
            label="TOTAL ECONOMY"
            value={`${totalEconomy.toFixed(0)}c`}
            color="border-neon-amber/30 text-neon-amber"
            sub={alive.length > 0 ? `${(totalEconomy / alive.length).toFixed(0)}c avg` : undefined}
          />
          <StatCard
            icon={Search}
            label="OPEN MARKETS"
            value={openMarkets.length}
            color="border-neon-cyan/30 text-neon-cyan"
            sub={`${openMarkets.filter((m) => m.source_type === 'RESEARCH').length} research`}
          />
          <StatCard
            icon={Skull}
            label="CASUALTIES"
            value={dead.length}
            color="border-alert-red/30 text-alert-red"
            sub={allBots.length > 0 ? `${((dead.length / allBots.length) * 100).toFixed(0)}% death rate` : undefined}
          />
        </div>
      </div>

      {/* Section: Agent Cards */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 bg-neon-green rounded-full animate-pulse" />
            <span className="text-[10px] text-neon-green uppercase tracking-[0.15em] font-bold">
              AGENT ROSTER
            </span>
          </div>
          <span className="text-[9px] text-zinc-700 uppercase">
            {alive.length} ALIVE | {dead.length} DEAD
          </span>
        </div>

        {sortedBots.length > 0 ? (
          <div className="grid grid-cols-3 gap-3">
            {sortedBots.map((bot) => (
              <AgentCard key={bot.id} bot={bot} now={now} />
            ))}
          </div>
        ) : (
          <div className="p-8 text-center text-[10px] text-zinc-600 uppercase tracking-widest border border-terminal-border">
            NO AGENTS IN THE ARENA — DEPLOY VIA THE GATE
          </div>
        )}
      </div>

      {/* Section: Market Snapshot */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Search size={12} className="text-neon-cyan" />
            <span className="text-[10px] text-neon-cyan uppercase tracking-[0.15em] font-bold">
              ACTIVE MARKETS
            </span>
          </div>
          {openMarkets.length > 3 && (
            <span className="text-[9px] text-zinc-600 uppercase flex items-center gap-1">
              {openMarkets.length} TOTAL
              <ArrowRight size={9} />
            </span>
          )}
        </div>

        {openMarkets.length > 0 ? (
          <div className="grid grid-cols-3 gap-3">
            {openMarkets.slice(0, 6).map((market) => (
              <MarketSnapshotCard key={market.id} market={market} now={now} />
            ))}
          </div>
        ) : (
          <div className="p-6 text-center text-[10px] text-zinc-600 uppercase tracking-widest border border-terminal-border">
            NO OPEN MARKETS — AWAITING EXTERNAL DATA
          </div>
        )}
      </div>
    </div>
  );
};

export default ArenaDashboard;
