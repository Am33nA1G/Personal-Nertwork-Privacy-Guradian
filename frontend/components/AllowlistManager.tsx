import { useState, useEffect, useCallback } from 'react';
import type { AllowlistRule } from '../lib/types';
import { apiGetAllowlist, apiCreateAllowlistRule, apiDeleteAllowlistRule } from '../lib/api';

interface Props {
  token: string;
}

interface AddForm {
  process_name: string;
  dst_ip: string;
  dst_hostname: string;
  expires_at: string;
  reason: string;
}

const EMPTY_FORM: AddForm = {
  process_name: '',
  dst_ip: '',
  dst_hostname: '',
  expires_at: '',
  reason: '',
};

export default function AllowlistManager({ token }: Props) {
  const [rules, setRules] = useState<AllowlistRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [deleteStates, setDeleteStates] = useState<Record<string, { pending: boolean; error: string | null }>>({});

  // Add form state
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<AddForm>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const loadRules = useCallback(() => {
    setLoading(true);
    setFetchError(null);
    apiGetAllowlist(token)
      .then(res => setRules(res?.data ?? []))
      .catch(() => setFetchError('Failed to load allowlist rules'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    loadRules();
  }, [loadRules]);

  const handleDelete = useCallback(
    async (ruleId: string) => {
      setDeleteStates(prev => ({ ...prev, [ruleId]: { pending: true, error: null } }));
      try {
        const res = await apiDeleteAllowlistRule(token, ruleId);
        if (res?.success === false) {
          setDeleteStates(prev => ({
            ...prev,
            [ruleId]: { pending: false, error: res.error ?? 'Delete failed' },
          }));
        } else {
          setRules(prev => prev.filter(r => r.rule_id !== ruleId));
          setDeleteStates(prev => {
            const next = { ...prev };
            delete next[ruleId];
            return next;
          });
        }
      } catch {
        setDeleteStates(prev => ({
          ...prev,
          [ruleId]: { pending: false, error: 'Delete failed — try again' },
        }));
      }
    },
    [token]
  );

  function handleFormChange(field: keyof AddForm, value: string) {
    setForm(prev => ({ ...prev, [field]: value }));
    setFormError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmedIp = form.dst_ip.trim();
    const trimmedHost = form.dst_hostname.trim();
    if (!trimmedIp && !trimmedHost) {
      setFormError('At least one of Destination IP or Destination Hostname is required.');
      return;
    }

    setSubmitting(true);
    setFormError(null);
    try {
      const body: Record<string, string> = {};
      if (form.process_name.trim()) body.process_name = form.process_name.trim();
      if (trimmedIp) body.dst_ip = trimmedIp;
      if (trimmedHost) body.dst_hostname = trimmedHost;
      if (form.expires_at.trim()) body.expires_at = form.expires_at.trim();
      if (form.reason.trim()) body.reason = form.reason.trim();

      const res = await apiCreateAllowlistRule(token, body);
      if (res?.success === false) {
        setFormError(res.error ?? 'Failed to add rule');
      } else if (res?.data) {
        setRules(prev => [...prev, res.data as AllowlistRule]);
        setForm(EMPTY_FORM);
        setShowForm(false);
      } else {
        setFormError('Unexpected response from server');
      }
    } catch {
      setFormError('Failed to add rule — try again');
    } finally {
      setSubmitting(false);
    }
  }

  // Loading skeleton
  if (loading) {
    return (
      <div className="p-3">
        <div className="placeholder-glow">
          {[1, 2, 3].map(n => (
            <div key={n} className="mb-2">
              <span className="placeholder col-2 me-2" />
              <span className="placeholder col-3 me-2" />
              <span className="placeholder col-4" />
            </div>
          ))}
        </div>
        <span className="visually-hidden">Loading allowlist rules…</span>
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
            onClick={loadRules}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Add rule toggle */}
      <div className="d-flex align-items-center justify-content-between p-3 pb-0">
        <h6 className="mb-0 text-secondary small fw-semibold text-uppercase">Allowlist Rules</h6>
        <button
          className={`btn btn-sm ${showForm ? 'btn-outline-secondary' : 'btn-outline-success'}`}
          onClick={() => {
            setShowForm(v => !v);
            setFormError(null);
          }}
        >
          {showForm ? 'Cancel' : '+ Add Rule'}
        </button>
      </div>

      {/* Add rule form (collapsible) */}
      {showForm && (
        <form className="p-3 border-bottom border-secondary" onSubmit={handleSubmit} noValidate>
          <div className="row g-2">
            <div className="col-md-6">
              <label className="form-label small text-secondary" htmlFor="al-process">
                Process name <span className="text-muted">(optional)</span>
              </label>
              <input
                id="al-process"
                type="text"
                className="form-control form-control-sm bg-transparent text-light border-secondary"
                placeholder="chrome.exe"
                value={form.process_name}
                onChange={e => handleFormChange('process_name', e.target.value)}
              />
            </div>
            <div className="col-md-6">
              <label className="form-label small text-secondary" htmlFor="al-dst-ip">
                Destination IP <span className="text-muted">(optional)</span>
              </label>
              <input
                id="al-dst-ip"
                type="text"
                className="form-control form-control-sm bg-transparent text-light border-secondary"
                placeholder="1.2.3.4"
                value={form.dst_ip}
                onChange={e => handleFormChange('dst_ip', e.target.value)}
              />
            </div>
            <div className="col-md-6">
              <label className="form-label small text-secondary" htmlFor="al-dst-host">
                Destination hostname <span className="text-muted">(optional)</span>
              </label>
              <input
                id="al-dst-host"
                type="text"
                className="form-control form-control-sm bg-transparent text-light border-secondary"
                placeholder="example.com"
                value={form.dst_hostname}
                onChange={e => handleFormChange('dst_hostname', e.target.value)}
              />
            </div>
            <div className="col-md-6">
              <label className="form-label small text-secondary" htmlFor="al-expires">
                Expires at <span className="text-muted">(optional)</span>
              </label>
              <input
                id="al-expires"
                type="datetime-local"
                className="form-control form-control-sm bg-transparent text-light border-secondary"
                value={form.expires_at}
                onChange={e => handleFormChange('expires_at', e.target.value)}
              />
            </div>
            <div className="col-12">
              <label className="form-label small text-secondary" htmlFor="al-reason">
                Reason <span className="text-muted">(optional)</span>
              </label>
              <input
                id="al-reason"
                type="text"
                className="form-control form-control-sm bg-transparent text-light border-secondary"
                placeholder="Known safe traffic"
                value={form.reason}
                onChange={e => handleFormChange('reason', e.target.value)}
              />
            </div>
          </div>

          {formError && (
            <div className="alert alert-danger py-1 px-2 mt-2 small" role="alert">
              {formError}
            </div>
          )}

          <button
            type="submit"
            className="btn btn-sm btn-success mt-2"
            disabled={submitting}
          >
            {submitting ? (
              <>
                <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true" />
                Adding…
              </>
            ) : (
              'Add Rule'
            )}
          </button>
        </form>
      )}

      {/* Rules table */}
      {rules.length === 0 ? (
        <div className="p-4 text-center text-secondary">
          <p className="mb-0 small">No rules — all traffic is evaluated</p>
        </div>
      ) : (
        <div className="table-responsive">
          <table className="table table-dark table-sm table-hover mb-0 small">
            <thead className="border-secondary">
              <tr>
                <th className="text-secondary fw-normal">Process</th>
                <th className="text-secondary fw-normal">Dest IP</th>
                <th className="text-secondary fw-normal">Domain</th>
                <th className="text-secondary fw-normal">Expires</th>
                <th className="text-secondary fw-normal">Reason</th>
                <th className="text-secondary fw-normal" />
              </tr>
            </thead>
            <tbody>
              {rules.map(rule => {
                const delState = deleteStates[rule.rule_id];
                const isPending = delState?.pending ?? false;
                const delError = delState?.error ?? null;
                return (
                  <tr key={rule.rule_id} className="align-middle">
                    <td>{rule.process_name ?? '—'}</td>
                    <td className="font-monospace">{rule.dst_ip ?? '—'}</td>
                    <td>{rule.dst_hostname ?? '—'}</td>
                    <td className="text-secondary">
                      {rule.expires_at
                        ? new Date(rule.expires_at).toLocaleString()
                        : 'Never'}
                    </td>
                    <td className="text-secondary">{rule.reason ?? '—'}</td>
                    <td>
                      <div className="d-flex align-items-center gap-2">
                        <button
                          className="btn btn-outline-danger btn-sm py-0"
                          disabled={isPending}
                          onClick={() => handleDelete(rule.rule_id)}
                          aria-label={`Delete allowlist rule ${rule.rule_id}`}
                        >
                          {isPending ? (
                            <span
                              className="spinner-border spinner-border-sm"
                              role="status"
                              aria-hidden="true"
                            />
                          ) : (
                            'Delete'
                          )}
                        </button>
                        {delError && (
                          <span className="text-danger small">{delError}</span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
