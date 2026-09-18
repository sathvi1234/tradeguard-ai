import { moneyDisplay, shown } from '@/lib/format';
import {
  freshnessLabel,
  marketStatusHeadline,
  simulationLabel,
  toMarketState,
  type MarketDataState,
} from '@/lib/marketState';

export default function MarketStatePanel({
  market,
  symbol,
  streamLive,
  error,
  compact = false,
}: {
  market?: unknown;
  symbol?: string;
  streamLive?: boolean;
  error?: unknown;
  compact?: boolean;
}) {
  const state = toMarketState(market, { streamLive, error, symbol });
  return <MarketStateBadges state={state} compact={compact} />;
}

export function MarketStateBadges({ state, compact = false }: { state: MarketDataState; compact?: boolean }) {
  const freshness = freshnessLabel(state);
  const simulation = simulationLabel(state);
  return (
    <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          {state.symbol ? <p className="text-sm font-semibold uppercase tracking-wide text-white">{state.symbol}</p> : null}
          <p className="mt-1 text-2xl font-bold tabular-nums text-white">
            {state.quoteAvailable && state.price !== null ? moneyDisplay(state.price) : 'NO QUOTE AVAILABLE'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-[10px] font-bold uppercase tracking-wide">
          {state.liveMarketData && (state.freshness === 'LIVE' || state.freshness === 'FRESH') ? (
            <span className="rounded border border-emerald-600 bg-emerald-950 px-2 py-1 text-emerald-300">LIVE MARKET DATA</span>
          ) : null}
          <span className={`rounded border px-2 py-1 ${state.marketStatus === 'CLOSED' ? 'border-amber-500 text-amber-200' : state.marketStatus === 'OPEN' ? 'border-emerald-600 text-emerald-300' : 'border-slate-500 text-slate-300'}`}>
            {marketStatusHeadline(state)}
          </span>
          <span className={`rounded border px-2 py-1 ${state.freshness === 'STALE' ? 'border-amber-600 text-amber-200' : state.freshness === 'LIVE' || state.freshness === 'FRESH' ? 'border-emerald-600 text-emerald-300' : 'border-slate-500 text-slate-300'}`}>
            Freshness: {freshness}
          </span>
        </div>
      </div>
      {!compact ? (
        <dl className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-[10px] uppercase text-slate-500">Session</dt>
            <dd className="font-semibold text-white">{shown(state.session)}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase text-slate-500">Latest quote</dt>
            <dd className="font-semibold text-white">{state.timestamp || 'NO QUOTE TIMESTAMP'}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase text-slate-500">Simulation</dt>
            <dd className="font-semibold text-amber-200">{simulation}</dd>
          </div>
          <div>
            <dt className="text-[10px] uppercase text-slate-500">Source</dt>
            <dd className="font-semibold text-white">{state.source}</dd>
          </div>
        </dl>
      ) : null}
      {state.dataError ? <p className="mt-2 text-sm text-rose-300">MARKET DATA ERROR · {state.dataError}</p> : null}
      {!state.simulationEligible && !state.dataError ? (
        <p className="mt-2 text-sm text-slate-300">
          {state.marketStatus === 'CLOSED'
            ? 'MARKET CLOSED. Simulation requires a fresh market quote. This is not an API outage.'
            : 'DATA STALE. Simulation requires a fresh quote.'}
          {state.reason ? ` ${state.reason}` : ''}
        </p>
      ) : null}
    </section>
  );
}
