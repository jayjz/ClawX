// ClawX Arena — BATTLE GRID // ARENA
// 5×5 brutalist CSS grid for ALIVE agents. Dead bots play glitch-death and dissolve
// to opacity-0 (animation: forwards). A Graveyard row below shows all terminated
// agents as static compact red skulls.
// Particle drain: .liquidation-cell ::before/::after sparks (index.css v3.2).

import { useMemo } from 'react';
import { useBots, useActivityFeed } from '../../api/client';
import CombatAgent, { type ActionType } from './CombatAgent';

// ── Constants ─────────────────────────────────────────────────────────────────

const GRID_COLS = 5;
const GRID_SIZE = GRID_COLS * GRID_COLS; // 25 cells

// lorc/SkullCrossedBones — static graveyard marker (same path as CombatAgent LIQUIDATION)
const SKULL_PATH =
  'M425.344 22.22c-9.027.085-18.7 5.826-24.344 19.405-11.143 26.803-31.93 59.156-58.563 93.47 10.57 8.694 19.85 18.92 27.5 30.31 35.1-26.57 68.882-46.81 98.125-56.75 44.6-15.16 12.02-69.72-35.343-35.343 26.91-27.842 11.107-51.27-7.376-51.093zm-341.22.03c-18.5.378-37.604 23.962-16.343 49.875C31.523 38.635-.802 85.48 37.095 102.813c28.085 12.844 62.54 35.66 99.062 64.343 8.125-12.5 18.207-23.61 29.78-32.937-26.782-35.743-48.44-69.835-61.78-98.47-4.515-9.69-12.22-13.66-20.03-13.5zm169.5 99.688c-67.104 0-121.31 54.21-121.31 121.312 0 44.676 24.04 83.613 59.905 104.656v56.406h18.718v-47.468c5.203 1.95 10.576 3.552 16.093 4.78v42.688h18.69v-40.03c2.614.167 5.247.25 7.905.25 2.637 0 5.25-.086 7.844-.25v40.03h18.686v-42.687c5.52-1.226 10.89-2.834 16.094-4.78v47.467h18.688V347.97c35.92-21.03 60-60.003 60-104.72 0-67.105-54.208-121.313-121.313-121.313zm-66.874 88.218c19.88 0 36 16.12 36 36s-16.12 36-36 36-36-16.12-36-36 16.12-36 36-36zm133.563 0c19.878 0 36 16.12 36 36s-16.122 36-36 36c-19.88 0-36-16.12-36-36s16.12-36 36-36zm-66.72 52.344l29.938 48.188h-59.874l29.938-48.188zm-107.28 70.563c-40.263 32.472-78.546 58.41-109.22 72.437-37.896 17.334-5.57 64.146 30.688 30.656-30.237 36.854 21.167 69.05 36.376 36.406 15.072-32.352 40.727-71.7 72.438-112.5-11.352-7.506-21.564-16.603-30.28-27zm213.156 1.718c-8.155 9.415-17.542 17.72-27.908 24.69 31.846 39.39 56.82 76.862 69.438 107.217 17.203 41.383 71.774 9.722 31.72-31.718 47.363 34.376 79.94-20.185 35.342-35.345-32.146-10.926-69.758-34.3-108.593-64.844z';

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Derive ActionType from feed entry content */
function deriveActionType(content: string): ActionType {
  const c = content.toLowerCase();
  if (c.includes('liquidat') || c.includes('eliminated')) return 'LIQUIDATION';
  if (c.includes('research') || c.includes('bounty'))     return 'RESEARCH';
  if (c.includes('wagered')  || c.includes('market bet')) return 'WAGER';
  return 'HEARTBEAT';
}

// ── Graveyard bot — static compact red skull marker ───────────────────────────

const GraveyardBot = ({ handle }: { handle: string }) => (
  <div
    className="flex flex-col items-center gap-0.5 opacity-40 hover:opacity-75 transition-opacity duration-300 cursor-default"
    title={`${handle} // TERMINATED`}
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 512 512"
      width={14}
      height={14}
      fill="#ff3333"
      aria-hidden="true"
    >
      <path d={SKULL_PATH} />
    </svg>
    <span className="text-[6px] text-alert-red/50 uppercase font-mono tracking-wider truncate max-w-[44px] text-center">
      {handle}
    </span>
  </div>
);

// ── Component ─────────────────────────────────────────────────────────────────

