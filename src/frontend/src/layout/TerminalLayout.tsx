import { useState, useEffect } from 'react';
import { Terminal, User, LogOut, AlertTriangle } from 'lucide-react';
import { useUser } from '../context/UserContext.tsx';

export type View = 'pulse' | 'trades' | 'ledger' | 'agents' | 'lab';

interface TerminalLayoutProps {
  children: React.ReactNode;
  sidebar: React.ReactNode;
  rightPanel: React.ReactNode;
  activeView: View;
  onViewChange: (view: View) => void;
}

const TerminalLayout = ({ activeView, onViewChange, children, sidebar, rightPanel }: TerminalLayoutProps) => {
  const { currentUser, logout } = useUser();
  const [clock, setClock] = useState(new Date().toLocaleTimeString());

  useEffect(() => {
    const t = setInterval(() => setClock(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="h-screen flex flex-col bg-terminal-black text-gray-400 font-mono overflow-hidden">
      {/* SYSTEM BANNER - THE WARNING */}
      <div className="bg-alert-red/20 border-b border-alert-red text-alert-red text-[10px] uppercase font-bold tracking-widest text-center py-1 flex items-center justify-center gap-2">
        <AlertTriangle size={10} />
        Warning: High-Entropy Arena. Inaction Penalized. Losses Irreversible.
        <AlertTriangle size={10} />
      </div>

      {/* TOP BAR */}
      <header className="h-9 flex items-center justify-between px-4 border-b border-terminal-border bg-terminal-deep text-[10px] uppercase tracking-[0.15em] shrink-0">
        <div className="flex items-center gap-3">
          <Terminal size={12} className="text-neon-green" />
          <span className="text-neon-green font-bold glow-green">NFH TERMINAL</span>
          <span className="text-gray-700">v0.9.0 (Arena)</span>
        </div>

        <div className="flex items-center gap-4">
          <span className="text-gray-600 font-mono">{clock}</span>
          <span className="text-gray-700">|</span>
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 bg-neon-green rounded-full animate-pulse" />
            <span className="text-neon-green">SYSTEM LIVE</span>
          </span>
          
          {currentUser && (
            <>
              <span className="text-gray-700">|</span>
              <div className="flex items-center gap-2">
                <User size={10} className="text-neon-cyan" />
                <span className="text-gray-400 font-bold">@{currentUser.username}</span>
                <span className="text-neon-amber font-mono">{currentUser.balance.toFixed(0)}c</span>
                <button 
                  onClick={logout}
                  className="text-gray-700 hover:text-alert-red transition-colors ml-1"
                  title="Disconnect"
                >
                  <LogOut size={10} />
                </button>
              </div>
            </>
          )}
        </div>
      </header>

      {/* NAV TABS */}
      <nav className="flex items-center gap-1 px-4 py-2 border-b border-terminal-border bg-terminal-black shrink-0">
        {(['pulse', 'trades', 'ledger', 'agents', 'lab'] as View[]).map((view) => (
          <button
            key={view}
            onClick={() => onViewChange(view)}
            className={`px-3 py-1.5 text-[10px] uppercase tracking-wider border transition-all ${
              activeView === view
                ? 'border-neon-green/50 text-neon-green bg-neon-green/5 shadow-[0_0_10px_rgba(0,255,65,0.1)]'
                : 'border-transparent text-gray-600 hover:text-gray-300 hover:bg-white/5'
            }`}
          >
            {view}
          </button>
        ))}
      </nav>

      {/* MAIN GRID */}
      <div className="flex-1 flex overflow-hidden">
        {/* LEFT SIDEBAR */}
        <aside className="w-[260px] xl:w-[280px] shrink-0 border-r border-terminal-border overflow-y-auto hidden lg:block">
          {sidebar}
        </aside>

        {/* CENTER */}
        <main className="flex-1 overflow-y-auto p-5">
          {children}
        </main>

        {/* RIGHT PANEL */}
        <aside className="w-[320px] xl:w-[360px] shrink-0 border-l border-terminal-border overflow-y-auto hidden lg:block">
          {rightPanel}
        </aside>
      </div>

      {/* BOTTOM STATUS */}
      <footer className="h-6 flex items-center justify-between px-4 border-t border-terminal-border bg-terminal-deep text-[9px] uppercase tracking-[0.15em] shrink-0">
        <span className="text-gray-700">CONN: ATOMIC GW | DB: PG15 | ORACLE: PUB/SUB</span>
        <span className="text-gray-700">PHYSICS: ENABLED | LATENCY: &lt;50ms</span>
      </footer>
    </div>
  );
};

export default TerminalLayout;
