// ClawX Arena — useArenaStream // WS HOOK
// Connects to /ws/stream, buffers events in useRef, drains to React state
// every 16ms (≈60fps). React.memo safe — state updates are batched,
// not one-per-message. Exponential-backoff reconnect (500ms → 30s cap).
//
// Payload from backend (ws_publisher.py):
//   {"t": unix_ts, "e": "W|H|L|R", "b": bot_id, "a": amount?}

import { useState, useEffect, useRef, useCallback } from 'react';

// ── Config ────────────────────────────────────────────────────────────────────

const API_BASE   = (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://localhost:8000';
const WS_BASE    = API_BASE.replace(/^http/, 'ws');
const WS_URL     = `${WS_BASE}/ws/stream`;

const MAX_EVENTS  = 200;    // rolling window retained in state
const DRAIN_MS    = 16;     // buffer drain interval (~60fps)
const BACKOFF_MIN = 500;    // initial reconnect delay (ms)
const BACKOFF_CAP = 30_000; // max reconnect delay (ms)

// ── Types ─────────────────────────────────────────────────────────────────────

export interface StreamEvent {
  /** Unix timestamp (seconds) */
  t: number;
  /** Event code: W=WAGER  H=HEARTBEAT  L=LIQUIDATION  R=RESEARCH/PORTFOLIO */
  e: 'W' | 'H' | 'L' | 'R';
  /** Bot ID that produced the event */
  b: number;
  /** Amount involved (optional) */
  a?: number;
}

export type StreamEventCode = StreamEvent['e'];

export interface ArenaStreamState {
  /** Last MAX_EVENTS events, newest first */
  events: StreamEvent[];
  /** Most recently received event */
  lastEvent: StreamEvent | null;
  /** Whether the WebSocket is currently OPEN */
  connected: boolean;
  /** Running totals per event code since mount */
  eventCounts: Record<StreamEventCode, number>;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

const ZERO_COUNTS: Record<StreamEventCode, number> = { W: 0, H: 0, L: 0, R: 0 };

export function useArenaStream(): ArenaStreamState {
  const [events,      setEvents     ] = useState<StreamEvent[]>([]);
  const [lastEvent,   setLastEvent  ] = useState<StreamEvent | null>(null);
  const [connected,   setConnected  ] = useState(false);
  const [eventCounts, setEventCounts] = useState<Record<StreamEventCode, number>>(ZERO_COUNTS);

  // ── Refs (never trigger re-renders) ────────────────────────────────────────
  /** Incoming events accumulate here between drain ticks */
  const buffer     = useRef<StreamEvent[]>([]);
  const wsRef      = useRef<WebSocket | null>(null);
  const drainTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoff    = useRef<number>(BACKOFF_MIN);
  const mounted    = useRef(true);

  // ── Drain: flush buffer → React state in one batch ─────────────────────────
  // Called every DRAIN_MS. Drains buffer atomically with splice(0) so
  // concurrent pushes from onmessage never race (single-threaded JS).
  const drainBuffer = useCallback(() => {
    const batch = buffer.current.splice(0); // drain entire buffer, newest-first
    if (batch.length === 0) return;

    setEvents((prev) => [...batch, ...prev].slice(0, MAX_EVENTS));
    if (batch[0]) setLastEvent(batch[0]); // batch[0] = most recent (unshift order)
    setEventCounts((prev) => {
      const next = { ...prev };
      for (const ev of batch) next[ev.e] = (next[ev.e] ?? 0) + 1;
      return next;
    });
  }, []); // stable — only touches refs and setState setters

  // ── Connect: open WebSocket with backoff retry ─────────────────────────────
  const connect = useCallback(() => {
    if (!mounted.current) return;
    // Guard against double-open
    const rs = wsRef.current?.readyState;
    if (rs === WebSocket.OPEN || rs === WebSocket.CONNECTING) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mounted.current) { ws.close(); return; }
      backoff.current = BACKOFF_MIN; // reset on successful connect
      setConnected(true);
    };

    ws.onmessage = (evt: MessageEvent<string>) => {
      try {
        const ev = JSON.parse(evt.data) as StreamEvent;
        // Validate required fields before buffering
        if (typeof ev.t === 'number' && typeof ev.b === 'number' && ev.e) {
          buffer.current.unshift(ev); // newest first
        }
      } catch {
        // malformed payload — discard silently
      }
    };

    ws.onclose = () => {
      if (!mounted.current) return;
      setConnected(false);
      const delay = backoff.current;
      backoff.current = Math.min(delay * 2, BACKOFF_CAP);
      retryTimer.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close(); // onclose fires → schedules retry
    };
  }, []); // stable — only touches refs

  // ── Lifecycle ──────────────────────────────────────────────────────────────
  useEffect(() => {
    mounted.current = true;
    connect();
    drainTimer.current = setInterval(drainBuffer, DRAIN_MS);

    return () => {
      mounted.current = false;
      if (drainTimer.current !== null) clearInterval(drainTimer.current);
      if (retryTimer.current !== null) clearTimeout(retryTimer.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect, drainBuffer]);

  return { events, lastEvent, connected, eventCounts };
}
