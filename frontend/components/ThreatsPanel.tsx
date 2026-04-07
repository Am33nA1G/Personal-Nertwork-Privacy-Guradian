import { useState, useCallback } from 'react';
import type { ThreatEvent } from '../lib/types';
import { apiRemediateThreat } from '../lib/api';
import { SwordsIcon, BanIcon, XIcon, CheckCircleIcon } from '../lib/icons';

interface Props {
  threats: ThreatEvent[];
  isInitialLoading: boolean;
  initialError: string | null;
  token: string;
  onThreatActioned: (threatId: string) => void;
}

type ActionState = { pending: boolean; error: string | null };

interface ConfirmState {
  threatId: string;
  action: 'kill' | 'block_ip';
  processName: string;
  pid: number;
  targetIp: string;
}

const SEV_BAR_COLOR: Record<string, string> = {
  WARNING:  'var(--sev-warning)',
  ALERT:    'var(--sev-alert)',
  HIGH:     'var(--sev-alert)',
  CRITICAL: 'var(--sev-critical)',
  THREAT:   'var(--sev-critical)',
  INFO:     'var(--sev-info)',
  LOW:      'var(--sev-low)',
};

const SEV_CLASS: Record<string, string> = {
  WARNING:  'sev-WARNING',
  ALERT:    'sev-ALERT',
  HIGH:     'sev-HIGH',
  CRITICAL: 'sev-CRITICAL',
  THREAT:   'sev-THREAT',
  INFO:     'sev-INFO',
  LOW:      'sev-LOW',
};

