import { useState, useEffect, useCallback } from 'react';
import type { Suppression } from '../lib/types';
import { apiGetSuppressions, apiDeleteSuppression } from '../lib/api';

interface Props {
  token: string;
}

export default function SuppressionsLog({ token }: Props) {
  const [suppressions, setSuppressions] = useState<Suppression[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [undoStates, setUndoStates] = useState<Record<string, { pending: boolean; error: string | null }>>({});

  useEffect(() => {
    setLoading(true);
    setFetchError(null);
    apiGetSuppressions(token)
      .then(res => setSuppressions(res?.data ?? []))
      .catch(() => setFetchError('Failed to load suppressions'))
      .finally(() => setLoading(false));
  }, [token]);

  const handleUndo = useCallback(
    async (suppressionId: string) => {
      setUndoStates(prev => ({ ...prev, [suppressionId]: { pending: true, error: null } }));
      try {
        const res = await apiDeleteSuppression(token, suppressionId);
        if (res?.success === false) {
          setUndoStates(prev => ({
            ...prev,
            [suppressionId]: { pending: false, error: res.error ?? 'Undo failed' },
          }));
        } else {
          setSuppressions(prev => prev.filter(s => s.suppression_id !== suppressionId));
          setUndoStates(prev => {
            const next = { ...prev };
            delete next[suppressionId];
            return next;
          });
        }
      } catch {
        setUndoStates(prev => ({
          ...prev,
          [suppressionId]: { pending: false, error: 'Undo failed — try again' },
        }));
      }
    },
    [token]
  );

  // Loading state: skeleton rows
  if (loading) {
    return (
      <div className="p-3">
        <div className="placeholder-glow">
          {[1, 2, 3].map(n => (
            <div key={n} className="mb-2">
              <span className="placeholder col-3 me-2" />
              <span className="placeholder col-2 me-2" />
              <span className="placeholder col-4" />
            </div>
          ))}
        </div>
        <span className="visually-hidden">Loading suppressions…</span>
      </div>
    );
  }

  // Error state
  if (fetchError) {
    return (
      <div className="p-3">
        <div className="alert alert-danger d-flex align-items-center gap-2" role="alert">
          <span>{fetchError}</span>
          <button
            className="btn btn-sm btn-outline-danger ms-auto"
            onClick={() => {
              setFetchError(null);
              setLoading(true);
              apiGetSuppressions(token)
                .then(res => setSuppressions(res?.data ?? []))
                .catch(() => setFetchError('Failed to load suppressions'))
                .finally(() => setLoading(false));
            }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Empty state
  if (suppressions.length === 0) {
    return (
      <div className="p-4 text-center text-secondary">
        <p className="mb-0 small">No suppressions on record</p>
      </div>
    );
  }

  return (
    <div className="table-responsive">
      <table className="table table-dark table-sm table-hover mb-0 small">
        <thead className="border-secondary">
          <tr>
            <th className="text-secondary fw-normal">Rule</th>
            <th className="text-secondary fw-normal">Process</th>
            <th className="text-secondary fw-normal">Scope</th>
            <th className="text-secondary fw-normal">Reason</th>
            <th className="text-secondary fw-normal">Created</th>
            <th className="text-secondary fw-normal" />
          </tr>
        </thead>
        <tbody>
          {suppressions.map(s => {
            const undoState = undoStates[s.suppression_id];
            const isPending = undoState?.pending ?? false;
            const undoError = undoState?.error ?? null;

            return (
              <tr key={s.suppression_id} className="align-middle">
                <td className="font-monospace text-light">{s.rule_id ?? '—'}</td>
                <td>{s.process_name ?? '—'}</td>
                <td>
                  <span className="badge bg-secondary">{s.scope}</span>
                </td>
                <td className="text-secondary">{s.reason ?? '—'}</td>
                <td className="text-secondary">
                  {new Date(s.created_at).toLocaleString()}
                </td>
                <td>
                  <div className="d-flex align-items-center gap-2">
                    <button
                      className="btn btn-outline-warning btn-sm py-0"
                      disabled={isPending}
                      onClick={() => handleUndo(s.suppression_id)}
                      aria-label={`Undo suppression ${s.suppression_id}`}
                    >
                      {isPending ? (
                        <span
                          className="spinner-border spinner-border-sm"
                          role="status"
                          aria-hidden="true"
                        />
                      ) : (
                        'Undo'
                      )}
                    </button>
                    {undoError && (
                      <span className="text-danger small">{undoError}</span>
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
