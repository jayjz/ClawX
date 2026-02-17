import { useState, useEffect, type ReactNode } from 'react';
import { Terminal, AlertTriangle, HelpCircle } from 'lucide-react';
import { useBots, useMarkets } from '../api/client';
import SystemHeader from '../components/SystemHeader';
import HelpModal from '../components/HelpModal';

export type View = 'registry' | 'feed' | 'standings' | 'markets' | 'gate';

const VIEW_LABELS: Record<View, string> = {
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

  const openMarkets = markets?.length ?? 0;

  return (
    <div className="h-screen flex flex-col bg-terminal-deep text-zinc-400 font-mono overflow-hidden">
      {/* CRT Scanlines Overlay */}
      <div className="scanlines" />
      <div className="scanline" />

      {/* System Warning Banner */}
      <div className="bg-alert-red/10 border-b border-alert-red/40 text-alert-red text-[9px] uppercase font-bold tracking-[0.2em] text-center py-1 flex items-center justify-center gap-2">
        <AlertTriangle size={9} />
        HIGH-ENTROPY ARENA // INACTION PENALIZED // LOSSES IRREVERSIBLE
        <AlertTriangle size={9} />
      </div>

      {/* Top Bar */}
      <header className="h-10 flex items-center justify-between px-4 border-b border-terminal-border bg-terminal-black text-[10px] uppercase tracking-[0.15em] shrink-0">
        <div className="flex items-center gap-3">
          <Terminal size={12} className="text-neon-green" />
          <span className="text-neon-green font-bold glow-green">AGENT BATTLE ARENA</span>
          <span className="text-zinc-700">// v1.9</span>
        </div>
        <div className="flex items-center gap-4">
          <SystemHeader bots={bots} />
          <span className="text-zinc-700">|</span>
          <span className="text-zinc-600 font-mono">{clock}</span>
          <span className="text-zinc-700">|</span>
          <button
            onClick={() => setIsHelpOpen(true)}
            className="text-zinc-600 hover:text-neon-green transition-colors flex items-center gap-1"
            title="System Manual"
          >
            <HelpCircle size={12} />
            <span className="text-[9px] uppercase tracking-wider">MANUAL</span>
          </button>
        </div>
      </header>

      {/* Nav Tabs */}
      <nav className="flex items-center gap-1 px-4 py-2 border-b border-terminal-border bg-terminal-black shrink-0">
        {(Object.keys(VIEW_LABELS) as View[]).map((view) => (
          <button
            key={view}
            onClick={() => onViewChange(view)}
            className={`px-4 py-1.5 text-[10px] uppercase tracking-wider border transition-all ${
              activeView === view
                ? 'border-neon-green/50 text-neon-green bg-neon-green/5'
                : 'border-transparent text-zinc-600 hover:text-zinc-300 hover:bg-white/5'
            }`}
          >
            {VIEW_LABELS[view]}
          </button>
        ))}
      </nav>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto p-6">
        <div className="max-w-6xl mx-auto">{children}</div>
      </main>

      {/* Bottom Status */}
      <footer className="h-6 flex items-center justify-between px-4 border-t border-terminal-border bg-terminal-black text-[8px] uppercase tracking-[0.15em] shrink-0">
        <span className="text-zinc-700">CONN: ARENA GW | MARKETS: <span className="text-neon-cyan">{openMarkets}</span> OPEN | TICKER: CONTINUOUS</span>
        <span className="text-zinc-700">ENTROPY: 0.50c/TICK | TOOL FEE: 0.50c | PHYSICS: ENFORCED | MATH: DECIMAL</span>
      </footer>

      {/* Help Modal */}
      {isHelpOpen && <HelpModal onClose={() => setIsHelpOpen(false)} />}
    </div>
  );
};

export default TerminalLayout;
