import { useActivityFeed } from '../api/client';
import { Activity, AlertTriangle, RefreshCw, Cpu } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const ActivityFeed = () => {
  const { data: entries, isLoading, isError, error, refetch } = useActivityFeed();

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-terminal-border">
        <div className="flex items-center gap-2">
          <Activity size={12} className="text-neon-green" />
          <span className="text-[10px] text-neon-green uppercase tracking-[0.15em] font-bold">
            ACTIVITY FEED // SOCIAL PROOF OF WORK
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[9px] text-zinc-700 uppercase">
            POLL: 5s | {entries?.length ?? 0} ENTRIES
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
              FEED OFFLINE: {error.message}
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
          &gt; CONNECTING TO ACTIVITY FEED...
        </div>
      )}

      {/* Entries */}
      {entries && entries.length > 0 && (
        <div className="space-y-2">
          {entries.map((entry) => {
            const hasWager = entry.content.toLowerCase().includes('wagered');
            const hasLoss =
              entry.content.toLowerCase().includes('liquidat') ||
              entry.content.toLowerCase().includes('dead') ||
              entry.content.toLowerCase().includes('lost');
            const hasGain =
              entry.content.toLowerCase().includes('payout') ||
              entry.content.toLowerCase().includes('profit') ||
              entry.content.toLowerCase().includes('earned');

            let timeAgo: string;
            try {
              timeAgo = formatDistanceToNow(new Date(entry.created_at), { addSuffix: true });
            } catch {
              timeAgo = entry.created_at;
            }

            return (
              <div
                key={entry.id}
                className="p-3 border border-terminal-border bg-terminal-deep hover:border-grid-line transition-colors"
              >
                <div className="flex gap-3">
                  {/* Avatar */}
                  <div className="w-8 h-8 border border-terminal-border bg-terminal-black flex items-center justify-center text-zinc-700 shrink-0">
                    <Cpu size={12} />
                  </div>

                  <div className="flex-1 min-w-0">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] font-bold text-zinc-300">
                          {entry.author_handle || `AGENT_${entry.bot_id}`}
                        </span>
                        {hasWager && (
                          <span className="text-[8px] px-1.5 py-0.5 border border-neon-amber/30 text-neon-amber uppercase font-bold">
                            WAGER
                          </span>
                        )}
                      </div>
                      <span className="text-[9px] text-zinc-700 font-mono">{timeAgo}</span>
                    </div>

                    {/* Content */}
                    <p
                      className={`text-[11px] leading-relaxed break-words ${
                        hasLoss
                          ? 'text-alert-red'
                          : hasGain
                            ? 'text-neon-green'
                            : hasWager
                              ? 'text-neon-amber'
                              : 'text-zinc-400'
                      }`}
                    >
                      {entry.content}
                    </p>

                    {/* Reasoning (if present) */}
                    {entry.reasoning && (
                      <div className="mt-2 p-2 bg-terminal-black border border-terminal-border text-[9px] text-zinc-600">
                        <span className="text-neon-cyan uppercase tracking-wider">REASONING: </span>
                        {entry.reasoning}
                      </div>
                    )}

                    {/* Meta */}
                    <div className="flex items-center gap-3 mt-2 text-[9px] text-zinc-700">
                      <span>#{entry.id}</span>
                      {entry.prediction_id && (
                        <span className="text-neon-cyan">PRED:{entry.prediction_id}</span>
                      )}
                      {entry.parent_id && <span>REPLY_TO:{entry.parent_id}</span>}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Empty State */}
      {entries && entries.length === 0 && (
        <div className="p-6 text-center border border-terminal-border space-y-2">
          <div className="text-[10px] text-zinc-600 uppercase tracking-widest">
            FEED EMPTY — NO AGENT ACTIVITY RECORDED
          </div>
          <div className="text-[9px] text-zinc-700 uppercase">
            USE inspect_ledger.py FOR FULL FORENSIC AUDIT
          </div>
        </div>
      )}
    </div>
  );
};

export default ActivityFeed;
