'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { moneyDisplay, shown, timeAgo } from '@/lib/format';
import { missingMetric, toMarketState } from '@/lib/marketState';
import StockSelector from '@/components/StockSelector';
import DataQualityIndicator from '@/components/DataQualityIndicator';
import { QUICK_SWITCH } from '@/lib/symbols';

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

function lastBarVolume(market: Dict): unknown {
  const bars = Array.isArray(market.bars) ? market.bars : [];
  const last = asDict(bars[bars.length - 1]);
  return last.volume;
}

export default function MarketWatchCard({
  symbol,
  onSymbolChange,
  market,
  error,
  loading,
  fetchedAt,
  onRefresh,
  onAnalyze,
}: {
  symbol: string;
  onSymbolChange: (symbol: string) => void;
  market: unknown;
  error?: unknown;
  loading?: boolean;
  fetchedAt?: number;
  onRefresh: () => void;
  onAnalyze?: () => void;
}) {
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = window.setInterval(() => setTick((n) => n + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  const data = asDict(market);
  const state = toMarketState(market, { error, symbol });
  const volume = lastBarVolume(data);
  const invalidSymbol = /not found|unknown symbol|invalid symbol|404/i.test(`${state.dataError || ''}`);

  return (
    <section id="market" className="rounded-xl border border-slate-700/80 bg-slate-900/70 p-4 sm:p-5">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Market Watch</h2>
        <p className="text-[10px] font-bold uppercase tracking-wide text-sky-400">Alpaca Market Data</p>
      </div>
      <StockSelector value={symbol} onChange={onSymbolChange} />
      <div className="mt-3 flex flex-wrap gap-1">
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

      {state.dataError && invalidSymbol ? (
        <p className="mt-3 text-sm text-rose-300">MARKET DATA ERROR · INVALID SYMBOL · {state.dataError}</p>
      ) : loading && !market ? (
        <p className="mt-3 text-sm text-slate-400">Loading Alpaca quote…</p>
      ) : (
        <>
          <div className="mt-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-wide text-slate-500">Selected</p>
              <p className="text-sm font-semibold text-white">{symbol}</p>
              <p className="text-3xl font-bold tabular-nums text-white">
                {state.quoteAvailable && state.price !== null ? moneyDisplay(state.price) : 'NO QUOTE AVAILABLE'}
              </p>
            </div>
            <div className="flex flex-wrap gap-2 text-[10px] font-bold uppercase tracking-wide">
              {state.liveMarketData ? (
                <span className="rounded border border-emerald-600 bg-emerald-950 px-2 py-1 text-emerald-300">LIVE MARKET DATA</span>
              ) : null}
              <span className={`rounded border px-2 py-1 ${state.marketStatus === 'CLOSED' ? 'border-amber-600 bg-amber-950 text-amber-200' : 'border-emerald-600 text-emerald-300'}`}>
                {state.marketStatus === 'CLOSED' ? 'MARKET CLOSED' : state.marketStatus === 'OPEN' ? 'MARKET OPEN' : 'MARKET STATUS UNKNOWN'}
              </span>
              <span className="rounded border border-slate-600 px-2 py-1 text-slate-300">Session {state.session}</span>
              <span className="rounded border border-slate-600 px-2 py-1 text-slate-300">Freshness {state.freshness}</span>
              <DataQualityIndicator quality={asDict(data.integrity)} compact />
            </div>
          </div>
          {state.quoteAvailable ? (
            <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-amber-200">Latest available Alpaca quote</p>
          ) : null}
          {state.dataError && !invalidSymbol ? <p className="mt-2 text-sm text-rose-300">MARKET DATA ERROR · {state.dataError}</p> : null}

          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <Item label="Bid" value={state.bid !== null ? moneyDisplay(state.bid) : 'NO BID'} />
            <Item label="Ask" value={state.ask !== null ? moneyDisplay(state.ask) : 'NO ASK'} />
            <Item
              label="Spread"
              value={state.bid !== null && state.ask !== null ? moneyDisplay(state.ask - state.bid) : 'NO SPREAD'}
            />
            <Item label="Volume" value={volume == null ? missingMetric('generic', 'VOLUME NOT AVAILABLE') : String(volume)} />
            <Item label="Session" value={state.session} />
            <Item label="Market status" value={state.marketStatus} />
            <Item label="Freshness" value={state.freshness} />
            <Item label="Source" value="ALPACA" />
            <Item label="Updated" value={state.timestamp || 'NO QUOTE TIMESTAMP'} />
          </dl>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
            <p>Last updated: {fetchedAt ? timeAgo(fetchedAt) : 'WAITING FOR FIRST FETCH'}</p>
            <button type="button" onClick={onRefresh} className="rounded border border-slate-600 px-2 py-1 font-semibold text-slate-200">
              ↻ Refresh
            </button>
          </div>
          {!state.simulationEligible ? (
            <p className="mt-3 text-sm text-slate-300">
              {state.marketStatus === 'CLOSED' ? 'MARKET CLOSED. ' : 'DATA STALE. '}
              Simulation requires a fresh market quote. Latest quote {state.quoteAvailable && state.price !== null ? moneyDisplay(state.price) : 'none'}.
              Status: WAITING FOR FRESH DATA.
            </p>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => {
                document.getElementById('analyze')?.scrollIntoView({ behavior: 'smooth' });
                onAnalyze?.();
              }}
              className="rounded-lg bg-primary px-3 py-2 text-xs font-semibold uppercase text-white"
            >
              Analyze Stock
            </button>
            <a href="#trade" className="rounded-lg border border-slate-600 px-3 py-2 text-xs font-semibold uppercase text-slate-100">
              Trade
            </a>
            <Link href="/market-intelligence" className="rounded-lg border border-slate-600 px-3 py-2 text-xs font-semibold uppercase text-slate-100">
              View Market Data
            </Link>
          </div>
        </>
      )}
    </section>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="mt-0.5 font-semibold text-white">{shown(value)}</dd>
    </div>
  );
}
