import { useRef, useEffect } from 'react';
import type { ConnectionEvent } from '../lib/types';
import { countryFlag } from '../lib/countryFlag';

const MAX_ROWS = 500;

interface ConnectionsTableProps {
  newEvents: ConnectionEvent[];
}

function formatTime(isoString: string): string {
  try {
    return new Date(isoString).toLocaleTimeString();
  } catch {
    return isoString;
  }
}

function buildRow(conn: ConnectionEvent): HTMLTableRowElement {
  const tr = document.createElement('tr');
  tr.className = conn.threat_intel?.is_blocklisted ? 'table-danger' : '';

  const cells: string[] = [
    formatTime(conn.timestamp),
    conn.process_name,
    conn.dst_hostname ?? conn.dst_ip,
    countryFlag(conn.dst_country),
    conn.dst_asn ?? '\u2014',
    conn.dst_ip,
    String(conn.dst_port),
    conn.protocol,
  ];

  for (const text of cells) {
    const td = document.createElement('td');
    td.textContent = text;
    tr.appendChild(td);
  }

  return tr;
}

export default function ConnectionsTable({ newEvents }: ConnectionsTableProps) {
  const tbodyRef = useRef<HTMLTableSectionElement>(null);
  const rowCountRef = useRef(0);

  useEffect(() => {
    const tbody = tbodyRef.current;
    if (!tbody || !newEvents || newEvents.length === 0) return;

    // Inject new rows at the top (prepend = newest first)
    const fragment = document.createDocumentFragment();
    for (const conn of newEvents) {
      fragment.appendChild(buildRow(conn));
      rowCountRef.current += 1;
    }
    tbody.insertBefore(fragment, tbody.firstChild);

    // Trim excess rows from the bottom
    while (rowCountRef.current > MAX_ROWS && tbody.lastChild) {
      tbody.removeChild(tbody.lastChild);
      rowCountRef.current -= 1;
    }
  }, [newEvents]);

  return (
    <div className="table-responsive">
      <table
        className="table table-dark table-hover table-sm table-live mb-0"
        aria-label="Live connections"
      >
        <thead className="sticky-top">
          <tr>
            <th scope="col">Time</th>
            <th scope="col">App</th>
            <th scope="col">Domain</th>
            <th scope="col">Country</th>
            <th scope="col">ASN</th>
            <th scope="col">IP</th>
            <th scope="col">Port</th>
            <th scope="col">Protocol</th>
          </tr>
        </thead>
        <tbody ref={tbodyRef} />
      </table>
    </div>
  );
}
