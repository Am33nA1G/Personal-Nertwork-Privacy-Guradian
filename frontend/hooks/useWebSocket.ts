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
): { status: WsStatus; ws: React.MutableRefObject<WebSocket | null> } {
  const [status, setStatus] = useState<WsStatus>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onBatchRef = useRef(onBatch);

  // Keep the callback ref current without re-triggering the effect
  useEffect(() => {
    onBatchRef.current = onBatch;
  }, [onBatch]);

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
          onBatchRef.current({
            connections: msg.events ?? [],
            alerts: msg.alerts ?? [],
          });
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

  return { status, ws: wsRef };
}
