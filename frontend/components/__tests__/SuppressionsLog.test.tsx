// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

describe('SuppressionsLog', () => {
  it.todo('renders a suppression entry row with rule_id and scope');
  it.todo('undo button calls DELETE /api/v1/suppressions/:id');
  it.todo('removes entry from list after undo');
  it.todo('shows empty state when no suppressions');
});
