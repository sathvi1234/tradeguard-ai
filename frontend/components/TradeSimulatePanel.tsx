'use client';

import { useEffect, useState } from 'react';
import { demo } from '@/lib/api';
import { useAutonomousStatus, useBodyguard } from '@/hooks/useApi';
import { useRefreshTrading } from '@/hooks/useApi';
import { money, moneyPositive, shown } from '@/lib/format';
import { simulationLabel, toMarketState } from '@/lib/marketState';
import { useLearnProgress } from '@/hooks/useLearnProgress';
import StockSelector from '@/components/StockSelector';
import { QUICK_SWITCH } from '@/lib/symbols';

type Preview = {
  symbol?: string;
  side?: string;
  quantity?: number;
  order_type?: string;
  estimated_price?: number | string;
  estimated_notional?: number | string;
  dry_run?: boolean;
  label?: string;
  quote_freshness?: string;
  session?: string;
  quote_usable?: boolean;
};

type Result = {
  ok?: boolean;
  submitted?: boolean;
  status?: string;
  reason?: string;
  gate?: string;
  preview?: Preview;
  order?: {
    alpaca_order_id?: string;
    order_id?: string;
    symbol?: string;
    side?: string;
    quantity?: number;
    filled_qty?: number;
    filled_avg_price?: number | string;
    price?: number | string;
    status?: string;
    timestamp?: string;
    submitted_at?: string;
    filled_at?: string;
    trade_type?: string;
  };
};

type MarketBits = {
  price?: unknown;
  bid?: unknown;
  ask?: unknown;
  spread?: unknown;
  volume?: unknown;
  session?: unknown;
  freshness?: unknown;
};

function asMoney(value: unknown): string {
  if (value === undefined || value === null || value === '') return 'NO QUOTE AVAILABLE';
  const formatted = money(value);
  return formatted === 'DATA_UNAVAILABLE' ? 'NO QUOTE AVAILABLE' : formatted;
}

