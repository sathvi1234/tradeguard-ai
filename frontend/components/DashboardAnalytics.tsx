'use client';

import { isMissing, moneyDisplay, shown } from '@/lib/format';
import { missingMetric, toMarketState } from '@/lib/marketState';

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

export default function DashboardAnalytics({
  analytics,
  loading,
  error,
}: {
  analytics: unknown;
  loading?: boolean;
  error?: unknown;
}) {
  const data = asDict(analytics);
  const tech = asDict(data.technicals);
  const state = toMarketState(analytics, { error, symbol: String(data.symbol || '') });
  const err = error instanceof Error ? error.message : error ? String(error) : '';

  if (err) {
    return (
      <section className="rounded-xl border border-slate-700/80 bg-slate-900/70 p-4 sm:p-5">
        <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Stock Analytics</h2>
        <p className="text-sm text-rose-300">MARKET DATA ERROR · {err}</p>
      </section>
    );
  }

  if (loading && !analytics) {
    return (
      <section className="rounded-xl border border-slate-700/80 bg-slate-900/70 p-4 sm:p-5">
        <h2 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Stock Analytics</h2>
        <p className="text-sm text-slate-400">Loading analytics from Alpaca bars…</p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-slate-700/80 bg-slate-900/70 p-4 sm:p-5">
      <h2 className="mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Stock Analytics</h2>
      <p className="mb-4 text-xs text-slate-500">{shown(data.symbol)} · source ALPACA · indicators only from available bars</p>
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Price</h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        <Field label="Current / Latest Price" value={state.quoteAvailable && state.price !== null ? moneyDisplay(state.price) : 'NO QUOTE AVAILABLE'} />
        <Field label="Bid" value={state.bid !== null ? moneyDisplay(state.bid) : 'NO BID'} />
        <Field label="Ask" value={state.ask !== null ? moneyDisplay(state.ask) : 'NO ASK'} />
        <Field label="Spread" value={state.bid !== null && state.ask !== null ? moneyDisplay(state.ask - state.bid) : 'NO SPREAD'} />
        <Field label="Volume" value={isMissing(data.volume) ? missingMetric('generic', 'VOLUME NOT AVAILABLE') : String(data.volume)} />
        <Field label="Previous close" value={typeof data.previous_close === 'number' ? moneyDisplay(data.previous_close) : 'PREVIOUS CLOSE NOT AVAILABLE'} />
        <Field label="Day change" value={typeof data.day_change === 'number' ? moneyDisplay(data.day_change) : 'DAY CHANGE NOT AVAILABLE'} />
        <Field label="Day change %" value={typeof data.day_change_pct === 'number' ? `${(Number(data.day_change_pct) * 100).toFixed(2)}%` : 'DAY CHANGE % NOT AVAILABLE'} />
        <Field label="Company" value={isMissing(data.company) ? 'COMPANY NAME NOT AVAILABLE' : shown(data.company)} />
      </div>
      <h3 className="mb-2 mt-5 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Market</h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Field label="Session" value={state.session} />
        <Field label="Market Status" value={state.marketStatus === 'CLOSED' ? 'MARKET CLOSED' : state.marketStatus} />
        <Field label="Data Source" value="ALPACA" />
        <Field label="Freshness" value={state.freshness} />
        <Field label="Timestamp" value={state.timestamp || 'NO QUOTE TIMESTAMP'} />
      </div>
      <h3 className="mb-2 mt-5 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">Technical Analytics</h3>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Field label="SMA" value={isMissing(tech.sma_20) ? 'SMA NOT AVAILABLE' : shown(tech.sma_20)} />
        <Field label="EMA" value={isMissing(tech.ema_12) ? 'EMA NOT AVAILABLE' : shown(tech.ema_12)} />
        <Field label="RSI" value={isMissing(tech.rsi_14) ? 'RSI NOT AVAILABLE' : shown(tech.rsi_14)} />
        <Field label="MACD" value={isMissing(tech.macd) ? 'MACD NOT AVAILABLE' : shown(tech.macd)} />
        <Field label="VWAP" value={isMissing(tech.vwap_last_bar) ? 'VWAP NOT AVAILABLE' : shown(tech.vwap_last_bar)} />
        <Field label="Volatility" value={isMissing(tech.realized_vol_ann) ? missingMetric('volatility') : shown(tech.realized_vol_ann)} />
      </div>
    </section>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-sm font-semibold text-white">{value}</p>
    </div>
  );
}
