'use client';

import { useState } from 'react';
import { demo } from '@/lib/api';
import { useRefreshTrading } from '@/hooks/useApi';
import { moneyDisplay, shown } from '@/lib/format';
import { toMarketState } from '@/lib/marketState';

type Market = Record<string, unknown>;
type Order = Record<string, unknown>;

export default function StockTicket({
  symbol,
  market,
  liveStream = false,
}: {
  symbol: string;
  market?: Market | null;
  liveStream?: boolean;
}) {
  const refresh = useRefreshTrading();
  const [qty, setQty] = useState(1);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [ok, setOk] = useState<boolean | null>(null);
  const [order, setOrder] = useState<Order | null>(null);

  const state = toMarketState(market, { streamLive: liveStream, symbol });
  const hasPrice = state.quoteAvailable;
  const buyBlocked = !hasPrice || !state.simulationEligible;
  const blockReason = !hasPrice
    ? 'NO QUOTE AVAILABLE'
    : !state.simulationEligible
      ? 'Fresh market data required for simulation.'
      : '';

  async function submit(side: 'buy' | 'sell') {
    setBusy(true);
    setMessage('Simulating demo fill…');
    setOk(null);
    setOrder(null);
    try {
      const response = await demo.submit({
        symbol,
        side,
        quantity: qty,
        order_type: 'demo',
        preview_only: false,
      });
      const body = response.data as {
        ok?: boolean;
        filled?: boolean;
        reason?: string;
        status?: string;
        order?: Order;
        alpaca_order_submitted?: boolean;
      };
      if (body.ok && body.order) {
        setOk(true);
        setOrder(body.order);
        const filled = body.order.filled_avg_price ?? body.order.price;
        setMessage(
          `${String(body.order.side || side).toUpperCase()} ${shown(body.order.symbol || symbol)} ${shown(body.order.filled_qty || body.order.quantity)} @ ${moneyDisplay(filled)} · ${shown(body.order.status)} · DEMO_SIMULATED`
        );
        await refresh();
      } else {
        setOk(false);
        setMessage(String(body.reason || 'Fresh market data required for simulation.'));
      }
    } catch (err) {
      setOk(false);
      setMessage(err instanceof Error ? err.message : 'Demo order failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">DEMO ORDER</p>
      <p className="mt-1 text-xs font-bold uppercase text-sky-300">Virtual Money · Simulation Only</p>
      <p className="mt-2 text-sm text-slate-300">
        {symbol} · {state.quoteAvailable && state.price !== null ? moneyDisplay(state.price) : 'NO QUOTE AVAILABLE'} · {state.session}
      </p>
      <p className="mt-1 text-[10px] font-bold uppercase tracking-wide text-slate-500">
        Market status: {state.marketStatus} · Session: {state.session}
      </p>
      <p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">Freshness: {state.freshness}</p>
      <div className="mt-3 flex items-center gap-2">
        <span className="text-xs uppercase text-slate-500">Quantity</span>
        <button type="button" className="rounded border border-slate-600 px-3 py-1" onClick={() => setQty((n) => Math.max(1, n - 1))}>
          −
        </button>
        <span className="min-w-[2rem] text-center font-semibold text-white">{qty}</span>
        <button type="button" className="rounded border border-slate-600 px-3 py-1" onClick={() => setQty((n) => Math.min(100, n + 1))}>
          +
        </button>
      </div>
      {buyBlocked ? <p className="mt-3 text-sm text-amber-200">{blockReason}</p> : null}
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy || buyBlocked}
          onClick={() => void submit('buy')}
          className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-bold uppercase text-white disabled:opacity-40"
        >
          Buy Stock
        </button>
        <button
          type="button"
          disabled={busy || !hasPrice}
          onClick={() => void submit('sell')}
          className="rounded-lg bg-rose-800 px-4 py-2 text-sm font-bold uppercase text-white disabled:opacity-40"
        >
          Sell
        </button>
      </div>
      <p className="mt-3 text-xs text-slate-500">Uses virtual money only. No real order will be placed.</p>
      {order ? (
        <dl className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
          <div>
            <dt className="text-slate-500">Trade ID</dt>
            <dd className="text-white">{shown(order.trade_id || order.order_id)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Status</dt>
            <dd className="text-white">{shown(order.status)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Filled qty</dt>
            <dd className="text-white">{shown(order.filled_qty)}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Fill price</dt>
            <dd className="text-white">{moneyDisplay(order.filled_avg_price ?? order.price)}</dd>
          </div>
        </dl>
      ) : null}
      {message ? <p className={`mt-3 text-sm ${ok ? 'text-emerald-300' : 'text-rose-300'}`}>{message}</p> : null}
    </section>
  );
}
