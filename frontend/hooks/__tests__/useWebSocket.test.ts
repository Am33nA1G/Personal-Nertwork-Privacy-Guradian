import { renderHook } from '@testing-library/react';

describe('useWebSocket', () => {
  it.todo('connects when token is provided');
  it.todo('does not connect when token is null');
  it.todo('reconnects with exponential backoff after close');
  it.todo('backoff delay doubles from 1s to max 30s');
  it.todo('resets attempt counter on successful connect');
  it.todo('returns status: connected after onopen');
  it.todo('returns status: disconnected after close');
});