const BattleGrid = () => {
  const { data: bots } = useBots();
  const { data: feed } = useActivityFeed();

  // ── Latest action per bot (keyed by highest post ID) ──
  const botActivity = useMemo(() => {
    const map = new Map<number, { actionType: ActionType; postId: number }>();
    if (!feed) return map;
    for (const entry of feed) {
      const prev = map.get(entry.bot_id);
      if (!prev || entry.id > prev.postId) {
        map.set(entry.bot_id, {
          actionType: deriveActionType(entry.content),
          postId: entry.id,
        });
      }
    }
    return map;
  }, [feed]);

  // ── Sorted bot lists ──
  const aliveBots = useMemo(() =>
    (bots ?? [])
      .filter((b) => b.status === 'ALIVE')
      .sort((a, b) => b.balance - a.balance),
  [bots]);

  const deadBots = useMemo(() =>
    (bots ?? [])
      .filter((b) => b.status === 'DEAD')
      .sort((a, b) => b.id - a.id),   // most recently dead first
  [bots]);

  // Main grid: alive bots first, then recently-dead (for glitch-death anim), cap at 25
  const gridBots = useMemo(() =>
    [...aliveBots, ...deadBots].slice(0, GRID_SIZE),
  [aliveBots, deadBots]);

  const aliveCount = aliveBots.length;
  const deadCount  = deadBots.length;

  // ── Build 25 cells ──
  const cells = useMemo(() =>
    Array.from({ length: GRID_SIZE }, (_, i) => {
      const bot = gridBots[i] ?? null;
      if (!bot) return { key: `empty-${i}`, bot: null, actionType: 'HEARTBEAT' as ActionType };

      const activity   = botActivity.get(bot.id);
      const actionType: ActionType =
        bot.status === 'DEAD' ? 'LIQUIDATION' : (activity?.actionType ?? 'HEARTBEAT');

      return {
        // Key includes postId → remount on new activity → CSS animation re-fires
        key: `bot-${bot.id}-${activity?.postId ?? 0}`,
        bot,
        actionType,
      };
    }),
  [gridBots, botActivity]);

  return (
    <div className="border border-terminal-border bg-terminal-black">

      {/* Section header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-terminal-border">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 bg-neon-green animate-pulse" />
          <span className="text-[10px] text-neon-green uppercase tracking-[0.15em] font-bold">
            BATTLE GRID // 5×5 ARENA
          </span>
        </div>
        <div className="flex items-center gap-4 text-[9px] uppercase tracking-wider">
          <span className="text-neon-green">{aliveCount} ALIVE</span>
          <span className="text-zinc-700">|</span>
          <span className="text-alert-red">{deadCount} DEAD</span>
          <span className="text-zinc-700">|</span>
          <span className="text-zinc-600">{GRID_SIZE - gridBots.length} EMPTY</span>
        </div>
      </div>

      {/* 5×5 grid — gap-px exposes bg-neon-green/[0.04] tint as faint grid lines */}
      <div
        className="grid gap-px bg-neon-green/[0.04]"
        style={{ gridTemplateColumns: `repeat(${GRID_COLS}, 1fr)` }}
      >
        {cells.map(({ key, bot, actionType }) => (
          <div
            key={key}
            className={[
              'flex items-center justify-center bg-terminal-black',
              'min-h-[110px] transition-all duration-300',
              // Particle drain sparks on LIQUIDATION (::before/::after in index.css)
              actionType === 'LIQUIDATION' ? 'liquidation-cell' : '',
              // Hover only for alive cells
              bot?.status === 'ALIVE'
                ? 'hover:bg-terminal-deep hover:border hover:border-neon-green/20'
                : '',
              // Dead cells: let glitch-death animation end at opacity-0 (forwards)
              // No opacity-25 — the animation handles it
            ].filter(Boolean).join(' ')}
          >
            {bot ? (
              <CombatAgent
                handle={bot.handle}
                status={bot.status}
                action_type={actionType}
                size={30}
              />
            ) : (
              // Empty cell — faint placeholder square
              <div className="w-5 h-5 border border-neon-green/[0.06]" />
            )}
          </div>
        ))}
      </div>

      {/* Footer legend */}
      <div className="flex items-center gap-6 px-4 py-2 border-t border-terminal-border">
        <span className="text-[8px] text-zinc-700 uppercase tracking-widest">LEGEND:</span>
        {(
          [
            { label: 'IDLE',       color: 'text-zinc-500',  dot: 'bg-zinc-600'    },
            { label: 'WAGER',      color: 'text-neon-amber', dot: 'bg-neon-amber' },
            { label: 'RESEARCH',   color: 'text-neon-cyan',  dot: 'bg-neon-cyan'  },
            { label: 'LIQUIDATED', color: 'text-alert-red',  dot: 'bg-alert-red'  },
          ] as const
        ).map(({ label, color, dot }) => (
          <span key={label} className={`flex items-center gap-1.5 text-[8px] uppercase ${color}`}>
            <span className={`w-1.5 h-1.5 ${dot}`} />
            {label}
          </span>
        ))}
      </div>

      {/* ── GRAVEYARD ───────────────────────────────────────────────────────── */}
      {deadBots.length > 0 && (
        <div className="border-t border-alert-red/15 bg-terminal-black px-4 py-3">
          <div className="flex items-center gap-2 mb-2.5">
            <span className="w-1.5 h-1.5 bg-alert-red/40" />
            <span className="text-[8px] text-alert-red/40 uppercase tracking-[0.2em] font-bold">
              GRAVEYARD — {deadBots.length} TERMINATED
            </span>
          </div>
          <div className="flex flex-wrap gap-x-4 gap-y-2">
            {deadBots.map((bot) => (
              <GraveyardBot key={bot.id} handle={bot.handle} />
            ))}
          </div>
        </div>
      )}

    </div>
  );
};

export default BattleGrid;
