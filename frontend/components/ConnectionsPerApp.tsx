import { useMemo } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import type { ConnectionEvent } from '../lib/types';

interface Props {
  connections: ConnectionEvent[];
}

const DARK_TOOLTIP_STYLE = {
  backgroundColor: '#1a1a2e',
  border: '1px solid #30363d',
  color: '#c9d1d9',
  fontSize: '0.8rem',
};

const TICK_STYLE = { fill: '#8b949e', fontSize: '0.75rem' };

function truncate(name: string, max = 20): string {
  return name.length > max ? name.slice(0, max - 1) + '\u2026' : name;
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
      <p className="text-muted text-center py-3 mb-0 small">No connection data yet</p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#30363d" vertical={false} />
        <XAxis
          dataKey="name"
          tick={TICK_STYLE}
          axisLine={{ stroke: '#30363d' }}
          tickLine={false}
          interval={0}
        />
        <YAxis
          tick={TICK_STYLE}
          axisLine={{ stroke: '#30363d' }}
          tickLine={false}
          width={32}
          allowDecimals={false}
        />
        <Tooltip
          contentStyle={DARK_TOOLTIP_STYLE}
          cursor={{ fill: 'rgba(255,255,255,0.05)' }}
          formatter={(value: number) => [value, 'Connections']}
        />
        <Bar dataKey="count" fill="#58a6ff" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