export default function ThreatsPanel({
  threats,
  isInitialLoading,
  initialError,
  token,
  onThreatActioned,
}: Props) {
  const [actionStates, setActionStates] = useState<Record<string, ActionState>>({});
  const [confirmation, setConfirmation] = useState<ConfirmState | null>(null);

  const setThreatState = useCallback((threatId: string, state: ActionState) => {
    setActionStates(prev => ({ ...prev, [threatId]: state }));
  }, []);

  const handleRemediateClick = useCallback(
    (threatId: string, action: 'kill' | 'block_ip', threat: ThreatEvent) => {
      setConfirmation({
        threatId,
        action,
        processName: threat.process_name,
        pid: threat.pid,
        targetIp: threat.dst_ip,
      });
    },
    []
  );

  const handleConfirm = useCallback(
    async (confirm: boolean) => {
      if (!confirmation) return;
      if (!confirm) { setConfirmation(null); return; }

      const { threatId, action, pid } = confirmation;
      setThreatState(threatId, { pending: true, error: null });

      try {
        const res = await apiRemediateThreat(token, pid, action);
        if (res?.success === false) {
          setThreatState(threatId, { pending: false, error: res.error ?? 'Action failed' });
        } else {
          onThreatActioned(threatId);
        }
      } catch {
        setThreatState(threatId, { pending: false, error: 'Action failed — try again' });
      } finally {
        setConfirmation(null);
      }
    },
    [confirmation, token, onThreatActioned, setThreatState]
  );

  /* Loading */
  if (isInitialLoading) {
    return (
      <div style={{ padding: 10 }}>
        {[1, 2, 3].map(n => (
          <div key={n} style={{ marginBottom: 6 }}>
            <div className="skeleton" style={{ height: 80, borderRadius: 10 }} />
          </div>
        ))}
        <span className="visually-hidden">Loading threats…</span>
      </div>
    );
  }

  if (initialError) {
    return (
      <div className="error-block" style={{ margin: 12 }} role="alert">
        {initialError}
      </div>
    );
  }

  if (threats.length === 0) {
    return (
      <div className="empty-state">
        <CheckCircleIcon className="empty-icon" size={32} />
        <span className="empty-text">No active threats</span>
      </div>
    );
  }

  return (
    <>
      <div style={{ padding: 8 }}>
        {threats.map(threat => {
          const state = actionStates[threat.threat_id] ?? { pending: false, error: null };
          const barColor  = SEV_BAR_COLOR[threat.severity] ?? 'var(--bd-2)';
          const sevClass  = SEV_CLASS[threat.severity] ?? 'sev-LOW';
          const dst       = threat.dst_hostname ?? threat.dst_ip;
          const confPct   = Math.round(threat.confidence * 100);
          const isKilled  = threat.remediation_status === 'killed';
          const isBlocked = threat.remediation_status === 'blocked';

          return (
            <div key={threat.threat_id} className="ev-card">
              <div className="ev-card-inner">
                {/* Severity bar */}
                <div
                  className="ev-severity-bar"
                  style={{ background: barColor }}
                  aria-hidden="true"
                />

                <div className="ev-body">
                  {/* Meta */}
                  <div className="ev-meta">
                    <span className={`sev-badge ${sevClass}`}>{threat.severity}</span>
                    <span className="ev-rule" style={{ fontWeight: 600 }}>{threat.threat_type}</span>
                    <span className="ev-time">
                      {new Date(threat.detected_at).toLocaleTimeString()}
                    </span>
                  </div>

                  {/* Process */}
                  <div className="ev-reason" style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                    <span>{threat.process_name}</span>
                    <span style={{ color: 'var(--tx-3)', fontSize: '0.68rem', fontFamily: 'var(--font-mono)' }}>
                      PID {threat.pid}
                    </span>
                  </div>

                  {/* Reason */}
                  <div style={{ fontSize: '0.72rem', color: 'var(--tx-3)', marginBottom: 4, lineHeight: 1.35 }}>
                    {threat.reason}
                  </div>

                  {/* Target + confidence */}
                  <div className="ev-detail">
                    <span className="ev-arrow">→</span>
                    <span className="ev-dest">{dst}</span>
                    <span style={{ marginLeft: 4, color: 'var(--tx-3)' }}>·</span>
                    <span style={{ fontSize: '0.67rem', color: 'var(--tx-3)' }}>
                      {confPct}% confidence
                    </span>
                  </div>

                  {/* Confidence bar */}
                  <div className="conf-bar-wrap">
                    <div
                      className="conf-bar-fill"
                      style={{
                        width: `${confPct}%`,
                        background: confPct >= 80 ? 'var(--sev-critical)' : confPct >= 50 ? 'var(--sev-warning)' : 'var(--tx-3)',
                      }}
                    />
                  </div>

                  {state.error && (
                    <div className="ev-error">{state.error}</div>
                  )}
                </div>

                {/* Actions */}
                <div className="ev-actions">
                  <button
                    className={`btn-pnpg ${isKilled ? 'btn-ghost-dim' : 'btn-danger-pnpg'}`}
                    style={{ padding: '4px 9px', fontSize: '0.7rem' }}
                    disabled={state.pending || isKilled}
                    onClick={() => handleRemediateClick(threat.threat_id, 'kill', threat)}
                    title={isKilled ? 'Process killed' : 'Kill process'}
                  >
                    {state.pending ? (
                      <span className="spinner-xs" />
                    ) : (
                      <SwordsIcon size={12} />
                    )}
                  </button>

                  <button
                    className={`btn-pnpg ${isBlocked ? 'btn-ghost-dim' : 'btn-warning-pnpg'}`}
                    style={{ padding: '4px 9px', fontSize: '0.7rem' }}
                    disabled={state.pending || isBlocked}
                    onClick={() => handleRemediateClick(threat.threat_id, 'block_ip', threat)}
                    title={isBlocked ? 'IP blocked' : 'Block IP'}
                  >
                    {state.pending ? (
                      <span className="spinner-xs" />
                    ) : (
                      <BanIcon size={12} />
                    )}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Confirmation modal ── */}
      {confirmation && (
        <div
          className="pnpg-modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="confirm-title"
          onClick={(e) => { if (e.target === e.currentTarget) handleConfirm(false); }}
        >
          <div className="pnpg-modal">
            <div className="pnpg-modal-header">
              <h2 className="pnpg-modal-title" id="confirm-title">
                {confirmation.action === 'kill' ? (
                  <>
                    <SwordsIcon size={16} />
                    Kill Process
                  </>
                ) : (
                  <>
                    <BanIcon size={16} />
                    Block IP Address
                  </>
                )}
              </h2>
              <button
                className="btn-icon-close"
                onClick={() => handleConfirm(false)}
                aria-label="Cancel"
              >
                <XIcon size={14} />
              </button>
            </div>

            <div className="pnpg-modal-body">
              {confirmation.action === 'kill' ? (
                <>
                  <p style={{ fontSize: '0.82rem', color: 'var(--tx-2)', margin: '0 0 14px' }}>
                    This will immediately terminate the process:
                  </p>
                  <div style={{
                    padding: '10px 14px',
                    borderRadius: 'var(--r-sm)',
                    background: 'var(--sev-critical-bg)',
                    border: '1px solid rgba(239,68,68,0.2)',
                    fontSize: '0.82rem',
                  }}>
                    <strong style={{ color: 'var(--tx-1)' }}>{confirmation.processName}</strong>
                    <span style={{ color: 'var(--tx-3)', fontFamily: 'var(--font-mono)', fontSize: '0.72rem', marginLeft: 8 }}>
                      PID {confirmation.pid}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.72rem', color: 'var(--tx-3)', marginTop: 12, marginBottom: 0 }}>
                    This action cannot be undone.
                  </p>
                </>
              ) : (
                <>
                  <p style={{ fontSize: '0.82rem', color: 'var(--tx-2)', margin: '0 0 14px' }}>
                    This will block all traffic to:
                  </p>
                  <div style={{
                    padding: '10px 14px',
                    borderRadius: 'var(--r-sm)',
                    background: 'rgba(245,158,11,0.08)',
                    border: '1px solid rgba(245,158,11,0.22)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.82rem',
                    color: 'var(--tx-1)',
                  }}>
                    {confirmation.targetIp}
                  </div>
                  <p style={{ fontSize: '0.72rem', color: 'var(--tx-3)', marginTop: 12, marginBottom: 0 }}>
                    A Windows Firewall rule will be created and persisted.
                  </p>
                </>
              )}
            </div>

            <div className="pnpg-modal-footer">
              <button
                className="btn-pnpg btn-ghost"
                onClick={() => handleConfirm(false)}
              >
                Cancel
              </button>
              <button
                className={`btn-pnpg ${confirmation.action === 'kill' ? 'btn-danger-solid' : 'btn-warning-solid'}`}
                onClick={() => handleConfirm(true)}
              >
                {confirmation.action === 'kill' ? (
                  <>
                    <SwordsIcon size={12} />
                    Kill Process
                  </>
                ) : (
                  <>
                    <BanIcon size={12} />
                    Block IP
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