export default function TradeSimulatePanel({
  symbol,
  onSymbolChange,
  market,
}: {
  symbol: string;
  onSymbolChange: (symbol: string) => void;
  market?: MarketBits;
}) {
  const { recordSimulation } = useLearnProgress();
  const refreshTrading = useRefreshTrading();
  const { status } = useAutonomousStatus();
  const { bodyguard } = useBodyguard();
  const [side, setSide] = useState<'buy' | 'sell'>('buy');
  const [quantity, setQuantity] = useState(1);
  const [orderType, setOrderType] = useState<'market' | 'limit'>('market');
  const [limitPrice, setLimitPrice] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const engine = status && typeof status === 'object' ? (status as Record<string, unknown>) : {};
  const mode = String(engine.current_mode || '').toUpperCase();
  const freeze = Boolean((bodyguard as Record<string, unknown> | undefined)?.freeze_new_trades);
  const riskStatus = freeze || mode === 'CRITICAL' ? 'CRITICAL / NEW TRADES BLOCKED' : mode || 'NORMAL';
  const marketState = toMarketState(market, { symbol });
  const session = preview?.session || marketState.session;
  const freshness = preview?.quote_freshness || marketState.freshness;
  const hasPrice = marketState.quoteAvailable || (typeof preview?.estimated_price === 'number' && preview.estimated_price > 0);

  async function loadPreview() {
    setBusy(true);
    setError('');
    try {
      const response = await demo.submit({
        symbol,
        side,
        quantity,
        order_type: 'demo',
        preview_only: true,
      });
      setPreview((response.data?.preview || null) as Preview);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Preview failed');
      setPreview(null);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void loadPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, quantity, orderType, limitPrice, side]);

  async function submit(nextSide: 'buy' | 'sell') {
    setSide(nextSide);
    setBusy(true);
    setError('');
    try {
      const response = await demo.submit({
        symbol,
        side: nextSide,
        quantity,
        order_type: 'demo',
        preview_only: false,
      });
      const body = response.data as Result;
      setResult(body);
      setPreview(body.preview || preview);
      if (body.ok && body.order) {
        recordSimulation({
          shock: `equity_${nextSide}`,
          pnl: 0,
          side: nextSide,
          direction: 'long',
        });
        await refreshTrading();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Simulation failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section id="trade" className="rounded-xl border border-slate-700/80 bg-slate-900/70 p-4 sm:p-5">
      <h2 className="mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">DEMO ORDER</h2>
      <p className="mb-4 text-xs text-sky-300">Virtual Money · Simulation Only · No real-money order will be placed · RiskGuardian is final</p>

      <StockSelector value={symbol} onChange={onSymbolChange} label="Stock" />
      <div className="mt-2 flex flex-wrap gap-1">
        {QUICK_SWITCH.map((item) => (
          <button
            key={item}
            type="button"
            onClick={() => onSymbolChange(item)}
            className={`rounded-md border px-2 py-1 text-[11px] font-semibold ${
              item === symbol ? 'border-sky-500 text-white' : 'border-slate-700 text-slate-400'
            }`}
          >
            {item}
          </button>
        ))}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <StatusChip label="Selected Symbol" value={symbol} />
        <StatusChip label="Current Price" value={asMoney(marketState.price ?? preview?.estimated_price)} />
        <StatusChip label="Bid" value={marketState.bid !== null ? moneyPositive(marketState.bid) : 'NO BID'} />
        <StatusChip label="Ask" value={marketState.ask !== null ? moneyPositive(marketState.ask) : 'NO ASK'} />
        <StatusChip label="Spread" value={marketState.bid !== null && marketState.ask !== null ? asMoney(marketState.ask - marketState.bid) : 'NO SPREAD'} />
        <StatusChip label="Volume" value={shown(market?.volume) === 'Not available' ? 'VOLUME NOT AVAILABLE' : shown(market?.volume)} />
        <StatusChip label="Session" value={String(session || marketState.session)} />
        <StatusChip label="Market status" value={marketState.marketStatus} />
        <StatusChip label="Freshness" value={String(freshness || marketState.freshness)} />
        <StatusChip label="Risk Status" value={riskStatus} />
      </div>

      <div className="mt-4 flex flex-wrap gap-3 text-sm">
        <label className="flex items-center gap-2">
          BUY / SELL
          <select value={side} onChange={(e) => setSide(e.target.value as 'buy' | 'sell')} className="rounded border border-slate-700 bg-slate-950 px-2 py-1">
            <option value="buy">BUY</option>
            <option value="sell">SELL</option>
          </select>
        </label>
        <label className="flex items-center gap-2">
          Quantity
          <input
            type="number"
            min={1}
            max={100}
            value={quantity}
            onChange={(e) => setQuantity(Number(e.target.value) || 1)}
            className="w-20 rounded border border-slate-700 bg-slate-950 px-2 py-1"
          />
        </label>
        <label className="flex items-center gap-2">
          Order Type
          <select value={orderType} onChange={(e) => setOrderType(e.target.value as 'market' | 'limit')} className="rounded border border-slate-700 bg-slate-950 px-2 py-1">
            <option value="market">MARKET</option>
            <option value="limit">LIMIT</option>
          </select>
        </label>
        {orderType === 'limit' ? (
          <label className="flex items-center gap-2">
            Limit Price
            <input
              value={limitPrice}
              onChange={(e) => setLimitPrice(e.target.value)}
              className="w-24 rounded border border-slate-700 bg-slate-950 px-2 py-1"
            />
          </label>
        ) : null}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <StatusChip label="Estimated Price" value={asMoney(preview?.estimated_price ?? marketState.price)} />
        <StatusChip label="Estimated Notional" value={asMoney(preview?.estimated_notional)} />
        <StatusChip label="Market Status" value={marketState.marketStatus === 'CLOSED' ? 'MARKET CLOSED' : String(session || marketState.session)} />
        <StatusChip label="Quote Freshness" value={String(freshness || marketState.freshness)} />
      </div>

      {preview ? (
        <div className="mt-4 space-y-1 rounded-lg border border-slate-800 p-3 text-sm">
          <p className="text-[10px] font-bold uppercase text-sky-300">Order Preview · DEMO ORDER</p>
          <p>
            Symbol {preview.symbol} · Side {preview.side} · Quantity {preview.quantity} · {preview.order_type}
          </p>
          <p>Estimated Price {asMoney(preview.estimated_price)}</p>
          <p>Estimated Notional {asMoney(preview.estimated_notional)}</p>
        </div>
      ) : null}
      {!marketState.simulationEligible ? (
        <div className="mt-4 rounded-lg border border-amber-700 bg-amber-950/40 p-4">
          <p className="text-sm font-bold uppercase tracking-wide text-amber-200">
            {marketState.marketStatus === 'CLOSED' ? 'MARKET CLOSED' : 'DATA STALE'}
          </p>
          <p className="mt-2 text-sm text-slate-200">Simulation requires a fresh market quote.</p>
          <p className="mt-1 text-sm text-slate-300">
            Latest available quote: {marketState.quoteAvailable && marketState.price !== null ? asMoney(marketState.price) : 'none'} · Session:{' '}
            {marketState.session} · Status: {simulationLabel(marketState)}
          </p>
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2">
        <button type="button" disabled={busy} onClick={() => void loadPreview()} className="rounded-lg border border-slate-600 px-3 py-2 text-xs font-semibold uppercase">
          Preview
        </button>
        <button
          type="button"
          disabled={busy || !hasPrice}
          onClick={() => void submit('buy')}
          className="rounded-lg bg-emerald-700 px-3 py-2 text-xs font-semibold uppercase text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          Buy Stock
        </button>
        <button
          type="button"
          disabled={busy || !hasPrice}
          onClick={() => void submit('sell')}
          className="rounded-lg bg-rose-800 px-3 py-2 text-xs font-semibold uppercase text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          Sell
        </button>
      </div>

      {result ? (
        <div className={`mt-3 rounded-lg border p-3 text-sm ${result.ok && result.order ? 'border-emerald-800' : 'border-rose-800'}`}>
          {result.ok && result.order ? (
            <>
              <p className="font-semibold text-emerald-300">DEMO_SIMULATED</p>
              <p>Trade ID {result.order.order_id}</p>
              <p>
                Symbol {result.order.symbol} · Side {result.order.side} · Quantity {result.order.filled_qty ?? result.order.quantity} · Price {asMoney(result.order.filled_avg_price ?? result.order.price)}
              </p>
              <p>Status {result.order.status} · {result.order.trade_type || 'DEMO_SIMULATED'}</p>
              <p className="mt-2 text-xs text-slate-400">Virtual fill using real Alpaca market data. Not submitted to Alpaca.</p>
            </>
          ) : (
            <>
              <p className="font-semibold text-rose-300">{result.gate || 'DEMO BUY BLOCKED'}</p>
              <p>{result.reason}</p>
            </>
          )}
        </div>
      ) : null}
      {error ? <p className="mt-2 text-sm text-rose-300">{error}</p> : null}
    </section>
  );
}

function StatusChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-2">
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 font-semibold text-white">{value}</p>
    </div>
  );
}
