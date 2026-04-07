import { useEffect, useRef, useState, useCallback } from 'react';
import type { ConnectionEvent, AlertEvent } from '../lib/types';

export type WsStatus = 'connecting' | 'connected' | 'disconnected';

export interface WsBatchPayload {
  connections?: ConnectionEvent[];
  alerts?: AlertEvent[];
}

const WS_BASE = 'ws://127.0.0.1:8001';

export function useWebSocket(
  token: string | null,
  onBatch: (payload: WsBatchPayload) => void
): {
  status: WsStatus;
  ws: React.MutableRefObject<WebSocket | null>;
  isPaused: boolean;
  pendingCount: number;
  pause: () => void;
  resume: () => void;
} {
  const [status, setStatus] = useState<WsStatus>('disconnected');
  const [isPaused, setIsPaused] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onBatchRef = useRef(onBatch);

  // Pause state refs for use inside ws.onmessage closure
  const isPausedRef = useRef(false);
  const pendingRef = useRef<WsBatchPayload[]>([]);

  // Keep the callback ref current without re-triggering the effect
  useEffect(() => {
    onBatchRef.current = onBatch;
  }, [onBatch]);

  const pause = useCallback(() => {
    isPausedRef.current = true;
    setIsPaused(true);
  }, []);

  const resume = useCallback(() => {
    isPausedRef.current = false;
    setIsPaused(false);
    if (pendingRef.current.length > 0) {
      const buffered = pendingRef.current.slice();
      pendingRef.current = [];
      setPendingCount(0);
      // Merge all buffered payloads into a single batch call
      const merged: WsBatchPayload = {
        connections: buffered.flatMap(p => p.connections ?? []),
        alerts: buffered.flatMap(p => p.alerts ?? []),
      };
      onBatchRef.current(merged);
    }
  }, []);

  const connect = useCallback(() => {
    if (!token) return;

    // Clear any pending reconnect timer
    if (reconnectTimerRef.current !== null) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    setStatus('connecting');
    const url = `${WS_BASE}/api/v1/ws/live?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      attemptRef.current = 0;
      setStatus('connected');
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string);
        if (msg.type === 'batch') {
          // WsManager batches payload objects into events[]:
          //   { type:'batch', events: [ {connections:[...], alerts:[...]}, ... ] }
          // Each element is a broadcast payload, not a raw connection event.
          const payloadItems: { connections?: ConnectionEvent[]; alerts?: AlertEvent[] }[] =
            Array.isArray(msg.events) ? msg.events : [];
          const payload: WsBatchPayload = {
            connections: payloadItems.flatMap(p => p.connections ?? []),
            alerts: payloadItems.flatMap(p => p.alerts ?? []),
          };
          if (isPausedRef.current) {
            // Buffer while paused (cap at 500 payloads to avoid unbounded growth)
            pendingRef.current = [...pendingRef.current, payload].slice(-500);
            const count = pendingRef.current.reduce(
              (acc, p) => acc + (p.connections?.length ?? 0) + (p.alerts?.length ?? 0),
              0
            );
            setPendingCount(count);
          } else {
            onBatchRef.current(payload);
          }
        }
        // heartbeat — ignore
      } catch {
        // Malformed message — ignore
      }
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onclose = () => {
      setStatus('disconnected');
      wsRef.current = null;

      if (!token) return;

      const delay = Math.min(30000, 1000 * Math.pow(2, attemptRef.current));
      attemptRef.current += 1;

      reconnectTimerRef.current = setTimeout(() => {
        connect();
      }, delay);
    };
  }, [token]);

  useEffect(() => {
    if (!token) {
      // Close existing connection if token is removed
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect on manual close
        wsRef.current.close();
        wsRef.current = null;
      }
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      setStatus('disconnected');
      return;
    }

    connect();

    return () => {
      // Cleanup on unmount
      if (reconnectTimerRef.current !== null) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect on unmount
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [token, connect]);

  return { status, ws: wsRef, isPaused, pendingCount, pause, resume };
}
