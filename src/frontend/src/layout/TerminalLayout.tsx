import { useState, useEffect } from 'react';
import { Terminal, Activity, TrendingUp, Shield, Zap, FlaskConical, User, LogOut } from 'lucide-react';
import { useUser } from '../context/UserContext.tsx';

export type View = 'pulse' | 'trades' | 'ledger' | 'agents' | 'lab';

interface TerminalLayoutProps {
  activeView: View;
  onViewChange: (view: View) => void;
  children: React.ReactNode;
  sidebar: React.ReactNode;
  rightPanel: React.ReactNode;
}

const NAV_ITEMS: { id: View; icon: React.ReactNode; label: string; shortcut: string }[] = [
  { id: 'pulse', icon: <Activity size={14} />, label: 'MARKET PULSE', shortcut: 'F1' },
  { id: 'trades', icon: <TrendingUp size={14} />, label: 'TRADE FEED', shortcut: 'F2' },
  { id: 'ledger', icon: <Shield size={14} />, label: 'LEDGER AUDIT', shortcut: 'F3' },
  { id: 'agents', icon: <Zap size={14} />, label: 'AGENT STATUS', shortcut: 'F4' },
  { id: 'lab', icon: <FlaskConical size={14} />, label: 'BOT LAB', shortcut: 'F5' },
];

const TerminalLayout = ({ activeView, onViewChange, children, sidebar, rightPanel }: TerminalLayoutProps) => {
  const { currentUser, logout } = useUser();
  const [clock, setClock] = useState(new Date().toLocaleTimeString());

  useEffect(() => {
    const t = setInterval(() => setClock(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="h-screen flex flex-col bg-terminal-black text-gray-400 font-mono overflow-hidden">
      {/* TOP BAR — System Status + User Identity */}
      <header className="h-9 flex items-center justify-between px-4 border-b border-terminal-border bg-terminal-deep text-[10px] uppercase tracking-[0.15em] shrink-0">
        {/* Left: Branding */}
        <div className="flex items-center gap-3">
          <Terminal size={12} className="text-neon-green" />
          <span className="text-neon-green font-bold glow-green">NFH TERMINAL</span>
          <span className="text-gray-700">v0.8.0</span>
        </div>

        {/* Right: Clock + User */}
        <div className="flex items-center gap-4">
          <span className="text-gray-600 font-mono">{clock}</span>

          <span className="text-gray-700">|</span>

          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 bg-neon-green rounded-full animate-pulse" />
            <span className="text-neon-green">ONLINE</span>
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

      {/* NAV BAR — Tab-style */}
      <nav className="h-7 flex items-center gap-0 border-b border-terminal-border bg-terminal-deep shrink-0">
        {NAV_ITEMS.map(item => (
          <button
            key={item.id}
            onClick={() => onViewChange(item.id)}
            className={`h-full px-4 flex items-center gap-2 text-[10px] uppercase tracking-wider border-r border-terminal-border transition-colors ${
              activeView === item.id
                ? 'bg-terminal-black text-neon-green border-b-0'
                : 'text-gray-600 hover:text-gray-400 hover:bg-terminal-black/50'
            }`}
          >
            {item.icon}
            <span className="hidden lg:inline">{item.label}</span>
            <span className="text-gray-700 hidden xl:inline">[{item.shortcut}]</span>
          </button>
        ))}
      </nav>

      {/* MAIN GRID — 3 Column with fixed sidebar widths */}
      <div className="flex-1 flex overflow-hidden">
        {/* LEFT SIDEBAR — Market Stats (fixed width) */}
        <aside className="w-[260px] xl:w-[280px] shrink-0 border-r border-terminal-border overflow-y-auto hidden lg:block">
          {sidebar}
        </aside>

        {/* CENTER — Main Content (fluid) */}
        <main className="flex-1 overflow-y-auto p-5">
          {children}
        </main>

        {/* RIGHT PANEL — User/Bets (fixed width) */}
        <aside className="w-[320px] xl:w-[360px] shrink-0 border-l border-terminal-border overflow-y-auto hidden lg:block">
          {rightPanel}
        </aside>
      </div>

      {/* BOTTOM STATUS BAR */}
      <footer className="h-6 flex items-center justify-between px-4 border-t border-terminal-border bg-terminal-deep text-[9px] uppercase tracking-[0.15em] shrink-0">
        <span className="text-gray-700">CONN: WS/POLL 5s | DB: PG15 | ORACLE: COINGECKO</span>
        <span className="text-gray-700">SESSION: HANDLE_V1 | LATENCY: &lt;200ms</span>
      </footer>
    </div>
  );
};

export default TerminalLayout;
