'use client';

import { NOT_AVAILABLE, isMissing } from '@/lib/format';

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

export default function PriceChart({ bars, symbol }: { bars?: unknown; symbol?: string }) {
  const rows = (Array.isArray(bars) ? bars : []).map(asDict);
  const closes = rows
    .map((row) => {
      const close = typeof row.close === 'number' ? row.close : Number(row.close);
      return Number.isFinite(close) ? close : null;
    })
    .filter((value): value is number => value !== null);

  if (closes.length < 2) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
        <p className="text-[10px] uppercase tracking-wide text-slate-500">Price chart · Alpaca daily bars</p>
        <p className="mt-2 text-sm text-slate-400">
          {closes.length === 1
            ? `Only one Alpaca bar is available for ${symbol || 'this symbol'}. A trend line is not drawn from a single point.`
            : `Chart ${NOT_AVAILABLE} — Alpaca did not return enough historical bars.`}
        </p>
      </div>
    );
  }

  const width = 320;
  const height = 96;
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const span = max - min || 1;
  const points = closes
    .map((price, index) => {
      const x = (index / (closes.length - 1)) * width;
      const y = height - ((price - min) / span) * (height - 8) - 4;
      return `${x},${y}`;
    })
    .join(' ');
  const up = closes[closes.length - 1] >= closes[0];

  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
      <p className="mb-2 text-[10px] uppercase tracking-wide text-slate-500">
        Price chart · {symbol} · {closes.length} Alpaca daily bars
      </p>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-24 w-full">
        <polyline fill="none" stroke={up ? '#3D7A57' : '#B42318'} strokeWidth="2" points={points} />
      </svg>
      <p className="mt-1 text-[10px] text-slate-500">
        {isMissing(min) ? NOT_AVAILABLE : `Range ${min.toFixed(2)} – ${max.toFixed(2)}`}
      </p>
    </div>
  );
}
