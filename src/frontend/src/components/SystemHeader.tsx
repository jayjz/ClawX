import { useHealth, useMarkets } from '../api/client';
import type { Bot } from '../types';
import { Wifi, WifiOff, Skull, Users, Search } from 'lucide-react';

interface SystemHeaderProps {
  bots: Bot[] | undefined;
}

const SystemHeader = ({ bots }: SystemHeaderProps) => {
  const { data: health, isError: healthError } = useHealth();
  const { data: markets } = useMarkets();

  const alive = bots?.filter((b) => b.status === 'ALIVE').length ?? 0;
  const dead = bots?.filter((b) => b.status === 'DEAD').length ?? 0;
  const isOnline = !healthError && health?.status === 'ok';
  const openMarkets = markets?.length ?? 0;

  return (
    <div className="flex items-center gap-5">
      {/* Agents Online */}
      <div className="flex items-center gap-2">
        <Users size={12} className="text-neon-green" />
        <span className="text-xs text-zinc-500 uppercase tracking-wider">AGENTS:</span>
        <span className="text-xs text-neon-green font-bold">{alive}</span>
      </div>

      {/* Casualties */}
      {dead > 0 && (
        <div className="flex items-center gap-2">
          <Skull size={12} className="text-alert-red" />
          <span className="text-xs text-zinc-500 uppercase tracking-wider">KIA:</span>
          <span className="text-xs text-alert-red font-bold">{dead}</span>
        </div>
      )}

      <span className="text-zinc-700">|</span>

      {/* Open Markets */}
      <div className="flex items-center gap-2">
        <Search size={12} className="text-neon-cyan" />
        <span className="text-xs text-zinc-500 uppercase tracking-wider">MARKETS:</span>
        <span className="text-xs text-neon-cyan font-bold">{openMarkets}</span>
      </div>

      <span className="text-zinc-700">|</span>

      {/* Uplink Status */}
      <div className="flex items-center gap-2">
        {isOnline ? (
          <>
            <Wifi size={12} className="text-neon-green" />
            <span className="text-xs text-neon-green uppercase tracking-wider font-bold">UPLINK</span>
            <span className="w-1.5 h-1.5 bg-neon-green rounded-full animate-pulse" />
          </>
        ) : (
          <>
            <WifiOff size={12} className="text-alert-red" />
            <span className="text-xs text-alert-red uppercase tracking-wider font-bold">OFFLINE</span>
            <span className="w-1.5 h-1.5 bg-alert-red rounded-full" />
          </>
        )}
      </div>
    </div>
  );
};

export default SystemHeader;
