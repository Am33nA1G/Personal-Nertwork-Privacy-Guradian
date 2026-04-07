import { useMemo } from 'react';
import {
  ResponsiveContainer, BarChart, Bar,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts';
import type { ConnectionEvent } from '../lib/types';

interface Props {
  connections: ConnectionEvent[];
}

const GRID_COLOR   = 'rgba(255,255,255,0.05)';
const AXIS_COLOR   = 'rgba(255,255,255,0.06)';
const TICK_STYLE   = { fill: '#445068', fontSize: 11, fontFamily: 'var(--font-sans, Inter, sans-serif)' };
const TOOLTIP_STYLE = {
  background: '#111827',
  border: '1px solid rgba(255,255,255,0.09)',
  borderRadius: 8,
  color: '#eef2ff',
  fontSize: 12,
  fontFamily: 'var(--font-sans, Inter, sans-serif)',
  boxShadow: '0 4px 20px rgba(0,0,0,0.6)',
};

function truncate(s: string, max = 18): string {
  return s.length > max ? s.slice(0, max - 1) + '…' : s;
}

export default function ConnectionsPerApp({ connections }: Props) {
  const data = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const c of connections) {
      const key = c.process_name || 'unknown';
      counts[key] = (counts[key] ?? 0) + 1;
    }
    return Object.entries(counts)
      .map(([name, count]) => ({ name: truncate(name), count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  }, [connections]);

  if (data.length === 0) {
    return (
      <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontSize: '0.76rem', color: 'var(--tx-3)' }}>No connection data yet</span>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 4, right: 12, bottom: 4, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} vertical={false} />
        <XAxis
          dataKey="name"
          tick={TICK_STYLE}
          axisLine={{ stroke: AXIS_COLOR }}
          tickLine={false}
          interval={0}
        />
        <YAxis
          tick={TICK_STYLE}
          axisLine={{ stroke: AXIS_COLOR }}
          tickLine={false}
          width={30}
          allowDecimals={false}
        />
        <Tooltip
          contentStyle={TOOLTIP_STYLE}
          cursor={{ fill: 'rgba(99,102,241,0.07)' }}
          formatter={(value: number) => [value, 'Connections']}
        />
        <Bar
          dataKey="count"
          fill="#6366f1"
          radius={[3, 3, 0, 0]}
          maxBarSize={40}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
