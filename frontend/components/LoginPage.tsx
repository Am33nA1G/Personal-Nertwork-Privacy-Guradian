import { useState, FormEvent } from 'react';
import { ShieldIcon, AlertTriangleIcon } from '../lib/icons';

interface LoginPageProps {
  onLogin: (password: string) => Promise<void>;
  onSetup: (password: string) => Promise<void>;
  needsSetup: boolean;
  loading: boolean;
  error: string | null;
}

export default function LoginPage({
  onLogin,
  onSetup,
  needsSetup,
  loading,
  error,
}: LoginPageProps) {
  const [loginPassword, setLoginPassword] = useState('');
  const [setupPassword, setSetupPassword] = useState('');
  const [setupConfirm, setSetupConfirm] = useState('');
  const [setupError, setSetupError] = useState<string | null>(null);

  function handleLogin(e: FormEvent) {
    e.preventDefault();
    onLogin(loginPassword);
  }

  function handleSetup(e: FormEvent) {
    e.preventDefault();
    if (setupPassword !== setupConfirm) {
      setSetupError('Passwords do not match');
      return;
    }
    if (setupPassword.length < 8) {
      setSetupError('Password must be at least 8 characters');
      return;
    }
    setSetupError(null);
    onSetup(setupPassword);
  }

  return (
    <div className="login-page">
      {/* Main login card */}
      <div className="login-card">
        {/* Logo */}
        <div className="login-logo-wrap">
          <ShieldIcon size={26} />
        </div>

        <h1 className="login-title">PNPG</h1>
        <p className="login-subtitle">Network Privacy Guardian</p>

        <form onSubmit={handleLogin} noValidate>
          <div style={{ marginBottom: 16 }}>
            <label htmlFor="login-password" className="pnpg-label">
              Password
            </label>
            <input
              id="login-password"
              type="password"
              className="pnpg-input"
              placeholder="Enter your password"
              value={loginPassword}
              onChange={(e) => setLoginPassword(e.target.value)}
              disabled={loading}
              required
              autoFocus
            />
          </div>

          {error && (
            <div className="login-error" role="alert">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn-pnpg btn-primary-pnpg"
            style={{ width: '100%', justifyContent: 'center', padding: '9px 16px', fontSize: '0.84rem' }}
            disabled={loading || !loginPassword}
          >
            {loading ? (
              <>
                <span className="spinner-xs" />
                Signing in…
              </>
            ) : (
              'Sign In'
            )}
          </button>
        </form>
      </div>

      {/* First-run setup card */}
      {needsSetup && (
        <div className="login-setup-card">
          <div className="login-setup-title">
            <AlertTriangleIcon size={15} />
            First-run Setup
          </div>
          <p className="login-setup-desc">
            No password configured yet. Set one to secure the dashboard.
          </p>

          <form onSubmit={handleSetup} noValidate>
            <div style={{ marginBottom: 12 }}>
              <label htmlFor="setup-password" className="pnpg-label">
                New Password
              </label>
              <input
                id="setup-password"
                type="password"
                className="pnpg-input"
                placeholder="Minimum 8 characters"
                value={setupPassword}
                onChange={(e) => setSetupPassword(e.target.value)}
                disabled={loading}
                required
                minLength={8}
              />
            </div>

            <div style={{ marginBottom: 14 }}>
              <label htmlFor="setup-confirm" className="pnpg-label">
                Confirm Password
              </label>
              <input
                id="setup-confirm"
                type="password"
                className="pnpg-input"
                placeholder="Repeat password"
                value={setupConfirm}
                onChange={(e) => setSetupConfirm(e.target.value)}
                disabled={loading}
                required
              />
            </div>

            {setupError && (
              <div className="login-error" role="alert">
                {setupError}
              </div>
            )}

            <button
              type="submit"
              className="btn-pnpg btn-warning-solid"
              style={{ width: '100%', justifyContent: 'center', padding: '9px 16px', fontSize: '0.84rem' }}
              disabled={loading || !setupPassword || !setupConfirm}
            >
              {loading ? (
                <>
                  <span className="spinner-xs" />
                  Setting up…
                </>
              ) : (
                'Set Password & Continue'
              )}
            </button>
          </form>
        </div>
      )}
    </div>
  );
}
