import { useQuery, useMutation } from '@tanstack/react-query';
import type { Bot, ActivityEntry, BotCreatePayload, BotCreateResponse, HealthResponse, Market, ApiError, AgentInsights, ViabilityLog } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const body: ApiError = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(body.detail);
  }
  return res.json() as Promise<T>;
}

// ── Queries ──

export function useBots() {
  return useQuery<Bot[], Error>({
    queryKey: ['bots'],
    queryFn: () => fetchJson<Bot[]>(`${API_BASE}/bots`),
    refetchInterval: 8_000,
    retry: 2,
  });
}

export function useActivityFeed() {
  return useQuery<ActivityEntry[], Error>({
    queryKey: ['activity-feed'],
    queryFn: () => fetchJson<ActivityEntry[]>(`${API_BASE}/posts/feed?limit=50`),
    refetchInterval: 5_000,
    retry: 2,
  });
}

export function useMarkets() {
  return useQuery<Market[], Error>({
    queryKey: ['markets'],
    queryFn: () => fetchJson<Market[]>(`${API_BASE}/markets/active`),
    refetchInterval: 10_000,
    retry: 2,
  });
}

export function useHealth() {
  return useQuery<HealthResponse, Error>({
    queryKey: ['health'],
    queryFn: () => fetchJson<HealthResponse>(`${API_BASE}/health`),
    refetchInterval: 30_000,
    retry: 1,
  });
}

// ── Mutations ──

export function useCreateBot() {
  return useMutation<BotCreateResponse, Error, BotCreatePayload>({
    mutationFn: async (payload) => {
      const res = await fetch(`${API_BASE}/bots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const body: ApiError = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(body.detail);
      }
      return res.json() as Promise<BotCreateResponse>;
    },
  });
}

export function useInsights(agentId: number | null | undefined) {
  return useQuery<AgentInsights, Error>({
    queryKey: ['insights', agentId],
    queryFn: () => fetchJson<AgentInsights>(`${API_BASE}/insights/${agentId}`),
    enabled: agentId != null,
    retry: 1,
    staleTime: 10_000,
  });
}

export function useViability() {
  return useQuery<ViabilityLog, Error>({
    queryKey: ['viability'],
    queryFn: () => fetchJson<ViabilityLog>(`${API_BASE}/viability`),
    staleTime: 30_000,
    retry: 1,
  });
}

export function useRetireBot() {
  return useMutation<{ id: number; handle: string; status: string }, Error, number>({
    mutationFn: async (botId) => {
      const res = await fetch(`${API_BASE}/bots/${botId}`, { method: 'DELETE' });
      if (!res.ok) {
        const body: ApiError = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(body.detail);
      }
      return res.json();
    },
  });
}
