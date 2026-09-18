'use client';

import Link from 'next/link';
import { moneyDisplay, shown } from '@/lib/format';

type Row = Record<string, unknown>;

export default function RecentTradesList({ fills }: { fills: Row[] }) {
  if (!fills.length) {
    return (
      <div className="text-sm text-slate-400">
        <p>No trades yet</p>
        <Link href="/stocks" className="mt-2 inline-block rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold uppercase text-white">
          Browse Stocks
        </Link>
      </div>
    );
  }
  return (
    <ul className="space-y-2">
      {fills
        .slice()
        .reverse()
        .slice(0, 8)
        .map((row) => (
          <li key={String(row.trade_id || row.order_id)} className="rounded-lg border border-slate-800 px-3 py-2 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold text-white">
                {shown(row.side).toUpperCase()} {shown(row.symbol)}
              </p>
              <p className="text-[10px] font-bold uppercase text-amber-300">{shown(row.label)}</p>
            </div>
            <p className="text-slate-300">
              {shown(row.quantity)} share{Number(row.quantity) === 1 ? '' : 's'} · {moneyDisplay(row.price)} · {moneyDisplay(row.total_value ?? row.notional)}
            </p>
            <p className="text-xs text-slate-500">
              {shown(row.timestamp)} · {shown(row.status)} · {shown(row.source)}
            </p>
          </li>
        ))}
    </ul>
  );
}
