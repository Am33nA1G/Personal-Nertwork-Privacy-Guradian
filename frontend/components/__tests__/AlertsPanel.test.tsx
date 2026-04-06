// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import AlertsPanel from '../AlertsPanel';
// eslint-disable-next-line @typescript-eslint/no-unused-vars
import type { AlertEvent } from '../../lib/types';

describe('AlertsPanel', () => {
  it.todo('renders each alert with its reason text');
  it.todo('applies text-warning class for WARNING severity');
  it.todo('applies text-pnpg-alert class for ALERT/HIGH severity');
  it.todo('applies text-danger class for CRITICAL severity');
  it.todo('calls PATCH suppress on Suppress button click');
  it.todo('calls PATCH resolve on Resolve button click');
  it.todo('removes alert from list after successful action');
  it.todo('shows spinner in button while action is pending');
});
