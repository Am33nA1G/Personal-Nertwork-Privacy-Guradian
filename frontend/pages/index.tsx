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
import ThreatsPanel from '../components/ThreatsPanel';
import {
  ShieldIcon, PauseIcon, PlayIcon, LogOutIcon,
  ListIcon, AlertTriangleIcon, ZapIcon, ActivityIcon,
} from '../lib/icons';
import type { ConnectionEvent, AlertEvent, ThreatEvent } from '../lib/types';
import type { WsBatchPayload } from '../hooks/useWebSocket';
import { apiAlerts, apiThreats } from '../lib/api';

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

  const [pendingConnections, setPendingConnections] = useState<ConnectionEvent[]>([]);
  const [connections, setConnections] = useState<ConnectionEvent[]>([]);
  const [latestBatchSize, setLatestBatchSize] = useState(0);

  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [alertsError, setAlertsError] = useState<string | null>(null);

  const [threats, setThreats] = useState<ThreatEvent[]>([]);
  const [threatsLoading, setThreatsLoading] = useState(false);
  const [threatsError, setThreatsError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<'alerts' | 'threats'>('alerts');

  useEffect(() => {
    if (!token) return;
    setAlertsLoading(true);
    setAlertsError(null);
    apiAlerts(token, 'active')
      .then(res => setAlerts(res?.data ?? []))
      .catch(() => setAlertsError('Failed to load alerts'))
      .finally(() => setAlertsLoading(false));
  }, [token]);

  useEffect(() => {
    if (!token) return;
    setThreatsLoading(true);
    setThreatsError(null);
    apiThreats(token, 'active')
      .then(res => setThreats(res?.data ?? []))
      .catch(() => setThreatsError('Failed to load threats'))
      .finally(() => setThreatsLoading(false));
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
    if (isPaused) resume(); else pause();
  }

  function handleAlertActioned(alertId: string) {
    setAlerts(prev => prev.filter(a => a.alert_id !== alertId));
  }

  function handleThreatActioned(threatId: string) {
    setThreats(prev => prev.filter(t => t.threat_id !== threatId));
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

  const hasAlerts  = alerts.length > 0;
  const hasThreats = threats.length > 0;

  return (
    <>
      <Head>
        <title>PNPG — Network Privacy Guardian</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      {/* ── Navbar ── */}
      <nav className="pnpg-nav" aria-label="Main navigation">
        <div className="pnpg-nav-left">
          {/* Brand */}
          <div className="pnpg-nav-brand">
            <ShieldIcon className="pnpg-nav-logo" size={26} />
            <span className="pnpg-nav-wordmark">PNPG</span>
          </div>

          <div className="pnpg-nav-divider" />

          {/* Status pills */}
          <div className="pnpg-nav-status">
            <WsStatusIndicator status={status} />
            <CaptureStatus token={token} />
          </div>
        </div>

        {/* Actions */}
        <div className="pnpg-nav-actions">
          <Link href="/allowlist" className="btn-pnpg btn-ghost-dim" style={{ gap: 5 }}>
            <ListIcon size={13} />
            Allowlist
          </Link>

          <button
            className={`btn-pnpg ${isPaused ? 'btn-paused' : 'btn-ghost'}`}
            onClick={handlePauseToggle}
            aria-pressed={isPaused}
            aria-label={isPaused ? 'Resume live updates' : 'Pause live updates'}
          >
            {isPaused ? (
              <>
                <PlayIcon size={12} />
                Resume
                {pendingCount > 0 && (
                  <span style={{
                    fontSize: '0.62rem',
                    background: 'rgba(0,0,0,0.25)',
                    borderRadius: '100px',
                    padding: '1px 6px',
                    fontWeight: 700,
                  }}>
                    {pendingCount}
                  </span>
                )}
              </>
            ) : (
              <>
                <PauseIcon size={12} />
                Pause
              </>
            )}
          </button>

          <button
            className="btn-pnpg btn-danger-pnpg"
            onClick={logout}
            aria-label="Sign out"
          >
            <LogOutIcon size={13} />
            Sign out
          </button>
        </div>
      </nav>

      {/* ── Paused banner ── */}
      {isPaused && (
        <div className="pause-banner" role="status">
          <PauseIcon size={12} />
          <span>Live updates paused — <strong>{pendingCount}</strong> events buffered</span>
          <button className="btn-pnpg btn-warning-solid" onClick={resume} style={{ padding: '3px 10px', fontSize: '0.72rem' }}>
            <PlayIcon size={11} />
            Resume
          </button>
        </div>
      )}

      {/* ── Main ── */}
      <main className="pnpg-main">

        {/* KPI Strip */}
        <div className="kpi-strip">
          <div className="kpi-card">
            <span className="kpi-label">Connections</span>
            <span className="kpi-value">{connections.length}</span>
            <span className="kpi-sub">last 500 buffered</span>
          </div>

          <div className="kpi-card">
            <span className="kpi-label">Active Alerts</span>
            <span className={`kpi-value ${hasAlerts ? 'kpi-danger' : ''}`}>
              {alerts.length}
            </span>
            <span className="kpi-sub">{hasAlerts ? 'require attention' : 'all clear'}</span>
          </div>

          <div className="kpi-card">
            <span className="kpi-label">Active Threats</span>
            <span className={`kpi-value ${hasThreats ? 'kpi-danger' : ''}`}>
              {threats.length}
            </span>
            <span className="kpi-sub">{hasThreats ? 'action needed' : 'none detected'}</span>
          </div>

          <div className="kpi-card">
            <span className="kpi-label">Batch Rate</span>
            <span className={`kpi-value ${latestBatchSize > 0 ? 'kpi-live' : ''}`}>
              {latestBatchSize}
            </span>
            <span className="kpi-sub">events / batch</span>
          </div>
        </div>

        {/* Row 1: Alert/Threat tabs + Live Connections */}
        <div className="row g-3 mb-3">

          {/* Alert / Threat tabs — col-4 */}
          <div className="col-12 col-lg-4">
            <div className="panel-card" style={{ height: 480 }}>
              {/* Tabs header */}
              <div className="pnpg-tabs" role="tablist">
                <button
                  role="tab"
                  aria-selected={activeTab === 'alerts'}
                  className={`pnpg-tab ${activeTab === 'alerts' ? 'tab-active' : ''}`}
                  onClick={() => setActiveTab('alerts')}
                >
                  <AlertTriangleIcon size={13} />
                  Alerts
                  {alerts.length > 0 && (
                    <span className="tab-count">{alerts.length}</span>
                  )}
                </button>
                <button
                  role="tab"
                  aria-selected={activeTab === 'threats'}
                  className={`pnpg-tab ${activeTab === 'threats' ? 'tab-active' : ''}`}
                  onClick={() => setActiveTab('threats')}
                >
                  <ZapIcon size={13} />
                  Threats
                  {threats.length > 0 && (
                    <span className="tab-count">{threats.length}</span>
                  )}
                </button>
              </div>

              {/* Tab content */}
              <div className="panel-body" style={{ overflowY: 'auto' }}>
                {activeTab === 'alerts' && (
                  <AlertsPanel
                    alerts={alerts}
                    isInitialLoading={alertsLoading}
                    initialError={alertsError}
                    token={token}
                    onAlertActioned={handleAlertActioned}
                  />
                )}
                {activeTab === 'threats' && (
                  <ThreatsPanel
                    threats={threats}
                    isInitialLoading={threatsLoading}
                    initialError={threatsError}
                    token={token}
                    onThreatActioned={handleThreatActioned}
                  />
                )}
              </div>
            </div>
          </div>

          {/* Live Connections — col-8 */}
          <div className="col-12 col-lg-8">
            <div className="panel-card" style={{ height: 480 }}>
              <div className="panel-header">
                <span className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <ActivityIcon size={13} />
                  Live Connections
                </span>
                {isPaused && (
                  <span className="status-pill pill-connecting">
                    <span className="status-dot" />
                    Paused — {pendingCount} buffered
                  </span>
                )}
              </div>
              <div className="panel-body" style={{ overflow: 'hidden' }}>
                <ConnectionsTable newEvents={pendingConnections} />
              </div>
            </div>
          </div>
        </div>

        {/* Row 2: Charts */}
        <div className="row g-3">
          <div className="col-12 col-lg-6">
            <div className="panel-card">
              <div className="panel-header">
                <span className="panel-title">Connections per App</span>
              </div>
              <div style={{ padding: '8px 4px 4px' }}>
                <ConnectionsPerApp connections={connections} />
              </div>
            </div>
          </div>

          <div className="col-12 col-lg-6">
            <div className="panel-card">
              <div className="panel-header">
                <span className="panel-title">Connection Rate — rolling 60s</span>
              </div>
              <div style={{ padding: '8px 4px 4px' }}>
                <ConnectionsPerSecond batchCount={latestBatchSize} />
              </div>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
