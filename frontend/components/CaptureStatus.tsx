import { useState, useEffect } from 'react';
import { apiStatus } from '../lib/api';
import type { CaptureStatus as CaptureStatusData } from '../lib/types';

interface Props {
  token: string;
}

type StatusState = 'loading' | 'active' | 'unreachable';

export default function CaptureStatus({ token }: Props) {
  const [state, setState] = useState<StatusState>('loading');
  const [statusData, setStatusData] = useState<CaptureStatusData | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const res = await apiStatus(token);
        if (cancelled) return;
        if (res?.capture === 'running') {
          setStatusData(res as CaptureStatusData);
          setState('active');
        } else {
          setState('unreachable');
        }
      } catch {
        if (!cancelled) setState('unreachable');
      }
    }

    poll();
    const id = setInterval(poll, 5_000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [token]);

  if (state === 'loading') {
    return (
      <span className="d-inline-flex align-items-center gap-1 text-secondary small">
        <span
          className="spinner-border spinner-border-sm"
          role="status"
          aria-label="Checking capture status"
        />
      </span>
    );
  }

  if (state === 'unreachable') {
    return (
      <span className="badge bg-danger d-inline-flex align-items-center gap-1" title="Backend unreachable">
        <span aria-hidden="true">&#10005;</span>
        <span>Backend unreachable</span>
      </span>
    );
  }

  // state === 'active'
  const probeType = statusData?.probe_type ?? 'scapy';
  const uptime = statusData?.uptime != null
    ? `${Math.floor(statusData.uptime / 60)}m ${Math.floor(statusData.uptime % 60)}s`
    : null;

  return (
    <span className="d-inline-flex align-items-center gap-1">
      <span
        className="badge bg-success d-inline-flex align-items-center gap-1"
        title={`Probe: ${probeType}`}
      >
        <span aria-hidden="true">&#9679;</span>
        <span>Active ({probeType})</span>
      </span>
      {uptime && (
        <span className="text-secondary small font-monospace" aria-label={`Uptime: ${uptime}`}>
          {uptime}
        </span>
      )}
    </span>
  );
}
