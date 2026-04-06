// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { render } from '@testing-library/react';

describe('CaptureStatus', () => {
  it.todo('renders Active badge when API returns capture:running');
  it.todo('shows probe_type in the badge text');
  it.todo('shows error state when poll request fails (backend unreachable)');
  it.todo('does not render a Stopped badge (backend does not emit stopped while alive)');
});
