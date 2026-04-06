import Head from 'next/head';
import { useRef, useCallback, useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { useWebSocket } from '../hooks/useWebSocket';
import LoginPage from '../components/LoginPage';
import WsStatusIndicator from '../components/WsStatusIndicator';
import ConnectionsTable from '../components/ConnectionsTable';
import type { ConnectionEvent } from '../lib/types';
import type { WsBatchPayload } from '../hooks/useWebSocket';

export default function Dashboard() {
  const { token, needsSetup, loading, error, login, setup, logout } = useAuth();
  const [pendingConnections, setPendingConnections] = useState<ConnectionEvent[]>([]);
  const isPausedRef = useRef(false);
  const pausedBufferRef = useRef<ConnectionEvent[]>([]);
  const [isPaused, setIsPaused] = useState(false);

  const handleBatch = useCallback((payload: WsBatchPayload) => {
    const connections = payload.connections ?? [];
    if (connections.length === 0) return;

    if (isPausedRef.current) {
      // Buffer while paused (cap buffer at 500 to avoid unbounded growth)
      pausedBufferRef.current = [
        ...pausedBufferRef.current,
        ...connections,
      ].slice(-500);
    } else {
      setPendingConnections(connections);
    }
  }, []);

  const { status } = useWebSocket(token, handleBatch);

  function handlePauseToggle() {
    const nowPaused = !isPausedRef.current;
    isPausedRef.current = nowPaused;
    setIsPaused(nowPaused);

    if (!nowPaused && pausedBufferRef.current.length > 0) {
      // Flush buffered events on resume
      setPendingConnections([...pausedBufferRef.current]);
      pausedBufferRef.current = [];
    }
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
        <title>PNPG \u2014 Network Privacy Guardian</title>
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

      {/* Main content */}
      <main
        className="container-fluid py-3"
        style={{ backgroundColor: 'var(--bs-body-bg, #0d1117)', minHeight: 'calc(100vh - 56px)' }}
      >
        <div className="row g-3">
          <div className="col-12">
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
                    Paused \u2014 buffering events
                  </span>
                )}
              </div>
              <div className="card-body p-0">
                <ConnectionsTable newEvents={pendingConnections} />
              </div>
            </div>
          </div>
          {/* Charts, AlertsPanel, AllowlistManager added in 06-02 and 06-03 */}
        </div>
      </main>
    </>
  );
}
