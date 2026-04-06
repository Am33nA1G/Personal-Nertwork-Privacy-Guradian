// eslint-disable-next-line @typescript-eslint/no-unused-vars
import { render } from '@testing-library/react';

describe('AllowlistManager', () => {
  it.todo('renders existing rules from GET /api/v1/allowlist');
  it.todo('delete button calls DELETE /api/v1/allowlist/:rule_id');
  it.todo('removes rule from list after delete');
  it.todo('POST fires on add form submit with process_name and dst_hostname');
  it.todo('appends new rule to list on success');
});
