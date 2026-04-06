import { useRef, useState, useEffect } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';

interface Props {
  batchCount: number;
}

interface DataPoint {
  ts: number;
  count: number;
}

const DARK_TOOLTIP_STYLE = {
  backgroundColor: '#1a1a2e',
  border: '1px solid #30363d',
  color: '#c9d1d9',
  fontSize: '0.8rem',
};

const TICK_STYLE = { fill: '#8b949e', fontSize: '0.75rem' };

export default function ConnectionsPerSecond({ batchCount }: Props) {
  const bufferRef = useRef<DataPoint[]>([]);
  const [chartData, setChartData] = useState<DataPoint[]>([]);

  // Push new batch entry whenever batchCount changes
  useEffect(() => {
    if (batchCount > 0) {
      bufferRef.current = [...bufferRef.current, { ts: Date.now(), count: batchCount }];
    }
  }, [batchCount]);

  // 1Hz interval: trim >60s entries and sync state
  useEffect(() => {
    const id = setInterval(() => {
      const cutoff = Date.now() - 60_000;
      bufferRef.current = bufferRef.current.filter(e => e.ts >= cutoff);
      setChartData([...bufferRef.current]);
    }, 1000);
    return () => clearInterval(id);
  }, []);

  if (chartData.length === 0) {
    return (
      <p className="text-muted text-center py-3 mb-0 small">Waiting for traffic data…</p>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#30363d" vertical={false} />
        <XAxis
          dataKey="ts"
          tick={TICK_STYLE}
          axisLine={{ stroke: '#30363d' }}
          tickLine={false}
          tickFormatter={(ts: number) => new Date(ts).toLocaleTimeString()}
          interval="preserveStartEnd"
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
          cursor={{ stroke: '#58a6ff', strokeWidth: 1 }}
          labelFormatter={(ts: number) => new Date(ts).toLocaleTimeString()}
          formatter={(value: number) => [value, 'Events']}
        />
        <Line
          type="monotone"
          dataKey="count"
          stroke="#28a745"
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
