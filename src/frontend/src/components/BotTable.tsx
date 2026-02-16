import { useBots } from '../api/client';
import { AlertTriangle, RefreshCw } from 'lucide-react';

const BotTable = () => {
  const { data: bots, isLoading, isError, error, refetch } = useBots();

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-terminal-border">
        <span className="text-[10px] text-neon-green uppercase tracking-[0.15em] font-bold">
          REGISTRY // ALL AGENTS
        </span>
        <div className="flex items-center gap-3">
          <span className="text-[9px] text-zinc-700 uppercase">
            POLL: 10s | {bots?.length ?? 0} REGISTERED
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
      {bots && bots.length > 0 && (
        <div className="border border-terminal-border">
          {/* Table Header */}
          <div className="grid grid-cols-[60px_1fr_120px_100px] gap-2 px-3 py-2.5 border-b border-terminal-border bg-terminal-deep text-[10px] text-zinc-600 uppercase tracking-[0.15em]">
            <span>ID</span>
            <span>HANDLE</span>
            <span className="text-right">BALANCE</span>
            <span className="text-right">STATUS</span>
          </div>

          {/* Rows */}
          {bots.map((bot) => {
            const isDead = bot.status === 'DEAD';
            return (
              <div
                key={bot.id}
                className={`grid grid-cols-[60px_1fr_120px_100px] gap-2 px-3 py-2.5 border-b border-terminal-border/50 text-xs font-mono transition-colors hover:bg-terminal-surface ${
                  isDead ? 'opacity-50' : ''
                }`}
              >
                <span className="text-zinc-600">#{bot.id}</span>
                <span className={isDead ? 'text-alert-red line-through' : 'text-zinc-300'}>
                  {bot.handle}
                </span>
                <span
                  className={`text-right ${
                    isDead
                      ? 'text-alert-red'
                      : bot.balance >= 1000
                        ? 'text-neon-green'
                        : bot.balance > 0
                          ? 'text-neon-amber'
                          : 'text-alert-red'
                  }`}
                >
                  {bot.balance.toFixed(2)}c
                </span>
                <span className="text-right">
                  <span
                    className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-[9px] font-bold uppercase ${
                      isDead
                        ? 'text-alert-red border border-alert-red/30'
                        : 'text-neon-green border border-neon-green/30'
                    }`}
                  >
                    <span
                      className={`w-1.5 h-1.5 rounded-full ${isDead ? 'bg-alert-red' : 'bg-neon-green'}`}
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
      {bots && bots.length === 0 && (
        <div className="p-8 text-center text-[10px] text-zinc-600 uppercase tracking-widest border border-terminal-border">
          NO AGENTS REGISTERED. USE THE GATE TO DEPLOY.
        </div>
      )}
    </div>
  );
};

export default BotTable;
