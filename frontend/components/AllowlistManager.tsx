import { useState, useEffect, useCallback } from 'react';
import type { AllowlistRule } from '../lib/types';
import { apiGetAllowlist, apiCreateAllowlistRule, apiDeleteAllowlistRule } from '../lib/api';
import { PlusIcon, Trash2Icon, XIcon, CheckCircleIcon } from '../lib/icons';

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
  const [rules, setRules]         = useState<AllowlistRule[]>([]);
  const [loading, setLoading]     = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [deleteStates, setDeleteStates] = useState<Record<string, { pending: boolean; error: string | null }>>({});

  const [showForm, setShowForm]   = useState(false);
  const [form, setForm]           = useState<AddForm>(EMPTY_FORM);
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

  useEffect(() => { loadRules(); }, [loadRules]);

  const handleDelete = useCallback(
    async (ruleId: string) => {
      setDeleteStates(prev => ({ ...prev, [ruleId]: { pending: true, error: null } }));
      try {
        const res = await apiDeleteAllowlistRule(token, ruleId);
        if (res?.success === false) {
          setDeleteStates(prev => ({ ...prev, [ruleId]: { pending: false, error: res.error ?? 'Delete failed' } }));
        } else {
          setRules(prev => prev.filter(r => r.rule_id !== ruleId));
          setDeleteStates(prev => { const next = { ...prev }; delete next[ruleId]; return next; });
        }
      } catch {
        setDeleteStates(prev => ({ ...prev, [ruleId]: { pending: false, error: 'Delete failed — try again' } }));
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
    const trimIp   = form.dst_ip.trim();
    const trimHost = form.dst_hostname.trim();
    if (!trimIp && !trimHost) {
      setFormError('Destination IP or Hostname is required.');
      return;
    }

    setSubmitting(true);
    setFormError(null);
    try {
      const body: Record<string, string> = {};
      if (form.process_name.trim()) body.process_name = form.process_name.trim();
      if (trimIp)                   body.dst_ip       = trimIp;
      if (trimHost)                 body.dst_hostname  = trimHost;
      if (form.expires_at.trim())   body.expires_at   = form.expires_at.trim();
      if (form.reason.trim())       body.reason        = form.reason.trim();

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

  /* Loading */
  if (loading) {
    return (
      <div style={{ padding: 12 }}>
        {[1, 2, 3].map(n => (
          <div key={n} className="skeleton-row">
            <div className="skeleton" style={{ width: 80, height: 14 }} />
            <div className="skeleton" style={{ width: 120, height: 14 }} />
            <div className="skeleton" style={{ width: 160, height: 14 }} />
          </div>
        ))}
        <span className="visually-hidden">Loading allowlist rules…</span>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="error-block" style={{ margin: 12 }} role="alert">
        <span>{fetchError}</span>
        <button className="btn-pnpg btn-ghost" style={{ marginLeft: 'auto', padding: '3px 10px', fontSize: '0.72rem' }} onClick={loadRules}>
          Retry
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Toolbar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px 14px',
        borderBottom: '1px solid var(--bd-1)',
      }}>
        <span style={{ fontSize: '0.72rem', color: 'var(--tx-3)', fontWeight: 600, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
          {rules.length} rule{rules.length !== 1 ? 's' : ''}
        </span>
        <button
          className={`btn-pnpg ${showForm ? 'btn-ghost' : 'btn-success-pnpg'}`}
          onClick={() => { setShowForm(v => !v); setFormError(null); }}
          style={{ padding: '5px 11px' }}
        >
          {showForm ? (
            <>
              <XIcon size={12} />
              Cancel
            </>
          ) : (
            <>
              <PlusIcon size={13} />
              Add Rule
            </>
          )}
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <form className="al-form-area" onSubmit={handleSubmit} noValidate>
          <div className="row g-2">
            <div className="col-md-6">
              <label className="pnpg-label" htmlFor="al-process">
                Process name <span className="pnpg-label-opt">(optional)</span>
              </label>
              <input
                id="al-process"
                type="text"
                className="pnpg-input"
                placeholder="chrome.exe"
                value={form.process_name}
                onChange={e => handleFormChange('process_name', e.target.value)}
              />
            </div>
            <div className="col-md-6">
              <label className="pnpg-label" htmlFor="al-dst-ip">
                Destination IP <span className="pnpg-label-opt">(optional)</span>
              </label>
              <input
                id="al-dst-ip"
                type="text"
                className="pnpg-input"
                placeholder="1.2.3.4"
                value={form.dst_ip}
                onChange={e => handleFormChange('dst_ip', e.target.value)}
              />
            </div>
            <div className="col-md-6">
              <label className="pnpg-label" htmlFor="al-dst-host">
                Destination hostname <span className="pnpg-label-opt">(optional)</span>
              </label>
              <input
                id="al-dst-host"
                type="text"
                className="pnpg-input"
                placeholder="example.com"
                value={form.dst_hostname}
                onChange={e => handleFormChange('dst_hostname', e.target.value)}
              />
            </div>
            <div className="col-md-6">
              <label className="pnpg-label" htmlFor="al-expires">
                Expires at <span className="pnpg-label-opt">(optional)</span>
              </label>
              <input
                id="al-expires"
                type="datetime-local"
                className="pnpg-input"
                value={form.expires_at}
                onChange={e => handleFormChange('expires_at', e.target.value)}
              />
            </div>
            <div className="col-12">
              <label className="pnpg-label" htmlFor="al-reason">
                Reason <span className="pnpg-label-opt">(optional)</span>
              </label>
              <input
                id="al-reason"
                type="text"
                className="pnpg-input"
                placeholder="Known safe traffic"
                value={form.reason}
                onChange={e => handleFormChange('reason', e.target.value)}
              />
            </div>
          </div>

          {formError && (
            <div className="error-block" style={{ marginTop: 10 }} role="alert">
              {formError}
            </div>
          )}

          <div style={{ marginTop: 12 }}>
            <button
              type="submit"
              className="btn-pnpg btn-success-pnpg"
              disabled={submitting}
            >
              {submitting ? (
                <>
                  <span className="spinner-xs" />
                  Adding…
                </>
              ) : (
                <>
                  <PlusIcon size={13} />
                  Add Rule
                </>
              )}
            </button>
          </div>
        </form>
      )}

      {/* Rules table */}
      {rules.length === 0 ? (
        <div className="empty-state">
          <CheckCircleIcon className="empty-icon" size={28} />
          <span className="empty-text">No rules — all traffic is evaluated</span>
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Process</th>
                <th>Dest IP</th>
                <th>Domain</th>
                <th>Expires</th>
                <th>Reason</th>
                <th style={{ width: 60 }} />
              </tr>
            </thead>
            <tbody>
              {rules.map(rule => {
                const delState = deleteStates[rule.rule_id];
                const isPending = delState?.pending ?? false;
                const delError  = delState?.error ?? null;
                return (
                  <tr key={rule.rule_id}>
                    <td className="td-primary">{rule.process_name ?? '—'}</td>
                    <td className="td-mono">{rule.dst_ip ?? '—'}</td>
                    <td>{rule.dst_hostname ?? '—'}</td>
                    <td className="td-muted">
                      {rule.expires_at ? new Date(rule.expires_at).toLocaleString() : 'Never'}
                    </td>
                    <td className="td-muted">{rule.reason ?? '—'}</td>
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <button
                          className="btn-pnpg btn-danger-pnpg"
                          style={{ padding: '4px 9px' }}
                          disabled={isPending}
                          onClick={() => handleDelete(rule.rule_id)}
                          aria-label={`Delete allowlist rule`}
                          title="Delete rule"
                        >
                          {isPending ? (
                            <span className="spinner-xs" />
                          ) : (
                            <Trash2Icon size={12} />
                          )}
                        </button>
                        {delError && (
                          <span style={{ fontSize: '0.68rem', color: 'var(--sev-critical)' }}>{delError}</span>
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
