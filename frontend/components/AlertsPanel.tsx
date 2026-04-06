import { useState, useCallback } from 'react';
import type { AlertEvent } from '../lib/types';
import { SEVERITY_BADGE, SEVERITY_CLASSES } from '../lib/types';
import { apiPatchAlert } from '../lib/api';

interface Props {
  alerts: AlertEvent[];
  isInitialLoading: boolean;
  initialError: string | null;
  token: string;
  onAlertActioned: (alertId: string) => void;
}

type ActionState = { pending: boolean; error: string | null };

const SEVERITY_BORDER: Record<string, string> = {
  WARNING:  'var(--sev-warning, #ffc107)',
  ALERT:    'var(--sev-alert, #fd7e14)',
  HIGH:     'var(--sev-alert, #fd7e14)',
  CRITICAL: 'var(--sev-critical, #dc3545)',
  INFO:     'var(--bs-info, #0dcaf0)',
  LOW:      'var(--bs-secondary, #6c757d)',
};

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

  // Loading state: skeleton cards
  if (isInitialLoading) {
    return (
      <div className="p-3">
        {[1, 2, 3].map(n => (
          <div
            key={n}
            className="card border-secondary mb-2 placeholder-glow"
            style={{ backgroundColor: 'var(--bs-card-bg, #161b22)' }}
          >
            <div className="card-body py-2 px-3">
              <span className="placeholder col-4 me-2" />
              <span className="placeholder col-6" />
              <div className="mt-1">
                <span className="placeholder col-8" />
              </div>
            </div>
          </div>
        ))}
        <span className="visually-hidden">Loading alerts…</span>
      </div>
    );
  }

  // Error state from parent's initial fetch
  if (initialError) {
    return (
      <div className="p-3">
        <div className="alert alert-danger d-flex align-items-center gap-2" role="alert">
          <span>{initialError}</span>
        </div>
      </div>
    );
  }

  // Empty state
  if (alerts.length === 0) {
    return (
      <div className="p-4 text-center text-secondary">
        <span style={{ fontSize: '1.5rem' }} role="img" aria-label="checkmark">&#10003;</span>
        <p className="mt-2 mb-0 small">No active alerts</p>
      </div>
    );
  }

  return (
    <div
      style={{ maxHeight: '420px', overflowY: 'auto' }}
      className="p-2"
    >
      {alerts.map(alert => {
        const alertState = actionStates[alert.alert_id];
        const isPending = alertState?.pending ?? false;
        const actionError = alertState?.error ?? null;
        const borderColor = SEVERITY_BORDER[alert.severity] ?? 'var(--bs-secondary, #6c757d)';
        const textClass = SEVERITY_CLASSES[alert.severity] ?? '';
        const badgeClass = SEVERITY_BADGE[alert.severity] ?? 'bg-secondary';

        return (
          <div
            key={alert.alert_id}
            className="card border-secondary mb-2"
            style={{
              backgroundColor: 'var(--bs-card-bg, #161b22)',
              borderLeft: `4px solid ${borderColor}`,
            }}
          >
            <div className="card-body py-2 px-3">
              <div className="d-flex align-items-start justify-content-between gap-2">
                <div className="flex-grow-1 min-width-0">
                  <div className="d-flex align-items-center gap-2 mb-1">
                    <span className={`badge ${badgeClass} small`}>
                      {alert.severity}
                    </span>
                    <span className={`small fw-semibold ${textClass}`}>
                      {alert.rule_id}
                    </span>
                    <span className="text-secondary small">
                      {new Date(alert.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="small text-light mb-1">{alert.reason}</div>
                  <div className="small text-secondary">
                    <span className="me-2">{alert.process_name}</span>
                    {(alert.dst_hostname ?? alert.dst_ip) && (
                      <span>&#8594; {alert.dst_hostname ?? alert.dst_ip}</span>
                    )}
                  </div>
                  {actionError && (
                    <span className="text-danger small mt-1 d-block">{actionError}</span>
                  )}
                </div>

                <div className="d-flex gap-1 flex-shrink-0">
                  <button
                    className="btn btn-outline-warning btn-sm"
                    disabled={isPending}
                    onClick={() => handleAction(alert.alert_id, 'suppress')}
                    aria-label={`Suppress alert ${alert.alert_id}`}
                  >
                    {isPending ? (
                      <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
                    ) : (
                      'Suppress'
                    )}
                  </button>
                  <button
                    className="btn btn-outline-success btn-sm"
                    disabled={isPending}
                    onClick={() => handleAction(alert.alert_id, 'resolve')}
                    aria-label={`Resolve alert ${alert.alert_id}`}
                  >
                    {isPending ? (
                      <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
                    ) : (
                      'Resolve'
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
