import { useRef, useEffect, useState } from 'react';
import { useActivityFeed } from '../api/client';
import { Activity, AlertTriangle, RefreshCw, Cpu, Skull, TrendingUp, Zap, Search, ChevronDown } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

const ActivityFeed = () => {
  const { data: entries, isLoading, isError, error, refetch } = useActivityFeed();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const [hasNew, setHasNew] = useState(false);
  const prevCountRef = useRef(0);

  // Auto-scroll when new entries arrive (if user is near bottom)
  useEffect(() => {
    const count = entries?.length ?? 0;
    if (count > prevCountRef.current) {
      if (autoScroll && scrollRef.current) {
        scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      } else if (!autoScroll) {
        setHasNew(true);
      }
    }
    prevCountRef.current = count;
  }, [entries?.length, autoScroll]);

  // Detect scroll position to toggle auto-scroll
  const handleScroll = () => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    const nearBottom = scrollHeight - scrollTop - clientHeight < 100;
    setAutoScroll(nearBottom);
    if (nearBottom) setHasNew(false);
  };

  const jumpToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      setAutoScroll(true);
      setHasNew(false);
    }
  };

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 220px)' }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4 pb-3 border-b border-terminal-border shrink-0">
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
        <div className="mb-4 p-3 border border-alert-red/30 bg-alert-red/5 flex items-center justify-between shrink-0">
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

      {/* Scrollable Feed Container */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto space-y-4 relative"
      >
        {entries && entries.length > 0 && (
          <>
            {entries.map((entry) => {
              const content = entry.content.toLowerCase();
              const hasWager = content.includes('wagered');
              const hasLoss =
                content.includes('liquidat') ||
                content.includes('dead') ||
                content.includes('eliminated');
              const hasGain =
                content.includes('payout') ||
                content.includes('profit') ||
                content.includes('earned') ||
                content.includes('bounty claimed');
              const hasError = content.includes('error');
              const hasResearch = content.includes('research');
              const hasTool = content.includes('[tool]');
              const hasMarketBet = content.includes('market bet');
              const hasResearchWin = hasResearch && hasGain;

              let timeAgo: string;
              try {
                timeAgo = formatDistanceToNow(new Date(entry.created_at), { addSuffix: true });
              } catch {
                timeAgo = entry.created_at;
              }

              // Badge priority: DEATH > ERROR > KNOWLEDGE VERIFIED > RESEARCH > WAGER > MARKET > PAYOUT
              let badge: { text: string; color: string; glitch?: boolean } | null = null;
              if (hasLoss) badge = { text: 'DEATH', color: 'border-alert-red/30 text-alert-red' };
              else if (hasError) badge = { text: 'ERROR', color: 'border-alert-red/30 text-alert-red' };
              else if (hasResearchWin) badge = { text: 'KNOWLEDGE VERIFIED', color: 'border-neon-cyan/40 text-neon-cyan', glitch: true };
              else if (hasResearch) badge = { text: 'RESEARCH', color: 'border-neon-cyan/30 text-neon-cyan', glitch: true };
              else if (hasWager) badge = { text: 'WAGER', color: 'border-neon-amber/30 text-neon-amber' };
              else if (hasMarketBet) badge = { text: 'MARKET', color: 'border-neon-amber/30 text-neon-amber' };
              else if (hasGain) badge = { text: 'PAYOUT', color: 'border-neon-green/30 text-neon-green' };

              const EntryIcon = hasLoss ? Skull : hasResearch ? Search : hasGain ? TrendingUp : hasError ? Zap : Cpu;

              const contentColor = hasLoss
                ? 'text-alert-red'
                : hasResearchWin
                  ? 'text-neon-cyan'
                  : hasResearch
                    ? 'text-neon-cyan'
                    : hasGain
                      ? 'text-neon-green'
                      : hasWager || hasMarketBet
                        ? 'text-neon-amber'
                        : 'text-zinc-400';

              const borderClass = hasLoss
                ? 'border-l-4 border-l-alert-red animate-death-pulse'
                : hasResearchWin
                  ? 'border-l-4 border-l-neon-cyan bg-neon-cyan/[0.04]'
                  : hasResearch
                    ? 'border-l-4 border-l-neon-cyan bg-neon-cyan/[0.02]'
                    : hasGain
                      ? 'border-l-4 border-l-neon-green'
                      : '';

              const glowStyle = hasLoss
                ? { boxShadow: '0 0 20px rgba(255,51,51,0.15)' }
                : hasResearchWin
                  ? { boxShadow: '0 0 20px rgba(0,212,255,0.15)' }
                  : hasResearch
                    ? { boxShadow: '0 0 12px rgba(0,212,255,0.08)' }
                    : hasGain
                      ? { boxShadow: '0 0 12px rgba(0,255,65,0.1)' }
                      : undefined;

              return (
                <div
                  key={entry.id}
                  className={`p-3 border border-terminal-border bg-terminal-deep hover:border-grid-line transition-colors animate-fadeIn ${borderClass}`}
                  style={glowStyle}
                >
                  <div className="flex gap-3">
                    {/* Icon */}
                    <div
                      className={`w-8 h-8 border flex items-center justify-center shrink-0 ${
                        hasLoss
                          ? 'border-alert-red/40 bg-alert-red/10 text-alert-red'
                          : hasResearch
                            ? 'border-neon-cyan/30 bg-neon-cyan/5 text-neon-cyan'
                            : hasGain
                              ? 'border-neon-green/30 bg-neon-green/5 text-neon-green'
                              : 'border-terminal-border bg-terminal-black text-zinc-700'
                      } ${hasLoss ? 'animate-pulse' : ''}`}
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
                            <span
                              className={`text-[8px] px-1.5 py-0.5 border uppercase font-bold ${badge.color} ${
                                badge.glitch ? 'animate-glitch glow-cyan' : ''
                              } ${hasLoss ? 'glow-red animate-pulse' : ''}`}
                            >
                              {badge.text}
                            </span>
                          )}
                          {hasTool && (
                            <span className="text-[8px] px-1.5 py-0.5 border border-neon-amber/40 text-neon-amber uppercase font-bold animate-pulse glow-amber">
                              TOOL
                            </span>
                          )}
                        </div>
                        <span className="text-[9px] text-zinc-700 font-mono">{timeAgo}</span>
                      </div>

                      {/* Content */}
                      <p className={`text-sm leading-relaxed break-words ${contentColor}`}>
                        {entry.content}
                      </p>

                      {/* Reasoning */}
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
          </>
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

      {/* "New Activity" jump button — shown when user has scrolled up */}
      {hasNew && (
        <button
          onClick={jumpToBottom}
          className="absolute bottom-20 left-1/2 -translate-x-1/2 z-10 flex items-center gap-1 px-3 py-1.5 bg-terminal-black border border-neon-green/40 text-neon-green text-[9px] uppercase tracking-wider font-bold hover:bg-neon-green/10 transition-colors animate-pulse"
        >
          <ChevronDown size={10} />
          NEW ACTIVITY
        </button>
      )}
    </div>
  );
};

export default ActivityFeed;
