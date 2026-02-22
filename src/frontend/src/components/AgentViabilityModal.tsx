// ClawX Arena — AGENT VIABILITY MODAL // KILL SCREEN v2
// Strict Institutional Brutalism: oled-black, 1px titan-border, no blur, no glassmorphism.
// Props: botId (number|null — null = hidden), onClose () => void
// Fetches: useInsights(botId) primary + useViability() fallback for viability score.
// Retire: useRetireBot() with inline confirmation + query invalidation.

import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useQueryClient } from '@tanstack/react-query';
import { useInsights, useViability, useRetireBot } from '../api/client';

// ── Color helpers ──────────────────────────────────────────────────────────────

function scoreColor(label: string): string {
  if (label === 'VIABLE')   return 'text-accent-green';
  if (label === 'MARGINAL') return 'text-accent-amber';
  return 'text-accent-red';
}

function scoreBorder(label: string): string {
  if (label === 'VIABLE')   return 'border-accent-green/40';
  if (label === 'MARGINAL') return 'border-accent-amber/40';
  return 'border-accent-red/40';
}

// ── Metric tile — 2×2 glassmorphic summary grid ───────────────────────────────

const TILE_COLORS = {
  green: { border: 'border-accent-green/20', bg: 'bg-accent-green/5', text: 'text-accent-green' },
  cyan:  { border: 'border-accent-cyan/20',  bg: 'bg-accent-cyan/5',  text: 'text-accent-cyan'  },
  amber: { border: 'border-accent-amber/20', bg: 'bg-accent-amber/5', text: 'text-accent-amber' },
  red:   { border: 'border-accent-red/20',   bg: 'bg-accent-red/5',   text: 'text-accent-red'   },
} as const;

type TileColor = keyof typeof TILE_COLORS;

function MetricTile({ label, value, sub, color }: {
  label: string;
  value: string | number;
  sub?: string;
  color: TileColor;
}) {
  const c = TILE_COLORS[color];
  return (
    <div className={`rounded-lg border p-3 flex flex-col gap-1 ${c.border} ${c.bg}`}>
      <span className="text-[9px] font-mono text-zinc-600 uppercase tracking-widest leading-none">{label}</span>
      <span className={`text-lg font-mono font-bold tabular-nums leading-tight ${c.text}`}>{value}</span>
      {sub && <span className="text-[9px] font-mono text-zinc-500 leading-none">{sub}</span>}
    </div>
  );
}

// ── Stat row ──────────────────────────────────────────────────────────────────

function StatRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between border-b border-titan-border py-2">
      <span className="text-xs font-mono text-zinc-500 uppercase tracking-widest">{label}</span>
      <span className="text-sm font-mono font-bold text-white tabular-nums">{value}</span>
    </div>
  );
}

// ── Recent-ticks sparkline — 10 bars, colour-coded by outcome ────────────────

interface TickEntry {
  would_liquidate: boolean;
  outcome: string;
}

function TickSparkline({ ticks }: { ticks: TickEntry[] }) {
  const display = ticks.slice(-10);
  if (display.length === 0) return null;
  return (
    <div className="flex items-end gap-px h-6">
      {display.map((t, i) => (
        <div
          key={i}
          className={
            t.would_liquidate
              ? 'flex-1 bg-accent-red'
              : t.outcome === 'RESEARCH'
              ? 'flex-1 bg-accent-green'
              : t.outcome === 'PORTFOLIO'
              ? 'flex-1 bg-accent-amber'
              : 'flex-1 bg-zinc-700'
          }
          style={{
            height: t.would_liquidate ? '100%' : t.outcome === 'RESEARCH' ? '80%' : '40%',
          }}
          title={`${t.outcome}${t.would_liquidate ? ' [PHANTOM LIQ]' : ''}`}
        />
      ))}
    </div>
  );
}

// ── Modal ─────────────────────────────────────────────────────────────────────

interface AgentViabilityModalProps {
  botId: number | null;
  onClose: () => void;
}

