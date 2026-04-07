import { useState, useEffect } from 'react';
import { apiStatus } from '../lib/api';
import type { CaptureStatus as CaptureStatusData } from '../lib/types';

interface Props {
  token: string;
}

type State = 'loading' | 'active' | 'unreachable';

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function CaptureStatus({ token }: Props) {
  const [state, setState] = useState<State>('loading');
  const [statusData, setStatusData] = useState<CaptureStatusData | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const res = await apiStatus(token);
        if (cancelled) return;
        const data = res?.data ?? res;
        if (data?.capture === 'running') {
          setStatusData(data as CaptureStatusData);
          setState('active');
        } else {
          setState('unreachable');
        }
      } catch {
        if (!cancelled) setState('unreachable');
      }
    }

    poll();
    const id = setInterval(poll, 1_000);
    return () => { cancelled = true; clearInterval(id); };
  }, [token]);

  if (state === 'loading') {
    return (
      <span className="status-pill pill-connecting" role="status" aria-label="Checking capture status">
        <span className="status-dot" />
        <span>Checking…</span>
      </span>
    );
  }

  if (state === 'unreachable') {
    return (
      <span className="status-pill pill-offline" title="Backend unreachable">
        <span className="status-dot" />
        <span>Backend offline</span>
      </span>
    );
  }

  const probeType = statusData?.probe_type ?? 'scapy';
  const uptime = statusData?.uptime != null ? formatUptime(statusData.uptime) : null;

  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
      <span
        className="status-pill pill-capture"
        title={`Probe: ${probeType}`}
        role="status"
        aria-label={`Capture active — ${probeType}`}
      >
        <span className="status-dot" />
        <span>{probeType}</span>
      </span>
      {uptime && (
        <span className="uptime-tag" aria-label={`Uptime: ${uptime}`}>
          {uptime}
        </span>
      )}
    </span>
  );
}
