import { useRef, useState, useEffect } from 'react';
import {
  ResponsiveContainer, AreaChart, Area,
  XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts';

interface Props {
  batchCount: number;
}

interface DataPoint {
  ts: number;
  count: number;
}

const GRID_COLOR    = 'rgba(255,255,255,0.05)';
const AXIS_COLOR    = 'rgba(255,255,255,0.06)';
const TICK_STYLE    = { fill: '#445068', fontSize: 11, fontFamily: 'var(--font-sans, Inter, sans-serif)' };
const TOOLTIP_STYLE = {
  background: '#111827',
  border: '1px solid rgba(255,255,255,0.09)',
  borderRadius: 8,
  color: '#eef2ff',
  fontSize: 12,
  fontFamily: 'var(--font-sans, Inter, sans-serif)',
  boxShadow: '0 4px 20px rgba(0,0,0,0.6)',
};

export default function ConnectionsPerSecond({ batchCount }: Props) {
  const bufferRef  = useRef<DataPoint[]>([]);
  const [chartData, setChartData] = useState<DataPoint[]>([]);

  useEffect(() => {
    if (batchCount > 0) {
      bufferRef.current = [...bufferRef.current, { ts: Date.now(), count: batchCount }];
    }
  }, [batchCount]);

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
      <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontSize: '0.76rem', color: 'var(--tx-3)' }}>Waiting for traffic…</span>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={chartData} margin={{ top: 4, right: 12, bottom: 4, left: 0 }}>
        <defs>
          <linearGradient id="liveGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%"   stopColor="#10b981" stopOpacity={0.25} />
            <stop offset="100%" stopColor="#10b981" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID_COLOR} vertical={false} />
        <XAxis
          dataKey="ts"
          tick={TICK_STYLE}
          axisLine={{ stroke: AXIS_COLOR }}
          tickLine={false}
          tickFormatter={(ts: number) => new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          interval="preserveStartEnd"
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
          cursor={{ stroke: 'rgba(16,185,129,0.3)', strokeWidth: 1 }}
          labelFormatter={(ts: number) => new Date(ts).toLocaleTimeString()}
          formatter={(value: number) => [value, 'Events']}
        />
        <Area
          type="monotone"
          dataKey="count"
          stroke="#10b981"
          strokeWidth={2}
          fill="url(#liveGradient)"
          dot={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
