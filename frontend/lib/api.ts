const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? '';

function authHeaders(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
}

export async function apiLogin(password: string) {
  const res = await fetch(`${BASE_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  });
  return res.json();
}

export async function apiSetup(password: string) {
  const res = await fetch(`${BASE_URL}/api/v1/auth/setup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
  });
  return res.json();
}

export async function apiHealth() {
  const res = await fetch(`${BASE_URL}/api/v1/health`);
  return res.json();
}

export async function apiConnections(token: string, page = 1, pageSize = 50) {
  const res = await fetch(
    `${BASE_URL}/api/v1/connections?page=${page}&page_size=${pageSize}`,
    { headers: authHeaders(token) }
  );
  return res.json();
}

export async function apiAlerts(token: string, status?: string) {
  const params = status ? `?status=${status}` : '';
  const res = await fetch(`${BASE_URL}/api/v1/alerts${params}`, {
    headers: authHeaders(token),
  });
  return res.json();
}

export async function apiPatchAlert(
  token: string,
  alertId: string,
  action: 'suppress' | 'resolve',
  reason?: string
) {
  const res = await fetch(`${BASE_URL}/api/v1/alerts/${alertId}`, {
    method: 'PATCH',
    headers: authHeaders(token),
    body: JSON.stringify({ action, reason }),
  });
  return res.json();
}

export async function apiGetAllowlist(token: string) {
  const res = await fetch(`${BASE_URL}/api/v1/allowlist`, { headers: authHeaders(token) });
  return res.json();
}

export async function apiCreateAllowlistRule(
  token: string,
  rule: {
    process_name?: string;
    dst_ip?: string;
    dst_hostname?: string;
    expires_at?: string;
    reason?: string;
  }
) {
  const res = await fetch(`${BASE_URL}/api/v1/allowlist`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(rule),
  });
  return res.json();
}

export async function apiDeleteAllowlistRule(token: string, ruleId: string) {
  const res = await fetch(`${BASE_URL}/api/v1/allowlist/${ruleId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  return res.json();
}

export async function apiGetSuppressions(token: string) {
  const res = await fetch(`${BASE_URL}/api/v1/suppressions`, { headers: authHeaders(token) });
  return res.json();
}

export async function apiDeleteSuppression(token: string, suppressionId: string) {
  const res = await fetch(`${BASE_URL}/api/v1/suppressions/${suppressionId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  return res.json();
}

export async function apiStatsSummary(token: string) {
  const res = await fetch(`${BASE_URL}/api/v1/stats/summary`, { headers: authHeaders(token) });
  return res.json();
}

export async function apiStatus(token: string) {
  const res = await fetch(`${BASE_URL}/api/v1/status`, { headers: authHeaders(token) });
  return res.json();
}

export async function apiThreats(token: string, status?: string) {
  const params = status ? `?status=${status}` : '';
  const res = await fetch(`${BASE_URL}/api/v1/threats${params}`, {
    headers: authHeaders(token),
  });
  return res.json();
}

export async function apiRemediateThreat(
  token: string,
  pid: number,
  action: 'kill' | 'block_ip',
  reason?: string
) {
  const endpoint = action === 'kill' ? 'kill' : 'block-ip';
  const res = await fetch(`${BASE_URL}/api/v1/threats/${pid}/${endpoint}`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ action, reason }),
  });
  return res.json();
}
