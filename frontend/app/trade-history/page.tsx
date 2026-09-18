'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { useDemoOrders } from '@/hooks/useApi';
import { moneyDisplay, shown } from '@/lib/format';

type Row = Record<string, unknown>;

export default function TradeHistory() {
  const { orders, isLoading } = useDemoOrders();
  const [filter, setFilter] = useState<'all' | 'buy' | 'sell'>('all');

  const rows = useMemo(() => {
    const paperRows: Row[] = (Array.isArray(orders) ? orders : []).map((order: Row) => ({
      ...order,
      date: String(order.filled_at || order.timestamp || order.submitted_at || ''),
      total: order.total_value ?? order.notional,
      type: order.trade_type || 'DEMO_SIMULATED',
      label: order.trade_type || 'DEMO_SIMULATED',
    }));
    return paperRows
      .sort((a, b) => String(b.date).localeCompare(String(a.date)))
      .filter((row) => {
        const side = String(row.side || '').toLowerCase();
        if (filter === 'buy') return side === 'buy';
        if (filter === 'sell') return side === 'sell';
        return true;
      });
  }, [orders, filter]);

  return (
    <main className="space-y-5 px-4 py-6 sm:px-6">
      <div>
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Trade AI</p>
        <h1 className="text-2xl font-bold text-white">Trade History</h1>
        <p className="mt-1 text-sm text-slate-400">Demo User virtual trades only. Type DEMO_SIMULATED. No Alpaca order IDs.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {(['all', 'buy', 'sell'] as const).map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => setFilter(item)}
            className={`rounded-lg border px-3 py-1 text-xs font-semibold uppercase ${
              filter === item ? 'border-sky-500 text-white' : 'border-slate-700 text-slate-400'
            }`}
          >
            {item}
          </button>
        ))}
      </div>
      {isLoading && rows.length === 0 ? (
        <p className="text-sm text-slate-400">Loading demo trades…</p>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-8 text-center">
          <p className="text-slate-300">No trades yet</p>
          <Link href="/stocks" className="mt-3 inline-block rounded-lg bg-primary px-4 py-2 text-xs font-semibold uppercase text-white">
            Browse Stocks
          </Link>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-700">
          <table className="min-w-full text-left text-sm">
            <thead className="text-[10px] uppercase tracking-wide text-slate-500">
              <tr>
                {['Date/Time', 'Symbol', 'Side', 'Quantity', 'Filled', 'Price', 'Total', 'Status', 'Type', 'Trade ID'].map((h) => (
                  <th key={h} className="px-3 py-2 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={String(row.trade_id || row.order_id)} className="border-t border-slate-800">
                  <td className="px-3 py-2 text-xs text-slate-400">{shown(row.date)}</td>
                  <td className="px-3 py-2 font-semibold text-white">{shown(row.symbol)}</td>
                  <td className="px-3 py-2 uppercase">{shown(row.side)}</td>
                  <td className="px-3 py-2">{shown(row.quantity)}</td>
                  <td className="px-3 py-2">{shown(row.filled_qty)}</td>
                  <td className="px-3 py-2">{moneyDisplay(row.filled_avg_price ?? row.price)}</td>
                  <td className="px-3 py-2">{moneyDisplay(row.total)}</td>
                  <td className="px-3 py-2">{shown(row.status)}</td>
                  <td className="px-3 py-2 text-amber-300">{shown(row.label || row.trade_type)}</td>
                  <td className="px-3 py-2 text-xs text-slate-400">{shown(row.trade_id || row.order_id)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
