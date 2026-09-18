'use client';

import Link from 'next/link';
import { moneyDisplay, NOT_AVAILABLE, pct, pnlClass, shown } from '@/lib/format';
import { normalizeFreshness, normalizeSession } from '@/lib/marketStatus';

type Row = Record<string, unknown>;

function liveLabel(row: Row): { text: string; klass: string } {
  const freshness = normalizeFreshness(row.freshness);
  if (row.live === true && freshness === 'FRESH') return { text: 'LIVE', klass: 'border-emerald-600 text-emerald-300' };
  if (freshness === 'STALE') return { text: 'STALE', klass: 'border-amber-600 text-amber-200' };
  if (row.error) return { text: 'DISCONNECTED', klass: 'border-rose-600 text-rose-300' };
  return { text: freshness === 'FRESH' ? 'LIVE' : freshness, klass: 'border-slate-600 text-slate-300' };
}

export default function WatchlistTable({
  items,
  selected,
  hrefBase = '/stocks',
}: {
  items: Row[];
  selected?: string;
  hrefBase?: string;
}) {
  if (!items.length) {
    return <p className="text-sm text-slate-400">Loading Alpaca watchlist…</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <thead className="text-[10px] uppercase tracking-wide text-slate-500">
          <tr>
            {['Symbol', 'Company', 'Price', 'Change', 'Bid', 'Ask', 'Volume', 'Session', 'Updated', 'Status'].map((h) => (
              <th key={h} className="px-2 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((row) => {
            const symbol = String(row.symbol || '');
            const live = liveLabel(row);
            const change = row.day_change_pct;
            return (
              <tr key={symbol} className={`border-t border-slate-800 ${selected === symbol ? 'bg-slate-800/40' : ''}`}>
                <td className="px-2 py-2 font-semibold text-white">
                  <Link href={`${hrefBase}?symbol=${symbol}`} className="hover:text-sky-300">
                    {symbol}
                  </Link>
                </td>
                <td className="px-2 py-2 text-slate-300">{shown(row.company)}</td>
                <td className="px-2 py-2 tabular-nums text-white">{moneyDisplay(row.price)}</td>
                <td className={`px-2 py-2 tabular-nums ${pnlClass(change)}`}>
                  {typeof change === 'number' ? pct(change, true) : NOT_AVAILABLE}
                </td>
                <td className="px-2 py-2 tabular-nums">{moneyDisplay(row.bid)}</td>
                <td className="px-2 py-2 tabular-nums">{moneyDisplay(row.ask)}</td>
                <td className="px-2 py-2 tabular-nums text-slate-300">{shown(row.volume)}</td>
                <td className="px-2 py-2 text-slate-300">{normalizeSession(row.session)}</td>
                <td className="px-2 py-2 text-xs text-slate-400">{shown(row.last_update)}</td>
                <td className="px-2 py-2">
                  <span className={`rounded border px-1.5 py-0.5 text-[10px] font-bold ${live.klass}`}>
                    {live.text === 'LIVE' ? '🟢 LIVE' : live.text === 'STALE' ? '🟡 STALE' : live.text === 'DISCONNECTED' ? '🔴 DISCONNECTED' : live.text}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
