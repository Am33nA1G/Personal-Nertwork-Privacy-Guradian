import Head from 'next/head';
import Link from 'next/link';
import { useAuth } from '../hooks/useAuth';
import LoginPage from '../components/LoginPage';
import AllowlistManager from '../components/AllowlistManager';
import SuppressionsLog from '../components/SuppressionsLog';
import { ShieldIcon, ArrowLeftIcon, LogOutIcon, ListIcon, EyeOffIcon } from '../lib/icons';

export default function AllowlistPage() {
  const { token, needsSetup, loading, error, login, setup, logout } = useAuth();

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
        <title>PNPG — Allowlist Manager</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>

      {/* Navbar */}
      <nav className="pnpg-nav" aria-label="Main navigation">
        <div className="pnpg-nav-left">
          <div className="pnpg-nav-brand">
            <ShieldIcon className="pnpg-nav-logo" size={26} />
            <span className="pnpg-nav-wordmark">PNPG</span>
          </div>
          <div className="pnpg-nav-divider" />
          <span style={{ fontSize: '0.76rem', color: 'var(--tx-3)', fontWeight: 500 }}>
            Allowlist Manager
          </span>
        </div>

        <div className="pnpg-nav-actions">
          <Link href="/" className="btn-pnpg btn-ghost-dim">
            <ArrowLeftIcon size={13} />
            Dashboard
          </Link>
          <button className="btn-pnpg btn-danger-pnpg" onClick={logout} aria-label="Sign out">
            <LogOutIcon size={13} />
            Sign out
          </button>
        </div>
      </nav>

      {/* Main */}
      <main className="pnpg-main">
        <div className="row g-3 mb-3">
          <div className="col-12">
            <div className="panel-card">
              <div className="panel-header">
                <span className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <ListIcon size={13} />
                  Allowlist Rules
                </span>
                <span style={{ fontSize: '0.7rem', color: 'var(--tx-3)' }}>
                  Rules matching both process and destination suppress anomaly alerts
                </span>
              </div>
              <div className="panel-body">
                <AllowlistManager token={token} />
              </div>
            </div>
          </div>
        </div>

        <div className="row g-3">
          <div className="col-12">
            <div className="panel-card">
              <div className="panel-header">
                <span className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <EyeOffIcon size={13} />
                  Suppression Log
                </span>
                <span style={{ fontSize: '0.7rem', color: 'var(--tx-3)' }}>
                  Suppressed alerts — undo to restore
                </span>
              </div>
              <div className="panel-body">
                <SuppressionsLog token={token} />
              </div>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
