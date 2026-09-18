'use client';

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { money } from '@/lib/format';
import type { ChartPoint } from '@/components/landing/landingData';

export default function LandingChart({
  series,
  height = 320,
  label,
  empty,
  format = 'money',
}: {
  series: ChartPoint[];
  height?: number;
  label: string;
  empty: string;
  format?: 'money' | 'count';
}) {
  if (series.length < 2) {
    return (
      <div className="lp-empty" style={{ minHeight: height }} role="status">
        <p>{empty}</p>
      </div>
    );
  }

  const last = series[series.length - 1]?.price;
  const first = series[0]?.price;
  const up = last >= first;
  const stroke = up ? '#34d399' : '#fb7185';
  const show = (value: unknown) => {
    const n = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(n)) return 'Not available';
    return format === 'count' ? String(n) : money(n);
  };

  return (
    <div className="lp-chart-wrap" style={{ height }}>
      <p className="lp-chart-caption">{label}</p>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={series} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="rgba(148,163,184,0.12)" vertical={false} />
          <XAxis dataKey="t" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={28} />
          <YAxis
            domain={['auto', 'auto']}
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={72}
            tickFormatter={(value: number) => show(value)}
          />
          <Tooltip
            contentStyle={{
              background: '#0b1220',
              border: '1px solid rgba(148,163,184,0.2)',
              borderRadius: 12,
              color: '#e8eef7',
            }}
            formatter={(value) => [show(value), format === 'count' ? 'Trades' : 'Close']}
            labelFormatter={(labelValue) => String(labelValue)}
          />
          <Line type="monotone" dataKey="price" stroke={stroke} strokeWidth={2.2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
