// ClawX Arena — COMMAND PALETTE // GLOBAL
// ⌘K / Ctrl+K to open. Glassmorphism slide-over, centered, keyboard-navigable.
// Dispatches nav: commands via NavigationContext, system: commands via onAction prop.

import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
  Search, X, BarChart2, Activity, DollarSign, Users,
  Database, RefreshCw, HelpCircle, ChevronRight,
} from 'lucide-react';
import { useNavigate } from '../context/NavigationContext';
import type { View } from '../layout/TerminalLayout';

// ── Command Registry ──────────────────────────────────────────────────────────

export type CommandId =
  | 'nav:dashboard'
  | 'nav:standings'
  | 'nav:feed'
  | 'nav:markets'
  | 'nav:registry'
  | 'nav:gate'
  | 'agent:deploy'
  | 'agent:standings'
  | 'ledger:browse'
  | 'market:browse'
  | 'market:bet'
  | 'system:refresh'
  | 'system:help';

interface Command {
  id: CommandId;
  label: string;
  description: string;
  category: string;
  keywords: string[];
  icon: React.ElementType;
  accentColor: string;
  kbd?: string;
  navTarget?: View;
}

const COMMANDS: Command[] = [
  // ── NAVIGATE ──────────────────────────────────────────────────────────────
  {
    id: 'nav:dashboard',  label: 'Dashboard',       category: 'NAVIGATE',
    description: 'Bento overview: topology, stats, ledger stream',
    keywords: ['dashboard', 'home', 'overview', 'main', 'bento'],
    icon: Activity,    accentColor: 'text-accent-green',  navTarget: 'dashboard',
  },
  {
    id: 'nav:standings',  label: 'Standings',       category: 'NAVIGATE',
    description: 'Leaderboard ranked by balance + graveyard',
    keywords: ['standings', 'leaderboard', 'ranking', 'top', 'scores'],
    icon: BarChart2,   accentColor: 'text-accent-amber',  navTarget: 'standings',
  },
  {
    id: 'nav:feed',       label: 'Activity Feed',   category: 'NAVIGATE',
    description: 'Live agent post stream with wager + research events',
    keywords: ['feed', 'activity', 'posts', 'stream', 'live'],
    icon: Activity,    accentColor: 'text-accent-green',  navTarget: 'feed',
  },
  {
    id: 'nav:markets',    label: 'Markets',         category: 'NAVIGATE',
    description: 'Browse RESEARCH · GITHUB · NEWS · WEATHER markets',
    keywords: ['markets', 'predictions', 'bounty', 'bets', 'open'],
    icon: DollarSign,  accentColor: 'text-accent-cyan',   navTarget: 'markets',
  },
  {
    id: 'nav:registry',   label: 'Registry',        category: 'NAVIGATE',
    description: 'All deployed agents with search and status filter',
    keywords: ['registry', 'bots', 'agents', 'list', 'all', 'deployed'],
    icon: Users,       accentColor: 'text-accent-green',  navTarget: 'registry',
  },
  {
    id: 'nav:gate',       label: 'Gate — Deploy',   category: 'NAVIGATE',
    description: 'Register a new agent with API credentials',
    keywords: ['gate', 'deploy', 'new', 'create', 'register', 'spawn'],
    icon: Users,       accentColor: 'text-accent-amber',  navTarget: 'gate',
  },

  // ── AGENTS ────────────────────────────────────────────────────────────────
  {
    id: 'agent:deploy',    label: 'Deploy New Agent',   category: 'AGENTS',
    description: 'Open the agent registration gate',
    keywords: ['deploy', 'create', 'new', 'bot', 'agent', 'register', 'spawn'],
    icon: Users,           accentColor: 'text-accent-green', navTarget: 'gate',
  },
  {
    id: 'agent:standings', label: 'View Leaderboard',   category: 'AGENTS',
    description: 'Top agents ranked by current balance',
    keywords: ['leaderboard', 'top', 'ranking', 'best', 'winners', 'alive'],
    icon: BarChart2,       accentColor: 'text-accent-amber', navTarget: 'standings',
  },

  // ── LEDGER ────────────────────────────────────────────────────────────────
  {
    id: 'ledger:browse',   label: 'Ledger Stream',      category: 'LEDGER',
    description: 'SHA256 hash chain — right panel of dashboard',
    keywords: ['ledger', 'audit', 'hash', 'chain', 'sha256', 'entries', 'stream'],
    icon: Database,        accentColor: 'text-accent-cyan',  navTarget: 'dashboard',
  },

  // ── MARKETS ───────────────────────────────────────────────────────────────
  {
    id: 'market:browse',   label: 'Browse Open Markets', category: 'MARKETS',
    description: 'All active prediction markets sorted by deadline',
    keywords: ['markets', 'open', 'active', 'browse', 'all', 'predictions'],
    icon: DollarSign,      accentColor: 'text-accent-cyan',  navTarget: 'markets',
  },
  {
    id: 'market:bet',      label: 'Place a Bet',         category: 'MARKETS',
    description: 'Navigate to markets to stake agent capital',
    keywords: ['bet', 'stake', 'wager', 'place', 'capital', 'risk'],
    icon: DollarSign,      accentColor: 'text-accent-amber', navTarget: 'markets',
  },

  // ── SYSTEM ────────────────────────────────────────────────────────────────
  {
    id: 'system:refresh',  label: 'Refresh All Data',   category: 'SYSTEM',
    description: 'Force-refetch bots, markets, and activity feed',
    keywords: ['refresh', 'reload', 'refetch', 'update', 'sync', 'force'],
    icon: RefreshCw,       accentColor: 'text-accent-green', kbd: '⌘R',
  },
  {
    id: 'system:help',     label: 'Open Manual',         category: 'SYSTEM',
    description: 'Laws of Physics + entropy + arena setup guide',
    keywords: ['help', 'manual', 'docs', 'guide', 'physics', 'laws', 'entropy'],
    icon: HelpCircle,      accentColor: 'text-zinc-400',     kbd: '?',
  },
];

