import dynamic from 'next/dynamic';
import Head from 'next/head';
import Link from 'next/link';
import { useCallback, useState, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useWebSocket } from '../hooks/useWebSocket';
import LoginPage from '../components/LoginPage';
import WsStatusIndicator from '../components/WsStatusIndicator';
import CaptureStatus from '../components/CaptureStatus';
import ConnectionsTable from '../components/ConnectionsTable';
import AlertsPanel from '../components/AlertsPanel';
import type { ConnectionEvent, AlertEvent } from '../lib/types';
import type { WsBatchPayload } from '../hooks/useWebSocket';
import { apiAlerts } from '../lib/api';

// Dynamic imports for Recharts components (no SSR — window must exist)
const ConnectionsPerApp = dynamic(
  () => import('../components/ConnectionsPerApp'),
  { ssr: false }
);

const ConnectionsPerSecond = dynamic(
  () => import('../components/ConnectionsPerSecond'),
  { ssr: false }
);

export default function Dashboard() {
  const { token, needsSetup, loading, error, login, setup, logout } = useAuth();

  // --- Connections state ---
  const [pendingConnections, setPendingConnections] = useState<ConnectionEvent[]>([]);
  // Chart connections buffer — capped at 500 for chart consumption
  const [connections, setConnections] = useState<ConnectionEvent[]>([]);
  const [latestBatchSize, setLatestBatchSize] = useState(0);

  // --- Alerts state (owned by index.tsx per plan ownership decision) ---
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [alertsError, setAlertsError] = useState<string | null>(null);

  // Initial alerts fetch — runs after token is available
  useEffect(() => {
    if (!token) return;
    setAlertsLoading(true);
    setAlertsError(null);
    apiAlerts(token, 'active')
      .then(res => setAlerts(res?.data ?? []))
      .catch(() => setAlertsError('Failed to load alerts'))
      .finally(() => setAlertsLoading(false));
  }, [token]);

  const handleBatch = useCallback((payload: WsBatchPayload) => {
    const newConns = payload.connections ?? [];
    const newAlerts = payload.alerts ?? [];

    if (newConns.length > 0) {
      setPendingConnections(newConns);
      setConnections(prev => [...newConns, ...prev].slice(0, 500));
      setLatestBatchSize(newConns.length);
    }
    if (newAlerts.length > 0) {
      setAlerts(prev => [...newAlerts, ...prev].slice(0, 200));
    }
  }, []);

  const { status, isPaused, pendingCount, pause, resume } = useWebSocket(token, handleBatch);

  function handlePauseToggle() {
    if (isPaused) {
      resume();
    } else {
      pause();
    }
  }

  function handleAlertActioned(alertId: string) {
    setAlerts(prev => prev.filter(a => a.alert_id !== alertId));
  }

  if (!token) {
    return (
      <LoginPage
        onLogin={login}
        onSetup={setup}
        needsSetup={needsSetup}
        loading={loading}
        error={error}
      />
    );
  }

  return (
    <>
      <Head>
        <title>PNPG &mdash; Network Privacy Guardian</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      {/* Navbar */}
      <nav
        className="navbar navbar-dark px-3 py-2 border-bottom border-secondary"
        style={{ backgroundColor: 'var(--bs-navbar-bg, #161b22)' }}
        aria-label="Main navigation"
      >
        <div className="d-flex align-items-center gap-2 flex-wrap">
          <span
            style={{ fontSize: '1.4rem' }}
            role="img"
            aria-label="shield"
          >
            &#128737;
          </span>
          <span className="navbar-brand mb-0 h5 fw-semibold text-light me-2">PNPG</span>
          <WsStatusIndicator status={status} />
          <CaptureStatus token={token} />
        </div>

        <div className="d-flex align-items-center gap-2 flex-wrap">
          <Link
            href="/allowlist"
            className="btn btn-sm btn-outline-secondary"
          >
            Allowlist
          </Link>
          <button
            className={`btn btn-sm ${isPaused ? 'btn-warning' : 'btn-outline-secondary'}`}
            onClick={handlePauseToggle}
            aria-pressed={isPaused}
            aria-label={isPaused ? 'Resume live updates' : 'Pause live updates'}
          >
            {isPaused ? '\u25b6 Resume' : '\u23f8 Pause'}
          </button>
          <button
            className="btn btn-sm btn-outline-danger"
            onClick={logout}
            aria-label="Logout"
          >
            Logout
          </button>
        </div>
      </nav>

      {/* Paused banner */}
      {isPaused && (
        <div
          className="alert alert-warning m-0 rounded-0 text-center py-1 small"
          role="status"
        >
          &#9888; Updates paused &mdash; {pendingCount} events buffered.
          <button
            className="btn btn-sm btn-warning ms-2 py-0"
            onClick={resume}
          >
            Resume
          </button>
        </div>
      )}

      {/* Main content */}
      <main
        className="container-fluid px-4 py-3"
        style={{ backgroundColor: 'var(--bs-body-bg, #0d1117)', minHeight: 'calc(100vh - 56px)' }}
      >
        {/* Row 1: Alerts (col-4) + Connections Table (col-8) */}
        <div className="row g-3 mb-3">
          {/* Alerts Panel — col-4 */}
          <div className="col-12 col-lg-4">
            <div
              className="card border-secondary h-100"
              style={{ backgroundColor: 'var(--bs-card-bg, #161b22)' }}
            >
              <div className="card-header border-secondary py-2">
                <span className="text-secondary small fw-semibold text-uppercase">
                  Active Alerts
                </span>
                {alerts.length > 0 && (
                  <span className="badge bg-danger ms-2">{alerts.length}</span>
                )}
              </div>
              <div className="card-body p-0">
                <AlertsPanel
                  alerts={alerts}
                  isInitialLoading={alertsLoading}
                  initialError={alertsError}
                  token={token}
                  onAlertActioned={handleAlertActioned}
                />
              </div>
            </div>
          </div>

          {/* Live Connections Table — col-8 */}
          <div className="col-12 col-lg-8">
            <div
              className="card border-secondary"
              style={{ backgroundColor: 'var(--bs-card-bg, #161b22)' }}
            >
              <div className="card-header border-secondary d-flex align-items-center justify-content-between py-2">
                <span className="text-secondary small fw-semibold text-uppercase">
                  Live Connections
                </span>
                {isPaused && (
                  <span className="badge bg-warning text-dark small">
                    Paused &mdash; {pendingCount} buffered
                  </span>
                )}
              </div>
              <div className="card-body p-0">
                <ConnectionsTable newEvents={pendingConnections} />
              </div>
            </div>
          </div>
        </div>

        {/* Row 2: Charts (col-6 each) */}
        <div className="row g-3">
          {/* Connections per App */}
          <div className="col-12 col-lg-6">
            <div
              className="card border-secondary"
              style={{ backgroundColor: 'var(--bs-card-bg, #161b22)' }}
            >
              <div className="card-header border-secondary py-2">
                <span className="text-secondary small fw-semibold text-uppercase">
                  Connections per App
                </span>
              </div>
              <div className="card-body p-2">
                <ConnectionsPerApp connections={connections} />
              </div>
            </div>
          </div>

          {/* Connections per Second */}
          <div className="col-12 col-lg-6">
            <div
              className="card border-secondary"
              style={{ backgroundColor: 'var(--bs-card-bg, #161b22)' }}
            >
              <div className="card-header border-secondary py-2">
                <span className="text-secondary small fw-semibold text-uppercase">
                  Connections per Second (rolling 60s)
                </span>
              </div>
              <div className="card-body p-2">
                <ConnectionsPerSecond batchCount={latestBatchSize} />
              </div>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
