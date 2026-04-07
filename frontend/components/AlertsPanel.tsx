import { useState, useCallback } from 'react';
import type { AlertEvent } from '../lib/types';
import { apiPatchAlert } from '../lib/api';
import { CheckCircleIcon, EyeOffIcon, CheckIcon } from '../lib/icons';

interface Props {
  alerts: AlertEvent[];
  isInitialLoading: boolean;
  initialError: string | null;
  token: string;
  onAlertActioned: (alertId: string) => void;
}

type ActionState = { pending: boolean; error: string | null };

/* Maps severity → CSS class used for .sev-badge and left bar color */
const SEV_CLASS: Record<string, string> = {
  INFO:     'sev-INFO',
  LOW:      'sev-LOW',
  WARNING:  'sev-WARNING',
  ALERT:    'sev-ALERT',
  HIGH:     'sev-HIGH',
  CRITICAL: 'sev-CRITICAL',
  THREAT:   'sev-THREAT',
};

const SEV_BAR_COLOR: Record<string, string> = {
  INFO:     'var(--sev-info)',
  LOW:      'var(--sev-low)',
  WARNING:  'var(--sev-warning)',
  ALERT:    'var(--sev-alert)',
  HIGH:     'var(--sev-alert)',
  CRITICAL: 'var(--sev-critical)',
  THREAT:   'var(--sev-critical)',
};

function SeverityBar({ severity }: { severity: string }) {
  const color = SEV_BAR_COLOR[severity] ?? 'var(--bd-2)';
  return (
    <div
      className="ev-severity-bar"
      style={{ background: color }}
      aria-hidden="true"
    />
  );
}

export default function AlertsPanel({
  alerts,
  isInitialLoading,
  initialError,
  token,
  onAlertActioned,
}: Props) {
  const [actionStates, setActionStates] = useState<Record<string, ActionState>>({});

  const setAlertState = useCallback((alertId: string, state: ActionState) => {
    setActionStates(prev => ({ ...prev, [alertId]: state }));
  }, []);

  const handleAction = useCallback(
    async (alertId: string, action: 'suppress' | 'resolve') => {
      setAlertState(alertId, { pending: true, error: null });
      try {
        const res = await apiPatchAlert(token, alertId, action);
        if (res?.success === false) {
          setAlertState(alertId, { pending: false, error: res.error ?? 'Action failed' });
        } else {
          onAlertActioned(alertId);
        }
      } catch {
        setAlertState(alertId, { pending: false, error: 'Action failed — try again' });
      }
    },
    [token, onAlertActioned, setAlertState]
  );

  /* Loading skeleton */
  if (isInitialLoading) {
    return (
      <div style={{ padding: 10 }}>
        {[1, 2, 3].map(n => (
          <div key={n} style={{ marginBottom: 6 }}>
            <div className="skeleton" style={{ height: 68, borderRadius: 10 }} />
          </div>
        ))}
        <span className="visually-hidden">Loading alerts…</span>
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

  if (alerts.length === 0) {
    return (
      <div className="empty-state">
        <CheckCircleIcon className="empty-icon" size={32} />
        <span className="empty-text">No active alerts</span>
      </div>
    );
  }

  return (
    <div style={{ padding: 8 }}>
      {alerts.map(alert => {
        const alertState = actionStates[alert.alert_id];
        const isPending  = alertState?.pending ?? false;
        const actionError = alertState?.error ?? null;
        const sevClass   = SEV_CLASS[alert.severity] ?? 'sev-LOW';
        const dst        = alert.dst_hostname ?? alert.dst_ip;

        return (
          <div key={alert.alert_id} className="ev-card">
            <div className="ev-card-inner">
              <SeverityBar severity={alert.severity} />

              <div className="ev-body">
                {/* Meta row */}
                <div className="ev-meta">
                  <span className={`sev-badge ${sevClass}`}>{alert.severity}</span>
                  <span className="ev-rule">{alert.rule_id}</span>
                  <span className="ev-time">
                    {new Date(alert.timestamp).toLocaleTimeString()}
                  </span>
                </div>

                {/* Reason */}
                <div className="ev-reason">{alert.reason}</div>

                {/* Process → dest */}
                <div className="ev-detail">
                  <span className="ev-process">{alert.process_name}</span>
                  {dst && (
                    <>
                      <span className="ev-arrow">→</span>
                      <span className="ev-dest">{dst}</span>
                    </>
                  )}
                </div>

                {actionError && (
                  <div className="ev-error">{actionError}</div>
                )}
              </div>

              {/* Actions */}
              <div className="ev-actions">
                <button
                  className="btn-pnpg btn-warning-pnpg"
                  style={{ padding: '4px 9px', fontSize: '0.7rem' }}
                  disabled={isPending}
                  onClick={() => handleAction(alert.alert_id, 'suppress')}
                  aria-label={`Suppress alert ${alert.alert_id}`}
                  title="Suppress"
                >
                  {isPending ? (
                    <span className="spinner-xs" />
                  ) : (
                    <EyeOffIcon size={12} />
                  )}
                </button>

                <button
                  className="btn-pnpg btn-success-pnpg"
                  style={{ padding: '4px 9px', fontSize: '0.7rem' }}
                  disabled={isPending}
                  onClick={() => handleAction(alert.alert_id, 'resolve')}
                  aria-label={`Resolve alert ${alert.alert_id}`}
                  title="Resolve"
                >
                  {isPending ? (
                    <span className="spinner-xs" />
                  ) : (
                    <CheckIcon size={12} />
                  )}
                </button>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
