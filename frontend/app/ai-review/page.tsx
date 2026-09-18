'use client';

import { useState } from 'react';
import { review } from '@/lib/api';
import { useLastReview } from '@/hooks/useApi';
import { QUICK_SWITCH } from '@/lib/symbols';

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

function asList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)) : [];
}

function pill(ok: boolean, yes: string, no: string) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${ok ? 'bg-emerald-500/20 text-emerald-200' : 'bg-rose-500/20 text-rose-200'}`}>
      {ok ? yes : no}
    </span>
  );
}

export default function AiReviewPage() {
  const { last, mutate } = useLastReview();
  const [symbol, setSymbol] = useState('AAPL');
  const [size, setSize] = useState('400');
  const [quantity, setQuantity] = useState('4');
  const [drawdown, setDrawdown] = useState('0');
  const [mode, setMode] = useState('normal');
  const [marketClosed, setMarketClosed] = useState(false);
  const [stale, setStale] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<Dict | null>(null);

  const payload = result || asDict(asDict(last).review);
  const proposal = asDict(payload.proposal);
  const first = asDict(payload.first_risk_guardian);
  const llm = asDict(payload.llm_review);
  const finalRg = asDict(payload.final_risk_guardian);
  const allowed = payload.allowed_to_execute === true;

  async function onRun() {
    setBusy(true);
    setError('');
    try {
      const response = await review.run({
        symbol,
        proposed_size: Number(size),
        quantity: Number(quantity),
        current_drawdown: Number(drawdown),
        trading_mode: mode,
        market_closed: marketClosed,
        integrity_state: stale ? 'DATA_STALE' : null,
        skip_quote_age: !stale,
      });
      setResult(asDict(response.data));
      mutate();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Review failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="space-y-5 px-4 py-6 sm:px-6">
      <div>
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Trade AI</p>
        <h1 className="text-2xl font-bold text-white">AI Review</h1>
        <p className="mt-2 text-sm text-slate-400">
          Restricted LLM reviewer only. Risk Guardian is the final deterministic authority. This page never submits
          orders and cannot enable live trading.
        </p>
      </div>
      <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm font-semibold text-amber-200">
        LLM may only return VETO, SHRINK, or NO_CHANGE. It cannot approve a blocked trade, increase size, override
        risk limits, stale data, MARKET_CLOSED, or CRITICAL drawdown, execute orders, or access Alpaca credentials.
      </div>
      <section className="grid gap-3 rounded-lg border border-slate-800 bg-slate-950/40 p-4 md:grid-cols-3">
        <label className="text-sm text-slate-300">
          Symbol
          <select
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-white"
            value={symbol}
            onChange={(event) => setSymbol(event.target.value)}
          >
            {QUICK_SWITCH.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
        </label>
        <label className="text-sm text-slate-300">
          Proposed size (USD)
          <input
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-white"
            value={size}
            onChange={(event) => setSize(event.target.value)}
          />
        </label>
        <label className="text-sm text-slate-300">
          Quantity
          <input
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-white"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
          />
        </label>
        <label className="text-sm text-slate-300">
          Drawdown
          <input
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-white"
            value={drawdown}
            onChange={(event) => setDrawdown(event.target.value)}
          />
        </label>
        <label className="text-sm text-slate-300">
          Trading mode
          <select
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-white"
            value={mode}
            onChange={(event) => setMode(event.target.value)}
          >
            <option value="normal">normal</option>
            <option value="critical">critical</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-300 md:mt-7">
          <input type="checkbox" checked={marketClosed} onChange={(event) => setMarketClosed(event.target.checked)} />
          MARKET_CLOSED
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input type="checkbox" checked={stale} onChange={(event) => setStale(event.target.checked)} />
          DATA_STALE
        </label>
        <div className="md:col-span-3">
          <button
            type="button"
            disabled={busy}
            onClick={onRun}
            className="rounded bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {busy ? 'Running RG → LLM → RG…' : 'Run restricted review'}
          </button>
        </div>
        {error ? <p className="md:col-span-3 text-sm text-amber-300">{error}</p> : null}
      </section>

      {Object.keys(payload).length ? (
        <section className="grid gap-4 lg:grid-cols-4">
          <article className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Proposal</h2>
            <p className="mt-3 text-white">{String(proposal.symbol || 'DATA_UNAVAILABLE')}</p>
            <p className="text-sm text-slate-300">Size: {String(payload.original_size ?? proposal.proposed_size ?? 'DATA_UNAVAILABLE')}</p>
            <p className="text-sm text-slate-300">Qty: {String(payload.original_quantity ?? proposal.quantity ?? 'DATA_UNAVAILABLE')}</p>
          </article>
          <article className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Risk Guardian</h2>
            <p className="mt-3 text-white">{String(first.display_decision || first.decision || 'DATA_UNAVAILABLE')}</p>
            <p className="mt-2 text-xs text-slate-400">{asList(first.rejection_reasons).join('; ') || 'No rejection reasons'}</p>
          </article>
          <article className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">LLM Review</h2>
            <p className="mt-3 text-white">{String(llm.action || 'DATA_UNAVAILABLE')}</p>
            <p className="text-sm text-slate-300">{String(llm.reason || '')}</p>
            <p className="text-xs text-slate-400">Flags: {asList(llm.risk_flags).join(', ') || 'none'}</p>
            <p className="text-xs text-slate-400">Reduction: {String(llm.suggested_reduction_pct ?? 0)}</p>
            <p className="text-xs text-slate-400">Confidence: {String(llm.confidence ?? 0)}</p>
            <p className="text-xs text-slate-400">Model: {String(llm.model || 'DATA_UNAVAILABLE')}</p>
            <p className="text-xs text-slate-400">Time: {String(llm.timestamp || 'DATA_UNAVAILABLE')}</p>
            <p className="mt-2 text-xs text-amber-200">Advisory only. Cannot execute.</p>
          </article>
          <article className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Final Risk Decision</h2>
            <p className="mt-3 text-white">{String(finalRg.display_decision || finalRg.decision || 'DATA_UNAVAILABLE')}</p>
            <p className="text-sm text-slate-300">Applied size: {String(payload.applied_size ?? 'DATA_UNAVAILABLE')}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {pill(allowed, 'May reach execution path', 'Blocked from execution')}
              {pill(payload.risk_guardian_is_final_authority === true, 'RG final authority', 'Authority error')}
            </div>
            <p className="mt-2 text-xs text-slate-400">{asList(finalRg.rejection_reasons).join('; ') || 'No rejection reasons'}</p>
            <p className="mt-2 text-xs text-amber-200">Live trading: off. Demo User virtual trading is unchanged.</p>
          </article>
        </section>
      ) : null}
    </main>
  );
}
