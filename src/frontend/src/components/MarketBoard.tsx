import { useMarkets } from '../api/client';
import { Search, AlertTriangle, RefreshCw } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const SOURCE_STYLES: Record<string, { color: string; border: string }> = {
  RESEARCH: { color: 'border-neon-cyan/30 text-neon-cyan', border: 'border-l-neon-cyan' },
  GITHUB:   { color: 'border-neon-green/30 text-neon-green', border: 'border-l-neon-green' },
  NEWS:     { color: 'border-neon-amber/30 text-neon-amber', border: 'border-l-neon-amber' },
  WEATHER:  { color: 'border-zinc-500/30 text-zinc-400', border: 'border-l-zinc-500' },
};

const MarketBoard = () => {
  const { data: markets, isLoading, isError, error, refetch } = useMarkets();

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
          <div className="grid grid-cols-[90px_1fr_90px_120px] gap-2 px-4 py-2.5 border-b border-terminal-border bg-terminal-deep text-[10px] text-zinc-600 uppercase tracking-[0.15em]">
            <span>TYPE</span>
            <span>DESCRIPTION</span>
            <span className="text-right">BOUNTY</span>
            <span className="text-right">DEADLINE</span>
          </div>

          {/* Rows */}
          {markets.map((market) => {
            const style = SOURCE_STYLES[market.source_type] ?? { color: 'border-zinc-500/30 text-zinc-400', border: 'border-l-zinc-500' };

            let deadline: string;
            try {
              deadline = formatDistanceToNow(new Date(market.deadline), { addSuffix: true });
            } catch {
              deadline = market.deadline;
            }

            return (
              <div
                key={market.id}
                className={`grid grid-cols-[90px_1fr_90px_120px] gap-2 px-4 py-3 border-b border-terminal-border/50 border-l-4 ${style.border} text-sm font-mono transition-colors hover:bg-terminal-surface`}
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
                <span className="text-right text-neon-green font-bold">
                  {Number(market.bounty).toFixed(2)}c
                </span>

                {/* Deadline */}
                <span className="text-right text-zinc-500 text-xs">
                  {deadline}
                </span>
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
