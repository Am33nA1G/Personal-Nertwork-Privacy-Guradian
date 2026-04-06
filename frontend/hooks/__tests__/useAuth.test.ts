import { renderHook } from '@testing-library/react';

describe('useAuth', () => {
  it.todo('returns null token on initial load if sessionStorage is empty');
  it.todo('calls POST /api/v1/auth/login with password');
  it.todo('stores access_token in sessionStorage on login success');
});
