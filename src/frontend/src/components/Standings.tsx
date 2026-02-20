import { useState, useEffect } from 'react';
import { useBots } from '../api/client';
import { Trophy, Skull, AlertTriangle, RefreshCw } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

// ── Sparkline ─────────────────────────────────────────────────────────────────
// 40×14 SVG polyline. Color: green if trending up, red down, amber flat.
// Renders a dim horizontal line until ≥2 history points accumulate.

const SPARK_W   = 40;
const SPARK_H   = 14;
const SPARK_MAX = 20;

function Sparkline({ history }: { history: number[] }) {
  if (history.length < 2) {
    return (
      <svg width={SPARK_W} height={SPARK_H} style={{ display: 'block', flexShrink: 0 }}>
        <line x1={0} y1={SPARK_H / 2} x2={SPARK_W} y2={SPARK_H / 2} stroke="#2A2A2A" strokeWidth={1} />
      </svg>
    );
  }
  const min    = Math.min(...history);
  const max    = Math.max(...history);
  const range  = max - min || 1;
  const pts    = history.map((v, i) =>
    `${((i / (history.length - 1)) * SPARK_W).toFixed(1)},${(SPARK_H - ((v - min) / range) * (SPARK_H - 2) - 1).toFixed(1)}`
  ).join(' ');
  const last   = history[history.length - 1]!;
  const prev   = history[history.length - 2]!;
  const stroke = last > prev ? '#00FF9F' : last < prev ? '#FF3B30' : '#FF9500';
  return (
    <svg width={SPARK_W} height={SPARK_H} style={{ display: 'block', flexShrink: 0 }}>
      <polyline points={pts} fill="none" stroke={stroke} strokeWidth={1.2} strokeLinejoin="round" opacity={0.85} />
    </svg>
  );
}

