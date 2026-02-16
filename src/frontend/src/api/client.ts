import { useQuery, useMutation } from '@tanstack/react-query';
import type { Bot, ActivityEntry, BotCreatePayload, BotCreateResponse, HealthResponse, ApiError } from '../types';

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
    refetchInterval: 10_000,
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
