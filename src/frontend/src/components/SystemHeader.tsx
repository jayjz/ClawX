import { useHealth } from '../api/client';
import type { Bot } from '../types';
import { Wifi, WifiOff, Skull, Users } from 'lucide-react';

interface SystemHeaderProps {
  bots: Bot[] | undefined;
}

const SystemHeader = ({ bots }: SystemHeaderProps) => {
  const { data: health, isError: healthError } = useHealth();

  const alive = bots?.filter((b) => b.status === 'ALIVE').length ?? 0;
  const dead = bots?.filter((b) => b.status === 'DEAD').length ?? 0;
  const isOnline = !healthError && health?.status === 'ok';

  return (
    <div className="flex items-center gap-5">
      {/* Agents Online */}
      <div className="flex items-center gap-1.5">
        <Users size={10} className="text-neon-green" />
        <span className="text-[10px] text-zinc-500 uppercase tracking-wider">AGENTS:</span>
        <span className="text-[10px] text-neon-green font-bold">{alive}</span>
      </div>

      {/* Casualties */}
      {dead > 0 && (
        <div className="flex items-center gap-1.5">
          <Skull size={10} className="text-alert-red" />
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">KIA:</span>
          <span className="text-[10px] text-alert-red font-bold">{dead}</span>
        </div>
      )}

      <span className="text-zinc-700">|</span>

      {/* Uplink Status */}
      <div className="flex items-center gap-1.5">
        {isOnline ? (
          <>
            <Wifi size={10} className="text-neon-green" />
            <span className="text-[10px] text-neon-green uppercase tracking-wider font-bold">UPLINK</span>
            <span className="w-1.5 h-1.5 bg-neon-green rounded-full animate-pulse" />
          </>
        ) : (
          <>
            <WifiOff size={10} className="text-alert-red" />
            <span className="text-[10px] text-alert-red uppercase tracking-wider font-bold">OFFLINE</span>
            <span className="w-1.5 h-1.5 bg-alert-red rounded-full" />
          </>
        )}
      </div>
    </div>
  );
};

export default SystemHeader;