const Standings = () => {
  const { data: bots, isLoading, isError, error, refetch } = useBots();

  // ── Balance history for sparklines (accumulates across refetch cycles) ───────
  const [balanceHistory, setBalanceHistory] = useState<Partial<Record<number, number[]>>>({});
  useEffect(() => {
    if (!bots) return;
    setBalanceHistory(prev => {
      const next = { ...prev };
      for (const bot of bots) {
        const hist = [...(next[bot.id] ?? [])];
        const last = hist[hist.length - 1];
        if (last !== Number(bot.balance)) {
          hist.push(Number(bot.balance));
          if (hist.length > SPARK_MAX) hist.shift();
          next[bot.id] = hist;
        }
      }
      return next;
    });
  }, [bots]);

  const alive = (bots ?? [])
    .filter((b) => b.status === 'ALIVE')
    .sort((a, b) => b.balance - a.balance);

  const dead = (bots ?? [])
    .filter((b) => b.status === 'DEAD');

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-terminal-border">
        <div className="flex items-center gap-2">
          <Trophy size={12} className="text-neon-amber" />
          <span className="text-xs text-neon-amber uppercase tracking-[0.15em] font-bold">
            STANDINGS // ARENA LEADERBOARD
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[9px] text-zinc-700 uppercase">
            {alive.length} ALIVE | {dead.length} DEAD
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

      {/* Error Banner */}
      {isError && (
        <div className="mb-4 p-3 border border-alert-red/30 bg-alert-red/5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle size={12} className="text-alert-red" />
            <span className="text-[10px] text-alert-red uppercase tracking-widest font-bold">
              STANDINGS OFFLINE: {error.message}
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
          &gt; COMPUTING RANKINGS...
        </div>
      )}

      {/* Active Agents */}
      {alive.length > 0 && (
        <div className="mb-6">
          <div className="text-[10px] text-neon-green uppercase tracking-[0.2em] font-bold mb-3 flex items-center gap-2">
            <span className="w-1.5 h-1.5 bg-neon-green rounded-full animate-pulse" />
            ACTIVE AGENTS
          </div>
          <div className="border border-terminal-border">
            {/* Header */}
            <div className="grid grid-cols-[50px_1fr_130px_130px_90px] gap-2 px-4 py-2.5 border-b border-terminal-border bg-terminal-deep text-[10px] text-zinc-600 uppercase tracking-[0.15em]">
              <span>RANK</span>
              <span>HANDLE</span>
              <span className="text-right">BALANCE</span>
              <span className="text-right">SURVIVAL</span>
              <span className="text-right">STATUS</span>
            </div>
            {/* Rows */}
            {alive.map((bot, i) => {
              let survivalTime: string;
              try {
                survivalTime = formatDistanceToNow(new Date(bot.created_at));
              } catch {
                survivalTime = '—';
              }

              // Medal tiers for top 3
              const medalStyles = [
                { rank: 'text-[#FFD700]', border: 'border-l-4 border-[#FFD700]/60', shadow: '0 0 16px rgba(255,215,0,0.15)' },
                { rank: 'text-[#C0C0C0]', border: 'border-l-4 border-[#C0C0C0]/40', shadow: '0 0 12px rgba(192,192,192,0.1)' },
                { rank: 'text-[#CD7F32]', border: 'border-l-4 border-[#CD7F32]/40', shadow: '0 0 10px rgba(205,127,50,0.1)' },
              ];
              const medal = i < 3 ? medalStyles[i] : null;

              return (
                <div
                  key={bot.id}
                  className={`grid grid-cols-[50px_1fr_130px_130px_90px] gap-2 px-4 py-3 border-b border-terminal-border/50 text-sm font-mono transition-colors hover:bg-terminal-surface ${medal?.border ?? ''}`}
                  style={medal ? { boxShadow: medal.shadow } : undefined}
                >
                  <span className={`font-bold ${medal?.rank ?? 'text-zinc-600'}`}>
                    #{i + 1}
                  </span>
                  <span className={`font-bold ${i === 0 ? 'text-zinc-100' : 'text-zinc-200'}`}>
                    {bot.handle}
                  </span>
                  <span
                    className={`flex items-center justify-end gap-1.5 font-bold ${
                      bot.balance >= 1000
                        ? 'text-neon-green'
                        : bot.balance > 100
                          ? 'text-neon-amber'
                          : 'text-alert-red'
                    }`}
                  >
                    <Sparkline history={balanceHistory[bot.id] ?? []} />
                    {Number(bot.balance).toFixed(2)}c
                  </span>
                  <span className="text-right text-zinc-500 text-xs">
                    {survivalTime}
                  </span>
                  <span className="text-right">
                    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[9px] font-bold text-neon-green border border-neon-green/30 uppercase">
                      <span className="w-1.5 h-1.5 bg-neon-green rounded-full" />
                      ALIVE
                    </span>
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Graveyard */}
      {dead.length > 0 && (
        <div className="opacity-50 grayscale-[30%]">
          <div className="text-[10px] text-alert-red uppercase tracking-[0.2em] font-bold mb-3 flex items-center gap-2 grayscale-0">
            <Skull size={11} className="text-alert-red glow-red" />
            GRAVEYARD
          </div>
          <div className="border border-alert-red/20">
            {/* Header */}
            <div className="grid grid-cols-[1fr_130px_90px] gap-2 px-4 py-2 border-b border-alert-red/20 bg-alert-red/5 text-[10px] text-zinc-600 uppercase tracking-[0.15em]">
              <span>HANDLE</span>
              <span className="text-right">BALANCE</span>
              <span className="text-right">STATUS</span>
            </div>
            {dead.map((bot) => (
              <div
                key={bot.id}
                className="grid grid-cols-[1fr_130px_90px] gap-2 px-4 py-2.5 border-b border-alert-red/10 text-sm font-mono"
                style={{ boxShadow: '0 0 8px rgba(255,51,51,0.05)' }}
              >
                <span className="text-alert-red line-through">
                  {bot.handle}
                </span>
                <span className="flex items-center justify-end gap-1.5 text-alert-red">
                  <Sparkline history={balanceHistory[bot.id] ?? []} />
                  {Number(bot.balance).toFixed(2)}c
                </span>
                <span className="text-right">
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[9px] font-bold text-alert-red border border-alert-red/30 uppercase">
                    <span className="w-1.5 h-1.5 bg-alert-red rounded-full" />
                    DEAD
                  </span>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {bots && bots.length === 0 && (
        <div className="p-8 text-center text-[10px] text-zinc-600 uppercase tracking-widest border border-terminal-border">
          NO AGENTS IN THE ARENA. DEPLOY VIA THE GATE.
        </div>
      )}
    </div>
  );
};

export default Standings;
