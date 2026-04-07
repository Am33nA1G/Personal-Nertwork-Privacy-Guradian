import { useState, useEffect, useCallback } from 'react';
import type { Suppression } from '../lib/types';
import { apiGetSuppressions, apiDeleteSuppression } from '../lib/api';
import { RotateCcwIcon, EyeOffIcon } from '../lib/icons';

interface Props {
  token: string;
}

export default function SuppressionsLog({ token }: Props) {
  const [suppressions, setSuppressions]   = useState<Suppression[]>([]);
  const [loading, setLoading]             = useState(false);
  const [fetchError, setFetchError]       = useState<string | null>(null);
  const [undoStates, setUndoStates]       = useState<Record<string, { pending: boolean; error: string | null }>>({});

  function load() {
    setLoading(true);
    setFetchError(null);
    apiGetSuppressions(token)
      .then(res => setSuppressions(res?.data ?? []))
      .catch(() => setFetchError('Failed to load suppressions'))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleUndo = useCallback(
    async (suppressionId: string) => {
      setUndoStates(prev => ({ ...prev, [suppressionId]: { pending: true, error: null } }));
      try {
        const res = await apiDeleteSuppression(token, suppressionId);
        if (res?.success === false) {
          setUndoStates(prev => ({ ...prev, [suppressionId]: { pending: false, error: res.error ?? 'Undo failed' } }));
        } else {
          setSuppressions(prev => prev.filter(s => s.suppression_id !== suppressionId));
          setUndoStates(prev => { const next = { ...prev }; delete next[suppressionId]; return next; });
        }
      } catch {
        setUndoStates(prev => ({ ...prev, [suppressionId]: { pending: false, error: 'Undo failed — try again' } }));
      }
    },
    [token]
  );

  /* Loading */
  if (loading) {
    return (
      <div style={{ padding: 12 }}>
        {[1, 2, 3].map(n => (
          <div key={n} className="skeleton-row">
            <div className="skeleton" style={{ width: 100, height: 14 }} />
            <div className="skeleton" style={{ width: 80, height: 14 }} />
            <div className="skeleton" style={{ width: 140, height: 14 }} />
          </div>
        ))}
        <span className="visually-hidden">Loading suppressions…</span>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="error-block" style={{ margin: 12 }} role="alert">
        <span>{fetchError}</span>
        <button
          className="btn-pnpg btn-ghost"
          style={{ marginLeft: 'auto', padding: '3px 10px', fontSize: '0.72rem' }}
          onClick={load}
        >
          Retry
        </button>
      </div>
    );
  }

  if (suppressions.length === 0) {
    return (
      <div className="empty-state">
        <EyeOffIcon className="empty-icon" size={28} />
        <span className="empty-text">No suppressions on record</span>
      </div>
    );
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="data-table">
        <thead>
          <tr>
            <th>Rule</th>
            <th>Process</th>
            <th>Scope</th>
            <th>Reason</th>
            <th>Created</th>
            <th style={{ width: 80 }} />
          </tr>
        </thead>
        <tbody>
          {suppressions.map(s => {
            const undoState = undoStates[s.suppression_id];
            const isPending = undoState?.pending ?? false;
            const undoError = undoState?.error ?? null;

            return (
              <tr key={s.suppression_id}>
                <td className="td-mono td-primary">{s.rule_id ?? '—'}</td>
                <td>{s.process_name ?? '—'}</td>
                <td>
                  <span className="scope-badge">{s.scope}</span>
                </td>
                <td className="td-muted">{s.reason ?? '—'}</td>
                <td className="td-muted">{new Date(s.created_at).toLocaleString()}</td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <button
                      className="btn-pnpg btn-warning-pnpg"
                      style={{ padding: '4px 9px', fontSize: '0.7rem' }}
                      disabled={isPending}
                      onClick={() => handleUndo(s.suppression_id)}
                      aria-label="Undo suppression"
                      title="Undo suppression"
                    >
                      {isPending ? (
                        <span className="spinner-xs" />
                      ) : (
                        <>
                          <RotateCcwIcon size={12} />
                          Undo
                        </>
                      )}
                    </button>
                    {undoError && (
                      <span style={{ fontSize: '0.68rem', color: 'var(--sev-critical)' }}>{undoError}</span>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
