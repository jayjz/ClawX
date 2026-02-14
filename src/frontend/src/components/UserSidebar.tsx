import { useState, useEffect } from 'react';
import {
  User, LogOut, TrendingUp, TrendingDown,
  Wallet, Crosshair, Cpu, RefreshCw,
} from 'lucide-react';
import { useUser } from '../context/UserContext.tsx';
import type { PredictionData, BotData } from '../types/index.ts';

const API_BASE = 'http://localhost:8000';

const UserSidebar = () => {
  const { currentUser, logout, refreshUser } = useUser();
  const [bets, setBets] = useState<PredictionData[]>([]);
  const [ownedBots, setOwnedBots] = useState<BotData[]>([]);

  useEffect(() => {
    if (!currentUser) return;

    const fetchData = async () => {
      try {
        const [betsRes, botsRes] = await Promise.all([
          fetch(`${API_BASE}/users/${encodeURIComponent(currentUser.username)}/bets`),
          fetch(`${API_BASE}/bots`),
        ]);
        if (betsRes.ok) setBets(await betsRes.json());
        if (botsRes.ok) {
          const all: BotData[] = await botsRes.json();
          setOwnedBots(all.filter(b => b.owner_id === currentUser.id));
        }
      } catch { /* silent */ }
    };

    fetchData();
    const timer = setInterval(fetchData, 10000);
    return () => clearInterval(timer);
  }, [currentUser]);

  if (!currentUser) return null;

  const openBets = bets.filter(b => b.status === 'OPEN');

  return (
    <div className="p-3 space-y-3 text-[10px]">
      {/* Identity */}
      <div className="pb-2 border-b border-terminal-border">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <User size={10} className="text-neon-cyan" />
            <span className="text-gray-600 uppercase tracking-[0.15em]">OPERATOR</span>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-1 text-gray-700 hover:text-alert-red transition-colors"
            title="Disconnect"
          >
            <LogOut size={9} />
            <span className="uppercase text-[8px]">EXIT</span>
          </button>
        </div>
        <div className="text-gray-300 font-bold uppercase text-[11px]">
          @{currentUser.username}
        </div>
      </div>

      {/* Balance */}
      <div className="pb-2 border-b border-terminal-border">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <Wallet size={10} className="text-neon-amber" />
            <span className="text-gray-600 uppercase tracking-[0.15em]">BALANCE</span>
          </div>
          <button
            onClick={refreshUser}
            className="text-gray-700 hover:text-neon-green transition-colors"
            title="Refresh"
          >
            <RefreshCw size={9} />
          </button>
        </div>
        <div className={`text-lg font-bold font-mono ${
          currentUser.balance >= 100 ? 'text-neon-green glow-green'
            : currentUser.balance > 0 ? 'text-neon-amber'
            : 'text-alert-red glow-red'
        }`}>
          {currentUser.balance.toFixed(2)}c
        </div>
        {currentUser.balance <= 0 && (
          <div className="text-[8px] text-alert-red uppercase mt-1">
            BALANCE DEPLETED — USE FAUCET
          </div>
        )}
      </div>

      {/* Active Bets */}
      <div className="pb-2 border-b border-terminal-border">
        <div className="flex items-center gap-2 mb-2">
          <Crosshair size={10} className="text-neon-cyan" />
          <span className="text-gray-600 uppercase tracking-[0.15em]">MY POSITIONS</span>
          <span className="text-gray-700 ml-auto">{openBets.length} OPEN</span>
        </div>
        <div className="space-y-1 max-h-48 overflow-y-auto">
          {openBets.slice(0, 8).map(bet => (
            <div key={bet.id} className="p-1.5 bg-terminal-deep border border-terminal-border">
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-gray-500 truncate max-w-[60%]">{bet.claim_text}</span>
                <span className={`font-bold ${bet.direction === 'UP' ? 'text-neon-green' : 'text-alert-red'}`}>
                  {bet.direction === 'UP' ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-700">CONF: {(bet.confidence * 100).toFixed(0)}%</span>
                <span className="text-neon-amber font-mono">{bet.wager_amount}c</span>
              </div>
            </div>
          ))}
          {openBets.length === 0 && (
            <div className="text-gray-700 text-center py-2">NO OPEN POSITIONS</div>
          )}
        </div>
      </div>

      {/* Owned Bots */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <Cpu size={10} className="text-neon-green" />
          <span className="text-gray-600 uppercase tracking-[0.15em]">MY AGENTS</span>
          <span className="text-gray-700 ml-auto">{ownedBots.length}</span>
        </div>
        <div className="space-y-1">
          {ownedBots.map(bot => (
            <div key={bot.id} className="p-1.5 bg-terminal-deep border border-terminal-border flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`w-1 h-1 rounded-full ${bot.status === 'DEAD' ? 'bg-alert-red' : 'bg-neon-green'}`} />
                <span className="text-gray-400 uppercase">{bot.handle}</span>
                {bot.is_verified && (
                  <span className="text-[7px] text-neon-cyan border border-neon-cyan/30 px-1">VERIFIED</span>
                )}
              </div>
              <span className="text-gray-600 font-mono">{bot.balance.toFixed(0)}c</span>
            </div>
          ))}
          {ownedBots.length === 0 && (
            <div className="text-gray-700 text-center py-2">NO CLAIMED AGENTS</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default UserSidebar;
