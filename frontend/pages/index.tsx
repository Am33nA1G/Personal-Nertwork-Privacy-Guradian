import Head from 'next/head';
import { useRef, useCallback, useState, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useWebSocket } from '../hooks/useWebSocket';
import LoginPage from '../components/LoginPage';
import WsStatusIndicator from '../components/WsStatusIndicator';
import ConnectionsTable from '../components/ConnectionsTable';
import AlertsPanel from '../components/AlertsPanel';
import type { ConnectionEvent, AlertEvent } from '../lib/types';
import type { WsBatchPayload } from '../hooks/useWebSocket';
import { apiAlerts } from '../lib/api';

export default function Dashboard() {
  const { token, needsSetup, loading, error, login, setup, logout } = useAuth();

  // --- Connections state ---
  const [pendingConnections, setPendingConnections] = useState<ConnectionEvent[]>([]);

  // --- Alerts state (owned by index.tsx per plan ownership decision) ---
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [alertsError, setAlertsError] = useState<string | null>(null);

  // --- Pause/Resume state ---
  const isPausedRef = useRef(false);
  const pausedBufferRef = useRef<ConnectionEvent[]>([]);
  const pausedAlertBufferRef = useRef<AlertEvent[]>([]);
  const [isPaused, setIsPaused] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);

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
    const connections = payload.connections ?? [];
    const newAlerts = payload.alerts ?? [];

    if (isPausedRef.current) {
      // Buffer while paused (cap at 500 to prevent unbounded growth)
      if (connections.length > 0) {
        pausedBufferRef.current = [
          ...pausedBufferRef.current,
          ...connections,
        ].slice(-500);
      }
      if (newAlerts.length > 0) {
        pausedAlertBufferRef.current = [
          ...pausedAlertBufferRef.current,
          ...newAlerts,
        ].slice(-200);
      }
      const total = pausedBufferRef.current.length + pausedAlertBufferRef.current.length;
      setPendingCount(total);
    } else {
      if (connections.length > 0) {
        setPendingConnections(connections);
      }
      if (newAlerts.length > 0) {
        setAlerts(prev => [...newAlerts, ...prev].slice(0, 200));
      }
    }
  }, []);

  const { status } = useWebSocket(token, handleBatch);

  function handlePauseToggle() {
    const nowPaused = !isPausedRef.current;
    isPausedRef.current = nowPaused;
    setIsPaused(nowPaused);

    if (!nowPaused) {
      // Flush buffered events on resume
      if (pausedBufferRef.current.length > 0) {
        setPendingConnections([...pausedBufferRef.current]);
        pausedBufferRef.current = [];
      }
      if (pausedAlertBufferRef.current.length > 0) {
        const flushed = [...pausedAlertBufferRef.current];
        setAlerts(prev => [...flushed, ...prev].slice(0, 200));
        pausedAlertBufferRef.current = [];
      }
      setPendingCount(0);
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
        <div className="d-flex align-items-center gap-2">
          <span
            style={{ fontSize: '1.4rem' }}
            role="img"
            aria-label="shield"
          >
            &#128737;
          </span>
          <span className="navbar-brand mb-0 h5 fw-semibold text-light me-3">PNPG</span>
          <WsStatusIndicator status={status} />
        </div>

        <div className="d-flex gap-2">
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
            onClick={handlePauseToggle}
          >
            Resume
          </button>
        </div>
      )}

      {/* Main content */}
      <main
        className="container-fluid py-3"
        style={{ backgroundColor: 'var(--bs-body-bg, #0d1117)', minHeight: 'calc(100vh - 56px)' }}
      >
        <div className="row g-3">
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
                    Paused &mdash; buffering events
                  </span>
                )}
              </div>
              <div className="card-body p-0">
                <ConnectionsTable newEvents={pendingConnections} />
              </div>
            </div>
          </div>

          {/* Charts, AllowlistManager added in 06-03 */}
        </div>
      </main>
    </>
  );
}