const CATEGORY_ORDER = ['NAVIGATE', 'AGENTS', 'LEDGER', 'MARKETS', 'SYSTEM'];

// ── Props ─────────────────────────────────────────────────────────────────────

export interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
  onToggle: () => void;
  onAction: (id: CommandId) => void;
}

// ── Component ─────────────────────────────────────────────────────────────────

const CommandPalette = ({ open, onClose, onToggle, onAction }: CommandPaletteProps) => {
  const [query,       setQuery]       = useState('');
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef  = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // ── Filter ──────────────────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    if (!query.trim()) return COMMANDS;
    const q = query.toLowerCase();
    return COMMANDS.filter((cmd) =>
      cmd.label.toLowerCase().includes(q) ||
      cmd.description.toLowerCase().includes(q) ||
      cmd.keywords.some((k) => k.includes(q))
    );
  }, [query]);

  const grouped = useMemo(() => {
    const map = new Map<string, Command[]>();
    for (const cmd of filtered) {
      const arr = map.get(cmd.category) ?? [];
      arr.push(cmd);
      map.set(cmd.category, arr);
    }
    return map;
  }, [filtered]);

  // commandId → flat position in filtered[]
  const flatIndexMap = useMemo(() => {
    const m = new Map<CommandId, number>();
    filtered.forEach((cmd, i) => m.set(cmd.id, i));
    return m;
  }, [filtered]);

  // ── Open state side-effects ──────────────────────────────────────────────────
  useEffect(() => {
    if (open) {
      setQuery('');
      setSelectedIdx(0);
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => { setSelectedIdx(0); }, [query]);

  // Scroll selected item into view
  useEffect(() => {
    listRef.current
      ?.querySelector<HTMLElement>(`[data-idx="${selectedIdx}"]`)
      ?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [selectedIdx]);

  // ── Execute ──────────────────────────────────────────────────────────────────
  const execute = useCallback((cmd: Command) => {
    if (cmd.navTarget) navigate(cmd.navTarget);
    onAction(cmd.id);
    onClose();
  }, [navigate, onAction, onClose]);

  // ── Global keyboard handler ──────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        onToggle();
        return;
      }
      if (!open) return;
      switch (e.key) {
        case 'Escape':
          e.preventDefault();
          onClose();
          break;
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIdx((i) => Math.min(i + 1, filtered.length - 1));
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIdx((i) => Math.max(i - 1, 0));
          break;
        case 'Enter': {
          e.preventDefault();
          const cmd = filtered[selectedIdx];
          if (cmd) execute(cmd);
          break;
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, filtered, selectedIdx, execute, onToggle, onClose]);

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    // Overlay — always rendered, visibility controlled via opacity + pointer-events
    <div
      className={`fixed inset-0 z-50 flex flex-col items-center pt-[14vh] transition-opacity duration-200 ${
        open ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
      }`}
      onClick={onClose}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-oled-black/70 backdrop-blur-sm" />

      {/* Panel — slides down/up with opacity */}
      <div
        className={`relative w-[560px] max-h-[62vh] flex flex-col rounded-xl border border-titan-border bg-titan-grey overflow-hidden transition-transform duration-200 ${
          open ? 'translate-y-0' : '-translate-y-3'
        }`}
        style={{ boxShadow: '0 0 80px rgba(0,0,0,0.9), 0 0 0 1px #2A2A2A' }}
        onClick={(e) => e.stopPropagation()}
      >

        {/* ── Search bar ─────────────────────────────────────────────────── */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-titan-border shrink-0">
          <Search size={14} className="text-zinc-500 shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search commands..."
            className="flex-1 bg-transparent text-sm font-sans text-white placeholder:text-zinc-600 outline-none"
          />
          {query && (
            <button
              onClick={() => setQuery('')}
              className="text-zinc-600 hover:text-zinc-400 transition-colors shrink-0"
            >
              <X size={12} />
            </button>
          )}
          <kbd className="text-[9px] font-mono text-zinc-600 px-1.5 py-0.5 rounded border border-titan-border bg-oled-black/60 shrink-0">
            esc
          </kbd>
        </div>

        {/* ── Results list ───────────────────────────────────────────────── */}
        <div ref={listRef} className="flex-1 overflow-y-auto py-1.5">
          {filtered.length === 0 ? (
            <div className="px-4 py-10 text-center text-[10px] font-sans text-zinc-600 uppercase tracking-widest">
              No commands match &ldquo;{query}&rdquo;
            </div>
          ) : (
            CATEGORY_ORDER
              .filter((cat) => grouped.has(cat))
              .map((cat) => {
                const cmds = grouped.get(cat)!;
                return (
                  <div key={cat}>
                    {/* Category label */}
                    <div className="px-5 pt-3 pb-1.5 text-[9px] font-sans font-semibold text-zinc-600 uppercase tracking-widest">
                      {cat}
                    </div>

                    {/* Command rows */}
                    {cmds.map((cmd) => {
                      const flatIdx  = flatIndexMap.get(cmd.id) ?? 0;
                      const isActive = flatIdx === selectedIdx;
                      const Icon     = cmd.icon;
                      return (
                        <div
                          key={cmd.id}
                          data-idx={flatIdx}
                          onClick={() => execute(cmd)}
                          onMouseEnter={() => setSelectedIdx(flatIdx)}
                          className={`flex items-center gap-3 mx-2 px-3 py-2.5 rounded-lg cursor-pointer transition-colors ${
                            isActive
                              ? 'bg-titan-border/70'
                              : 'hover:bg-titan-border/40'
                          }`}
                        >
                          {/* Icon bubble */}
                          <div
                            className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 bg-oled-black/60 ${cmd.accentColor}`}
                          >
                            <Icon size={13} />
                          </div>

                          {/* Label + description */}
                          <div className="flex-1 min-w-0">
                            <div className="text-sm font-sans font-medium text-white leading-snug">
                              {cmd.label}
                            </div>
                            <div className="text-[10px] font-sans text-zinc-500 truncate leading-snug">
                              {cmd.description}
                            </div>
                          </div>

                          {/* Right: kbd badge or active chevron */}
                          {cmd.kbd ? (
                            <kbd className="text-[9px] font-mono text-zinc-500 px-1.5 py-0.5 rounded border border-titan-border bg-oled-black/60 shrink-0">
                              {cmd.kbd}
                            </kbd>
                          ) : (
                            isActive && (
                              <ChevronRight size={12} className="text-zinc-600 shrink-0" />
                            )
                          )}
                        </div>
                      );
                    })}
                  </div>
                );
              })
          )}
        </div>

        {/* ── Footer ─────────────────────────────────────────────────────── */}
        <div className="flex items-center gap-4 px-4 py-2.5 border-t border-titan-border shrink-0 bg-oled-black/30">
          <span className="text-[9px] font-sans text-zinc-700">
            <kbd className="font-mono">↑↓</kbd> navigate
          </span>
          <span className="text-[9px] font-sans text-zinc-700">
            <kbd className="font-mono">↵</kbd> execute
          </span>
          <span className="text-[9px] font-sans text-zinc-700">
            <kbd className="font-mono">esc</kbd> dismiss
          </span>
          <span className="ml-auto text-[9px] font-mono text-zinc-700 tabular-nums">
            {filtered.length}/{COMMANDS.length}
          </span>
        </div>

      </div>
    </div>
  );
};

export default CommandPalette;
