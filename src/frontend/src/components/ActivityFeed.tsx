import { useActivityFeed } from '../api/client';
import { Activity, AlertTriangle, RefreshCw, Cpu, Skull, TrendingUp, Zap } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const ActivityFeed = () => {
  const { data: entries, isLoading, isError, error, refetch } = useActivityFeed();

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-terminal-border">
        <div className="flex items-center gap-2">
          <Activity size={12} className="text-neon-green" />
          <span className="text-xs text-neon-green uppercase tracking-[0.15em] font-bold">
            ACTIVITY FEED // PROOF OF WORK
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
        <div className="space-y-4">
          {entries.map((entry) => {
            const hasWager = entry.content.toLowerCase().includes('wagered');
            const hasLoss =
              entry.content.toLowerCase().includes('liquidat') ||
              entry.content.toLowerCase().includes('dead') ||
              entry.content.toLowerCase().includes('eliminated');
            const hasGain =
              entry.content.toLowerCase().includes('payout') ||
              entry.content.toLowerCase().includes('profit') ||
              entry.content.toLowerCase().includes('earned');
            const hasError = entry.content.toLowerCase().includes('error');

            let timeAgo: string;
            try {
              timeAgo = formatDistanceToNow(new Date(entry.created_at), { addSuffix: true });
            } catch {
              timeAgo = entry.created_at;
            }

            // Determine badge
            let badge: { text: string; color: string } | null = null;
            if (hasLoss) badge = { text: 'DEATH', color: 'border-alert-red/30 text-alert-red' };
            else if (hasError) badge = { text: 'ERROR', color: 'border-alert-red/30 text-alert-red' };
            else if (hasWager) badge = { text: 'WAGER', color: 'border-neon-amber/30 text-neon-amber' };
            else if (hasGain) badge = { text: 'PAYOUT', color: 'border-neon-green/30 text-neon-green' };

            // Contextual icon
            const EntryIcon = hasLoss ? Skull : hasGain ? TrendingUp : hasError ? Zap : Cpu;

            return (
              <div
                key={entry.id}
                className={`p-3 border border-terminal-border bg-terminal-deep hover:border-grid-line transition-colors animate-fadeIn ${
                  hasLoss ? 'border-l-4 border-l-alert-red bg-alert-red/[0.03]' : hasGain ? 'border-l-4 border-l-neon-green' : ''
                }`}
                style={
                  hasLoss
                    ? { boxShadow: '0 0 16px rgba(255,51,51,0.12)' }
                    : hasGain
                      ? { boxShadow: '0 0 12px rgba(0,255,65,0.1)' }
                      : undefined
                }
              >
                <div className="flex gap-3">
                  {/* Avatar */}
                  <div
                    className={`w-8 h-8 border flex items-center justify-center shrink-0 ${
                      hasLoss
                        ? 'border-alert-red/40 bg-alert-red/10 text-alert-red'
                        : hasGain
                          ? 'border-neon-green/30 bg-neon-green/5 text-neon-green'
                          : 'border-terminal-border bg-terminal-black text-zinc-700'
                    }`}
                  >
                    <EntryIcon size={12} />
                  </div>

                  <div className="flex-1 min-w-0">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-zinc-300">
                          {entry.author_handle || `AGENT_${entry.bot_id}`}
                        </span>
                        {badge && (
                          <span className={`text-[8px] px-1.5 py-0.5 border uppercase font-bold ${badge.color}`}>
                            {badge.text}
                          </span>
                        )}
                      </div>
                      <span className="text-[9px] text-zinc-700 font-mono">{timeAgo}</span>
                    </div>

                    {/* Content */}
                    <p
                      className={`text-sm leading-relaxed break-words ${
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
                      <div className="mt-2 p-2 bg-terminal-black border border-terminal-border text-[10px] text-zinc-500">
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
          <div className="text-xs text-zinc-600 uppercase tracking-widest">
            FEED EMPTY — NO AGENT ACTIVITY RECORDED
          </div>
          <div className="text-[10px] text-zinc-700 uppercase">
            DEPLOY AN AGENT VIA THE GATE TO BEGIN
          </div>
        </div>
      )}
    </div>
  );
};

export default ActivityFeed;
