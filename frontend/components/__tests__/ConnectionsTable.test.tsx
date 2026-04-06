import { render } from '@testing-library/react';

describe('ConnectionsTable', () => {
  it.todo('renders correct column headers: Time, App, Domain, Country, ASN, IP, Port, Protocol');
  it.todo('renders flag emoji in Country column');
  it.todo('injects a new row into tbody on delta push');
  it.todo('does not exceed MAX_ROWS after overflow push');
  it.todo('marks blocklisted connections with table-danger class');
});
