/** Shared utility functions for bot display logic */

/** Compute ticks until death at base entropy rate (0.50c/tick) */
export const ticksUntilDeath = (balance: number) => Math.floor(balance / 0.5);

/** Survival bar color based on ticks remaining */
export const survivalColor = (ticks: number) => {
  if (ticks > 500) return { bar: 'bg-neon-green', text: 'text-neon-green' };
  if (ticks > 100) return { bar: 'bg-neon-amber', text: 'text-neon-amber' };
  return { bar: 'bg-alert-red', text: 'text-alert-red' };
};

/** Deterministic color from handle string */
export const avatarColor = (handle: string): string => {
  const colors = ['#00ff41', '#00d4ff', '#ffaa00', '#ff3333', '#cc44ff', '#44ffcc'];
  let hash = 0;
  for (let i = 0; i < handle.length; i++) hash = handle.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length] ?? '#00ff41';
};

/** Hash string to deterministic boolean array for 5x5 mirrored identicon grid */
export const hashToGrid = (handle: string): boolean[] => {
  let h = 0;
  for (let i = 0; i < handle.length; i++) {
    h = ((h << 5) - h + handle.charCodeAt(i)) | 0;
  }
  const bits: boolean[] = [];
  for (let row = 0; row < 5; row++) {
    const rowBits: boolean[] = [];
    for (let col = 0; col < 3; col++) {
      const bitIndex = row * 3 + col;
      rowBits.push(((Math.abs(h >> bitIndex) & 1) === 1));
    }
    bits.push(rowBits[0]!, rowBits[1]!, rowBits[2]!, rowBits[1]!, rowBits[0]!);
  }
  return bits;
};

/** Deterministic mock sparkline points from balance + id */
export const sparklinePoints = (balance: number, id: number, width = 44, height = 14, steps = 5): string => {
  const dx = width / (steps - 1);
  let seed = (id * 7919 + Math.floor(balance * 13)) | 0;
  const pts: number[] = [];
  for (let i = 0; i < steps; i++) {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    const jitter = ((seed % 100) / 100 - 0.5) * 0.6;
    const baseY = height * (1 - Math.min(balance / 1200, 1));
    pts.push(Math.max(1, Math.min(height - 1, baseY + jitter * height)));
  }
  pts[steps - 1] = Math.max(1, Math.min(height - 1, height * (1 - Math.min(balance / 1200, 1))));
  return pts.map((y, i) => `${i * dx},${y}`).join(' ');
};

/** Recency tier from last_action_at */
export type RecencyTier = 'active' | 'recent' | 'stale' | 'unknown';

export const getRecencyTier = (lastActionAt: string | null, now: number): RecencyTier => {
  if (!lastActionAt) return 'unknown';
  const elapsed = now - new Date(lastActionAt).getTime();
  if (elapsed < 60_000) return 'active';
  if (elapsed < 300_000) return 'recent';
  return 'stale';
};

export const TIER_STYLES: Record<RecencyTier, { ring: string; anim: string; label: string }> = {
  active:  { ring: 'ring-1 ring-neon-green/60', anim: 'animate-pulse-fast', label: 'ACTIVE' },
  recent:  { ring: 'ring-1 ring-neon-amber/40', anim: 'animate-pulse-slow', label: 'IDLE' },
  stale:   { ring: 'ring-1 ring-alert-red/30', anim: '', label: 'RISK' },
  unknown: { ring: 'ring-1 ring-zinc-800', anim: '', label: '' },
};

/** Format seconds into MM:SS */
export const formatCountdown = (seconds: number): string => {
  if (seconds <= 0) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
};
