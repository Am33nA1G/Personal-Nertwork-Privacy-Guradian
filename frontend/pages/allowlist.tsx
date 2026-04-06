import Head from 'next/head';
import Link from 'next/link';
import { useAuth } from '../hooks/useAuth';
import LoginPage from '../components/LoginPage';
import AllowlistManager from '../components/AllowlistManager';
import SuppressionsLog from '../components/SuppressionsLog';

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
        <title>PNPG &mdash; Allowlist Manager</title>
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
          <span className="navbar-brand mb-0 h5 fw-semibold text-light">PNPG</span>
        </div>

        <div className="d-flex align-items-center gap-2">
          <Link href="/" className="btn btn-sm btn-outline-secondary">
            &#8592; Dashboard
          </Link>
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
        className="container-fluid px-4 py-3"
        style={{ backgroundColor: 'var(--bs-body-bg, #0d1117)', minHeight: 'calc(100vh - 56px)' }}
      >
        {/* Allowlist Manager */}
        <div className="row g-3 mb-4">
          <div className="col-12">
            <div
              className="card border-secondary"
              style={{ backgroundColor: 'var(--bs-card-bg, #161b22)' }}
            >
              <div className="card-header border-secondary py-2">
                <h5 className="mb-0 fw-semibold text-light" style={{ fontSize: '1rem' }}>
                  Allowlist Manager
                </h5>
                <p className="mb-0 text-secondary small">
                  Rules matching both process and destination suppress anomaly alerts.
                </p>
              </div>
              <div className="card-body p-0">
                <AllowlistManager token={token} />
              </div>
            </div>
          </div>
        </div>

        {/* Suppressions Log */}
        <div className="row g-3">
          <div className="col-12">
            <div
              className="card border-secondary"
              style={{ backgroundColor: 'var(--bs-card-bg, #161b22)' }}
            >
              <div className="card-header border-secondary py-2">
                <h5 className="mb-0 fw-semibold text-light" style={{ fontSize: '1rem' }}>
                  Suppression Log
                </h5>
                <p className="mb-0 text-secondary small">
                  Alerts that have been suppressed. Undo removes the suppression.
                </p>
              </div>
              <div className="card-body p-0">
                <SuppressionsLog token={token} />
              </div>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
