import { useState, FormEvent } from 'react';

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
    <div
      className="d-flex align-items-center justify-content-center vh-100"
      style={{ backgroundColor: 'var(--bs-body-bg, #0d1117)' }}
    >
      <div style={{ width: '100%', maxWidth: '400px' }}>
        {/* Login Card */}
        <div className="card border-0 shadow-lg" style={{ backgroundColor: 'var(--bs-card-bg, #161b22)' }}>
          <div className="card-body p-4">
            <div className="text-center mb-4">
              <span style={{ fontSize: '2.5rem' }} role="img" aria-label="shield">
                &#128737;
              </span>
              <h4 className="mt-2 mb-0 text-light fw-semibold">PNPG</h4>
              <p className="text-secondary small mb-0">Network Privacy Guardian</p>
            </div>

            <form onSubmit={handleLogin} noValidate>
              <div className="mb-3">
                <label htmlFor="login-password" className="form-label text-secondary small">
                  Password
                </label>
                <input
                  id="login-password"
                  type="password"
                  className="form-control bg-dark border-secondary text-light"
                  placeholder="Enter password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  disabled={loading}
                  required
                  autoFocus
                />
              </div>

              {error && (
                <div className="alert alert-danger py-2 small" role="alert">
                  {error}
                </div>
              )}

              <button
                type="submit"
                className="btn btn-primary w-100"
                disabled={loading || !loginPassword}
              >
                {loading ? (
                  <>
                    <span
                      className="spinner-border spinner-border-sm me-2"
                      role="status"
                      aria-hidden="true"
                    />
                    Signing in...
                  </>
                ) : (
                  'Sign In'
                )}
              </button>
            </form>
          </div>
        </div>

        {/* First-run setup section (shown only after 503 response) */}
        {needsSetup && (
          <div
            className="card border-warning mt-3 shadow-lg"
            style={{ backgroundColor: 'var(--bs-card-bg, #161b22)' }}
          >
            <div className="card-body p-4">
              <h6 className="text-warning mb-3">
                <span role="img" aria-label="warning">&#9888;</span> First-run Setup
              </h6>
              <p className="text-secondary small mb-3">
                No password has been configured yet. Set a password to secure the dashboard.
              </p>

              <form onSubmit={handleSetup} noValidate>
                <div className="mb-3">
                  <label htmlFor="setup-password" className="form-label text-secondary small">
                    New Password
                  </label>
                  <input
                    id="setup-password"
                    type="password"
                    className="form-control bg-dark border-secondary text-light"
                    placeholder="Minimum 8 characters"
                    value={setupPassword}
                    onChange={(e) => setSetupPassword(e.target.value)}
                    disabled={loading}
                    required
                    minLength={8}
                  />
                </div>

                <div className="mb-3">
                  <label htmlFor="setup-confirm" className="form-label text-secondary small">
                    Confirm Password
                  </label>
                  <input
                    id="setup-confirm"
                    type="password"
                    className="form-control bg-dark border-secondary text-light"
                    placeholder="Repeat password"
                    value={setupConfirm}
                    onChange={(e) => setSetupConfirm(e.target.value)}
                    disabled={loading}
                    required
                  />
                </div>

                {setupError && (
                  <div className="alert alert-danger py-2 small" role="alert">
                    {setupError}
                  </div>
                )}

                <button
                  type="submit"
                  className="btn btn-warning w-100"
                  disabled={loading || !setupPassword || !setupConfirm}
                >
                  {loading ? (
                    <>
                      <span
                        className="spinner-border spinner-border-sm me-2"
                        role="status"
                        aria-hidden="true"
                      />
                      Setting up...
                    </>
                  ) : (
                    'Set Password and Continue'
                  )}
                </button>
              </form>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
