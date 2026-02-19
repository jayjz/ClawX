import { useState, useEffect } from 'react';
import { useMarkets } from '../api/client';
import { Search, AlertTriangle, RefreshCw, Clock, Zap } from 'lucide-react';

const SOURCE_STYLES: Record<string, { color: string; border: string }> = {
  RESEARCH: { color: 'border-neon-cyan/30 text-neon-cyan', border: 'border-l-neon-cyan' },
  GITHUB:   { color: 'border-neon-green/30 text-neon-green', border: 'border-l-neon-green' },
  NEWS:     { color: 'border-neon-amber/30 text-neon-amber', border: 'border-l-neon-amber' },
  WEATHER:  { color: 'border-zinc-500/30 text-zinc-400', border: 'border-l-zinc-500' },
};

/** Format seconds into MM:SS */
const formatCountdown = (seconds: number): string => {
  if (seconds <= 0) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
};

const MarketBoard = () => {
  const { data: markets, isLoading, isError, error, refetch } = useMarkets();
  const [now, setNow] = useState(Date.now());

  // Tick countdown every second
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-terminal-border">
        <div className="flex items-center gap-2">
          <Search size={12} className="text-neon-cyan" />
          <span className="text-xs text-neon-cyan uppercase tracking-[0.15em] font-bold">
            MARKET BOARD // OPEN CONTRACTS
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[9px] text-zinc-700 uppercase">
            {markets?.length ?? 0} OPEN
          </span>
          <button
            onClick={() => void refetch()}
            className="text-zinc-700 hover:text-neon-cyan transition-colors"
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
              MARKETS OFFLINE: {error.message}
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
          &gt; SCANNING OPEN MARKETS...
        </div>
      )}

      {/* Market Table */}
      {markets && markets.length > 0 && (
        <div className="border border-terminal-border">
          {/* Table Header */}
          <div className="grid grid-cols-[90px_1fr_100px_130px] gap-2 px-4 py-2.5 border-b border-terminal-border bg-terminal-deep text-[10px] text-zinc-600 uppercase tracking-[0.15em]">
            <span>TYPE</span>
            <span>DESCRIPTION</span>
            <span className="text-right">BOUNTY</span>
            <span className="text-right">COUNTDOWN</span>
          </div>

          {/* Rows */}
          {markets.map((market) => {
            const style = SOURCE_STYLES[market.source_type] ?? { color: 'border-zinc-500/30 text-zinc-400', border: 'border-l-zinc-500' };
            const isResearch = market.source_type === 'RESEARCH';

            // Live countdown
            const deadlineMs = new Date(market.deadline).getTime();
            const secondsLeft = Math.max(0, (deadlineMs - now) / 1000);
            const isExpired = secondsLeft <= 0;
            const isUrgent = secondsLeft > 0 && secondsLeft < 60;
            const isWarning = secondsLeft > 0 && secondsLeft < 180;

            const countdownColor = isExpired
              ? 'text-zinc-600'
              : isUrgent
                ? 'text-alert-red'
                : isWarning
                  ? 'text-neon-amber'
                  : 'text-zinc-500';

            return (
              <div
                key={market.id}
                className={`grid grid-cols-[90px_1fr_100px_130px] gap-2 px-4 py-3 border-b border-terminal-border/50 border-l-4 ${style.border} text-sm font-mono transition-all hover:bg-terminal-surface ${
                  isExpired ? 'opacity-40' : ''
                } ${isResearch && !isExpired ? 'bg-neon-cyan/[0.02]' : ''}`}
                style={isResearch && !isExpired ? { boxShadow: '0 0 16px rgba(0,212,255,0.06)' } : undefined}
              >
                {/* Source Type Badge */}
                <span>
                  <span className={`text-[8px] px-1.5 py-0.5 border uppercase font-bold ${style.color}`}>
                    {market.source_type}
                  </span>
                </span>

                {/* Description */}
                <span className="text-zinc-300 text-xs truncate" title={market.description}>
                  {market.description}
                </span>

                {/* Bounty */}
                <span className="text-right flex items-center justify-end gap-1">
                  {isResearch && !isExpired && (
                    <Zap size={10} className="text-neon-cyan animate-pulse" />
                  )}
                  <span className={`font-bold ${isResearch ? 'text-neon-cyan glow-cyan' : 'text-neon-green'}`}>
                    {Number(market.bounty).toFixed(0)}c
                  </span>
                </span>

                {/* Countdown + Progress Bar */}
                <div className="flex flex-col items-end gap-1">
                  <span className={`text-xs flex items-center gap-1 ${countdownColor}`}>
                    {isExpired ? (
                      <span className="text-[9px] uppercase tracking-wider">EXPIRED</span>
                    ) : (
                      <>
                        <Clock size={10} className={isUrgent ? 'animate-pulse' : ''} />
                        <span className={`font-bold tabular-nums ${isUrgent ? 'animate-pulse' : ''}`}>
                          {formatCountdown(secondsLeft)}
                        </span>
                      </>
                    )}
                  </span>
                  {!isExpired && (
                    <div className="w-20 h-1 bg-terminal-black border border-terminal-border/50 overflow-hidden">
                      <div
                        className={`h-full transition-all duration-1000 ${
                          isUrgent ? 'bg-alert-red' : isWarning ? 'bg-neon-amber' : 'bg-neon-cyan'
                        }`}
                        style={{ width: `${Math.min((secondsLeft / 300) * 100, 100)}%` }}
                      />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Empty State */}
      {markets && markets.length === 0 && (
        <div className="p-8 text-center text-[10px] text-zinc-600 uppercase tracking-widest border border-terminal-border">
          NO OPEN MARKETS — AWAITING EXTERNAL DATA
        </div>
      )}
    </div>
  );
};

export default MarketBoard;
