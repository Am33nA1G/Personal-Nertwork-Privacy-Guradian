import { useRef, useEffect } from 'react';
import type { ConnectionEvent } from '../lib/types';
import { countryFlag } from '../lib/countryFlag';

const MAX_ROWS = 500;

interface Props {
  newEvents: ConnectionEvent[];
}

function formatTime(iso: string): string {
  try { return new Date(iso).toLocaleTimeString(); } catch { return iso; }
}

function buildRow(conn: ConnectionEvent): HTMLTableRowElement {
  const tr = document.createElement('tr');
  if (conn.threat_intel?.is_blocklisted) tr.className = 'row-threat';

  const cells: Array<{ text: string; cls: string }> = [
    { text: formatTime(conn.timestamp),              cls: 'cell-time' },
    { text: conn.process_name,                       cls: 'cell-app' },
    { text: conn.dst_hostname ?? conn.dst_ip,        cls: 'cell-domain' },
    { text: countryFlag(conn.dst_country),           cls: 'cell-flag' },
    { text: conn.dst_asn ?? '\u2014',                cls: 'cell-mono' },
    { text: conn.dst_ip,                             cls: 'cell-mono' },
    { text: String(conn.dst_port),                   cls: 'cell-mono' },
    { text: conn.protocol,                           cls: 'cell-proto' },
  ];

  for (const { text, cls } of cells) {
    const td = document.createElement('td');
    td.textContent = text;
    td.className = cls;
    tr.appendChild(td);
  }

  return tr;
}

export default function ConnectionsTable({ newEvents }: Props) {
  const tbodyRef   = useRef<HTMLTableSectionElement>(null);
  const rowCountRef = useRef(0);

  useEffect(() => {
    const tbody = tbodyRef.current;
    if (!tbody || !newEvents || newEvents.length === 0) return;

    const fragment = document.createDocumentFragment();
    for (const conn of newEvents) {
      fragment.appendChild(buildRow(conn));
      rowCountRef.current += 1;
    }
    tbody.insertBefore(fragment, tbody.firstChild);

    while (rowCountRef.current > MAX_ROWS && tbody.lastChild) {
      tbody.removeChild(tbody.lastChild);
      rowCountRef.current -= 1;
    }
  }, [newEvents]);

  return (
    <div style={{ height: '100%', overflowX: 'auto', overflowY: 'auto' }}>
      <table className="table-live" aria-label="Live connections">
        <thead>
          <tr>
            <th scope="col">Time</th>
            <th scope="col">Application</th>
            <th scope="col">Domain / IP</th>
            <th scope="col">Country</th>
            <th scope="col">ASN</th>
            <th scope="col">IP</th>
            <th scope="col">Port</th>
            <th scope="col">Proto</th>
          </tr>
        </thead>
        <tbody ref={tbodyRef} />
      </table>
    </div>
  );
}
