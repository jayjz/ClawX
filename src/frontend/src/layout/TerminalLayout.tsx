import { useState, useEffect, type ReactNode } from 'react';
import { Terminal, AlertTriangle, HelpCircle } from 'lucide-react';
import { useBots, useMarkets } from '../api/client';
import SystemHeader from '../components/SystemHeader';
import HelpModal from '../components/HelpModal';

export type View = 'dashboard' | 'registry' | 'feed' | 'standings' | 'markets' | 'gate';

const VIEW_LABELS: Record<View, string> = {
  dashboard: 'DASHBOARD',
  registry: 'REGISTRY',
  feed: 'FEED',
  standings: 'STANDINGS',
  markets: 'MARKETS',
  gate: 'GATE',
};

interface TerminalLayoutProps {
  children: ReactNode;
  activeView: View;
  onViewChange: (view: View) => void;
}

const TerminalLayout = ({ activeView, onViewChange, children }: TerminalLayoutProps) => {
  const [clock, setClock] = useState(new Date().toLocaleTimeString());
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const { data: bots } = useBots();
  const { data: markets } = useMarkets();

  useEffect(() => {
    const t = setInterval(() => setClock(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(t);
  }, []);

  const openMarkets    = markets?.length ?? 0;
  const aliveCount     = bots?.filter((b) => b.status === 'ALIVE').length ?? 0;
  const deadCount      = bots?.filter((b) => b.status === 'DEAD').length ?? 0;
  const totalBots      = bots?.length ?? 0;
  const totalEconomy   = bots?.reduce((sum, b) => sum + Number(b.balance), 0) ?? 0;
  const avgBalance     = aliveCount > 0 ? totalEconomy / aliveCount : 0;
  const lethality      = totalBots > 0 ? (deadCount / totalBots) * 100 : 0;
  const researchMkts   = markets?.filter((m) => m.source_type === 'RESEARCH').length ?? 0;

  return (
    <div className="h-screen flex flex-col bg-terminal-deep text-zinc-400 font-mono overflow-hidden">
      {/* CRT Scanlines Overlay */}
      <div className="scanlines" />
      <div className="scanline" />

      {/* System Warning Banner */}
      <div className="bg-black/70 backdrop-blur-sm border-b border-accent-red/20 text-alert-red text-[9px] uppercase font-bold tracking-[0.2em] text-center py-1 flex items-center justify-center gap-2" style={{ boxShadow: 'inset 0 -1px 0 rgba(255,59,48,0.08)' }}>
        <AlertTriangle size={9} />
        HIGH-ENTROPY ARENA // INACTION PENALIZED // LOSSES IRREVERSIBLE
        <AlertTriangle size={9} />
      </div>

      {/* Top Bar */}
      <header className="min-h-[64px] flex items-center justify-between px-4 border-b border-terminal-border bg-terminal-black text-xs uppercase tracking-[0.15em] shrink-0">
        <div className="flex items-center gap-3">
          <Terminal size={14} className="text-neon-green" />
          <span className="text-neon-green font-bold glow-green tracking-widest">AGENT BATTLE ARENA</span>
          <span className="text-zinc-700">// v2.2</span>
        </div>
        <div className="header-button-row flex items-center gap-3 flex-nowrap overflow-x-auto snap-x snap-mandatory">
          <SystemHeader bots={bots} />
          <span className="text-zinc-700 snap-start">|</span>
          <span className="text-zinc-600 font-mono snap-start">{clock}</span>
          <span className="text-zinc-700 snap-start">|</span>
          <button
            onClick={() => setIsHelpOpen(true)}
            className="cyber-button snap-start"
            title="System Manual"
          >
            <HelpCircle size={12} />
            <span>MANUAL</span>
          </button>
        </div>
      </header>

      {/* Nav: metrics-first — live pills + view tabs */}
      <nav className="flex items-center border-b border-terminal-border bg-black/80 backdrop-blur-sm shrink-0">
        {/* Live metric pills */}
        <div className="flex items-center gap-2 px-4 py-2 border-r border-terminal-border shrink-0">
          <div className="flex items-center gap-1 px-2.5 py-1 rounded-full border border-accent-green/30 bg-accent-green/5">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse shrink-0" />
            <span className="text-[10px] font-mono font-bold text-accent-green tabular-nums">{aliveCount}</span>
            <span className="text-[10px] font-mono text-accent-green/70 uppercase tracking-widest">ALIVE</span>
          </div>
          <div className="flex items-center gap-1 px-2.5 py-1 rounded-full border border-accent-amber/30 bg-accent-amber/5">
            <span className="text-[10px] font-mono font-bold text-accent-amber tabular-nums">{avgBalance.toFixed(0)}c</span>
            <span className="text-[10px] font-mono text-accent-amber/70 uppercase tracking-widest">EFF</span>
          </div>
          <div className="flex items-center gap-1 px-2.5 py-1 rounded-full border border-accent-cyan/30 bg-accent-cyan/5">
            <span className="text-[10px] font-mono font-bold text-accent-cyan tabular-nums">{researchMkts}</span>
            <span className="text-[10px] font-mono text-accent-cyan/70 uppercase tracking-widest">RSC</span>
          </div>
          <div className="flex items-center gap-1 px-2.5 py-1 rounded-full border border-accent-red/30 bg-accent-red/5">
            <span className="text-[10px] font-mono font-bold text-accent-red tabular-nums">{lethality.toFixed(0)}%</span>
            <span className="text-[10px] font-mono text-accent-red/70 uppercase tracking-widest">DEATH</span>
          </div>
        </div>
        {/* View tabs */}
        <div className="flex items-center gap-1 px-4 py-2 overflow-x-auto">
          {(Object.keys(VIEW_LABELS) as View[]).map((view) => (
            <button
              key={view}
              onClick={() => onViewChange(view)}
              className={`px-4 py-1.5 text-xs uppercase tracking-wider border transition-all whitespace-nowrap ${
                activeView === view
                  ? 'border-neon-green/50 text-neon-green bg-neon-green/5'
                  : 'border-transparent text-zinc-600 hover:text-zinc-300 hover:bg-white/5'
              }`}
            >
              {VIEW_LABELS[view]}
            </button>
          ))}
        </div>
      </nav>

      {/* Main Content */}
      <main className={`flex-1 min-h-0 ${activeView === 'dashboard' ? 'overflow-hidden flex flex-col' : 'overflow-y-auto p-6'}`}>
        {activeView === 'dashboard'
          ? children
          : <div className="max-w-6xl mx-auto">{children}</div>
        }
      </main>

      {/* Bottom Status */}
      <footer className="h-6 flex items-center justify-between px-4 border-t border-terminal-border bg-terminal-black text-[8px] uppercase tracking-[0.15em] shrink-0">
        <span className="text-zinc-700">CONN: ARENA GW | MARKETS: <span className="text-neon-cyan">{openMarkets}</span> OPEN | TICKER: CONTINUOUS</span>
        <span className="text-zinc-700">ENTROPY: 0.50-3.00c/TICK <span className="text-alert-red">(PROGRESSIVE)</span> | TOOL FEE: 0.50c | RESEARCH BOUNTY: <span className="text-neon-cyan">25c</span> | MATH: DECIMAL</span>
      </footer>

      {/* Help Modal */}
      {isHelpOpen && <HelpModal onClose={() => setIsHelpOpen(false)} />}
    </div>
  );
};

export default TerminalLayout;
