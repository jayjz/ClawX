import { useState, useEffect, useRef, type ReactNode } from 'react';
import { useBots, useMarkets } from '../api/client';
import HelpModal from '../components/HelpModal';

export type View = 'dashboard' | 'registry' | 'feed' | 'standings' | 'markets' | 'gate';

interface TerminalLayoutProps {
  children:     ReactNode;
  activeView:   View;
  onViewChange: (view: View) => void;
}

const TerminalLayout = ({ activeView, onViewChange: _onViewChange, children }: TerminalLayoutProps) => {
  const [clock,         setClock]        = useState(new Date().toLocaleTimeString());
  const [isHelpOpen,    setIsHelpOpen]   = useState(false);
  const [tickCountdown, setTickCountdown] = useState(10);
  const [kiaFlash,      setKiaFlash]     = useState(false);
  const prevDeadRef = useRef<number | null>(null);
  const { data: bots }    = useBots();
  const { data: markets } = useMarkets();

  useEffect(() => {
    const t = setInterval(() => setClock(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(t);
  }, []);

  // Epoch-aligned 10→1 countdown
  useEffect(() => {
    const tick = () => setTickCountdown(10 - (Math.floor(Date.now() / 1000) % 10));
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, []);

  const aliveCount    = bots?.filter((b) => b.status === 'ALIVE').length ?? 0;
  const deadCount     = bots?.filter((b) => b.status === 'DEAD').length ?? 0;
  const totalBots     = bots?.length ?? 0;
  const lethality     = totalBots > 0 ? (deadCount / totalBots) * 100 : 0;
  const totalResearch = markets?.filter((m) => m.source_type === 'RESEARCH').length ?? 0;
  const openMarkets   = markets?.length ?? 0;

  // KIA flash on any new death
  useEffect(() => {
    if (prevDeadRef.current === null) { prevDeadRef.current = deadCount; return; }
    if (deadCount > prevDeadRef.current) {
      setKiaFlash(true);
      const t = setTimeout(() => setKiaFlash(false), 800);
      prevDeadRef.current = deadCount;
      return () => clearTimeout(t);
    }
    prevDeadRef.current = deadCount;
  }, [deadCount]);

  const handleCmdOpen = () => {
    window.dispatchEvent(new CustomEvent('clawx:command-open'));
  };
  const handlePanelOpen = (panel: 'ledger' | 'orderbook' | 'battleground') => {
    window.dispatchEvent(new CustomEvent('clawx:panel', { detail: panel }));
  };

  return (
    <div className="h-screen flex flex-col bg-oled-black text-zinc-400 font-mono overflow-hidden">

      {/* CRT scanlines */}
      <div className="scanlines" />
      <div className="scanline" />

      {/* Minimal header */}
      <header
        className="h-10 flex items-center justify-between px-4 border-b border-zinc-800 bg-black shrink-0"
        style={{ boxShadow: 'inset 0 -1px 0 rgba(255,255,255,0.03)' }}
      >
        <span className="text-[10px] font-sans font-bold text-white uppercase tracking-widest">
          DARK FOREST ARENA
          <span className="ml-2 text-zinc-700 font-normal">// v3.2</span>
        </span>

        <div className="flex items-center gap-3">
          <span className="text-[10px] font-mono text-zinc-600 tabular-nums">{clock}</span>
          <button
            onClick={() => setIsHelpOpen(true)}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg border border-zinc-800 text-[10px] font-mono text-zinc-500 hover:border-zinc-600 hover:text-zinc-300 transition-all"
          >
            MANUAL
          </button>
        </div>
      </header>

      {/* Telemetry ribbon — glassmorphic data pills */}
      <div className="telemetry-ribbon shrink-0">
        <span className="telemetry-pill telemetry-pill--alive">● {aliveCount}&nbsp;ALIVE</span>
        <span className={lethality > 50 ? 'telemetry-pill telemetry-pill--lethality-hot' : 'telemetry-pill telemetry-pill--lethality'}>
          {lethality.toFixed(0)}%&nbsp;LETHALITY
        </span>
        <span className="telemetry-pill telemetry-pill--research">{totalResearch}&nbsp;RESEARCH</span>
        <span className={kiaFlash ? 'telemetry-pill telemetry-pill--kia-hot' : 'telemetry-pill telemetry-pill--kia'}>
          ☠&nbsp;{deadCount}&nbsp;KIA
        </span>
      </div>

      {/* Main content */}
      <main className={`flex-1 min-h-0 ${
        activeView === 'dashboard'
          ? 'overflow-hidden flex flex-col'
          : 'overflow-y-auto p-6'
      }`}>
        {activeView === 'dashboard'
          ? children
          : <div className="max-w-6xl mx-auto">{children}</div>
        }
      </main>

      {/* Floating ⌘K command bar — dashboard only */}
      {activeView === 'dashboard' && (
        <div className="floating-cmd-bar">
          <div className="floating-cmd-group">
            <div className="floating-cmd-actions">
              <button className="floating-cmd-action" onClick={() => handlePanelOpen('battleground')}>
                BATTLEGROUND
              </button>
              <button className="floating-cmd-action" onClick={() => handlePanelOpen('ledger')}>
                LEDGER
              </button>
              <button className="floating-cmd-action" onClick={() => handlePanelOpen('orderbook')}>
                ORDER BOOK
              </button>
            </div>
            <button className="floating-cmd-btn" onClick={handleCmdOpen} aria-label="Open command palette">
              <kbd className="text-[11px] font-mono text-accent-green font-bold leading-none">⌘K</kbd>
              <span className="floating-cmd-label">COMMAND</span>
            </button>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="h-6 flex items-center justify-between px-4 border-t border-zinc-800 bg-black text-[8px] uppercase tracking-[0.15em] shrink-0">
        <span className="text-zinc-700">
          CONN: ARENA GW | MARKETS: <span className="text-accent-cyan">{openMarkets}</span> OPEN | STREAM: CONTINUOUS
        </span>
        <span className={`font-mono tabular-nums font-bold ${
          tickCountdown <= 3 ? 'text-accent-red animate-pulse' : 'text-zinc-600'
        }`}>
          NEXT TICK: {tickCountdown}s
        </span>
        <span className="text-zinc-700">
          ENTROPY: 0.50c/TICK | LEDGER: SHA256 | MATH: DECIMAL
        </span>
      </footer>

      {isHelpOpen && <HelpModal onClose={() => setIsHelpOpen(false)} />}
    </div>
  );
};

export default TerminalLayout;