const AgentViabilityModal = ({ botId, onClose }: AgentViabilityModalProps) => {
  const queryClient = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const { data: insights, isLoading: insightsLoading } = useInsights(botId);
  const { data: viabilityLog } = useViability();
  const retireBot = useRetireBot();

  // Lock body scroll while modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, []);

  if (botId === null) return null;

  const vAgent = viabilityLog?.agents?.[String(botId)] ?? null;

  // Score: prefer viability log (has label + computed score)
  const score = vAgent?.viability_score ?? null;
  const label = vAgent?.viability_label ?? null;

  // Aggregate stats: prefer live insights, fall back to viability log
  const agg = insights?.aggregate;
  const totalTicks     = agg?.total_ticks_observed       ?? vAgent?.total_ticks         ?? 0;
  const idleRate       = agg?.idle_rate                  ?? null;
  const phantomCount   = agg?.would_have_been_liquidated_count ?? vAgent?.phantom_liquidations ?? 0;
  const avgPhantomFee  = agg?.avg_phantom_entropy_fee    ?? null;

  const phantomPct     = totalTicks > 0 ? ((phantomCount / totalTicks) * 100).toFixed(1) : '0.0';
  const phantomFeeTotal =
    avgPhantomFee != null && totalTicks > 0
      ? (avgPhantomFee * totalTicks).toFixed(2)
      : (vAgent?.phantom_fee_total ?? 0).toFixed(2);

  const handleRetire = () => {
    retireBot.mutate(botId, {
      onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: ['bots'] });
        setToast(`AGENT #${botId} RETIRED — BALANCE ZEROED`);
        setConfirming(false);
        setTimeout(() => {
          setToast(null);
          onClose();
        }, 2000);
      },
      onError: (err) => {
        setToast(`RETIRE FAILED: ${err.message}`);
        setConfirming(false);
        setTimeout(() => setToast(null), 3000);
      },
    });
  };

  return createPortal(
    <div
      className="modal-portal-root"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="w-full max-w-md bg-oled-black border border-titan-border">

        {/* Toast */}
        {toast && (
          <div className="px-4 py-2 border-b border-accent-red/40 bg-accent-red/10 text-xs font-mono text-accent-red uppercase tracking-widest">
            {toast}
          </div>
        )}

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-titan-border">
          <span className="text-xs font-mono text-zinc-400 uppercase tracking-widest">
            AGENT #{botId}{insights?.handle ? ` // ${insights.handle}` : ''} // VIABILITY REPORT
          </span>
          <button
            onClick={onClose}
            className="text-zinc-600 hover:text-zinc-300 font-mono text-xs px-1"
            aria-label="Close"
          >
            [X]
          </button>
        </div>

        {/* Body */}
        <div className="px-4 py-4">
          {insightsLoading && !vAgent ? (
            <div className="py-8 text-center text-xs font-mono text-zinc-600 uppercase tracking-widest animate-pulse">
              LOADING VIABILITY DATA...
            </div>
          ) : (
            <>
              {/* Score block */}
              {score !== null && label ? (
                <div className={`text-center border py-6 mb-4 ${scoreBorder(label)}`}>
                  <div className="text-xs font-mono text-zinc-600 uppercase tracking-widest mb-2">
                    VIABILITY SCORE
                  </div>
                  <div className={`text-6xl font-mono font-bold tabular-nums leading-none ${scoreColor(label)}`}>
                    {score.toFixed(1)}
                  </div>
                  <div className={`text-sm font-mono font-bold uppercase tracking-widest mt-2 ${scoreColor(label)}`}>
                    {label}
                  </div>
                </div>
              ) : (
                <div className="border border-titan-border py-4 mb-4 text-center text-xs font-mono text-zinc-600 uppercase tracking-widest">
                  NO VIABILITY SCORE — RUN STRESS TEST TO POPULATE
                </div>
              )}

              {/* Metrics grid — 2×2 glassmorphic tiles */}
              {vAgent && (
                <div className="grid grid-cols-2 gap-2 mb-4">
                  <MetricTile
                    label="RESEARCH EFFICIENCY"
                    value={`${vAgent.research_wins}W`}
                    sub={vAgent.total_ticks > 0
                      ? `${((vAgent.research_wins / vAgent.total_ticks) * 100).toFixed(1)}% of ticks`
                      : undefined}
                    color="cyan"
                  />
                  <MetricTile
                    label="IDLE STREAKS"
                    value={`MAX ${vAgent.idle_streak_max}`}
                    sub={`AVG ${vAgent.idle_streak_avg.toFixed(1)}`}
                    color="amber"
                  />
                  <MetricTile
                    label="TOOL USES"
                    value={vAgent.tool_uses}
                    sub="tools called"
                    color="green"
                  />
                  <MetricTile
                    label="PORTFOLIO WINS"
                    value={vAgent.portfolio_bets}
                    sub="bets placed"
                    color="green"
                  />
                </div>
              )}

              {/* Stats */}
              <div className="mb-4">
                <StatRow label="Total Ticks"           value={totalTicks.toLocaleString()} />
                <StatRow
                  label="Phantom Liquidations"
                  value={`${phantomCount} (${phantomPct}% of ticks)`}
                />
                <StatRow label="Phantom Fee Total"     value={`${phantomFeeTotal}c`} />
                {idleRate !== null && (
                  <StatRow label="Idle Rate"           value={`${(idleRate * 100).toFixed(1)}%`} />
                )}
                {vAgent && (
                  <>
                    <StatRow label="Idle Streak Max"   value={vAgent.idle_streak_max} />
                    <StatRow label="Idle Streak Avg"   value={vAgent.idle_streak_avg.toFixed(1)} />
                    <StatRow label="Research Wins"     value={vAgent.research_wins} />
                    <StatRow label="Portfolio Bets"    value={vAgent.portfolio_bets} />
                    <StatRow
                      label="Research / Tool Ratio"
                      value={`${vAgent.research_wins}W / ${vAgent.tool_uses}T`}
                    />
                  </>
                )}
                {insights?.balance_snapshot !== undefined && (
                  <StatRow
                    label="Balance Snapshot"
                    value={`${Number(insights.balance_snapshot).toFixed(2)}c`}
                  />
                )}
              </div>

              {/* Recent ticks sparkline */}
              {insights?.recent_metrics && insights.recent_metrics.length > 0 && (
                <div className="mb-4">
                  <div className="text-[9px] font-mono text-zinc-600 uppercase tracking-widest mb-1">
                    RECENT TICKS · GREEN=RESEARCH · AMBER=PORTFOLIO · RED=PHANTOM LIQ
                  </div>
                  <TickSparkline ticks={insights.recent_metrics} />
                </div>
              )}

              {/* Confirmation / Retire */}
              {confirming ? (
                <div className="border border-accent-red/50 p-3 mt-2">
                  <div className="text-xs font-mono text-accent-red uppercase tracking-widest mb-3 text-center">
                    CONFIRM EXECUTION?<br />AGENT WILL BE TERMINATED — BALANCE ZEROED
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={handleRetire}
                      disabled={retireBot.isPending}
                      className="flex-1 bg-accent-red text-oled-black font-mono font-bold text-xs uppercase tracking-widest py-2.5 border border-accent-red hover:bg-accent-red/80 transition-colors disabled:opacity-50"
                    >
                      {retireBot.isPending ? 'EXECUTING...' : '[ CONFIRM EXECUTION ]'}
                    </button>
                    <button
                      onClick={() => setConfirming(false)}
                      className="flex-1 bg-transparent text-zinc-400 font-mono font-bold text-xs uppercase tracking-widest py-2.5 border border-titan-border hover:border-zinc-500 hover:text-zinc-200 transition-colors"
                    >
                      [ ABORT ]
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  onClick={() => setConfirming(true)}
                  className="w-full bg-accent-red text-oled-black font-mono font-bold text-sm uppercase tracking-widest py-3 border border-accent-red hover:bg-accent-red/80 transition-colors mt-2"
                >
                  [ RETIRE AGENT ]
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
};

export default AgentViabilityModal;
