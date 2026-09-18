'use client';

import { useState } from 'react';
import { volatility } from '@/lib/api';
import { useVolatilityForecasts } from '@/hooks/useApi';
import { QUICK_SWITCH } from '@/lib/symbols';

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

function show(value: unknown): string {
  if (value === null || value === undefined || value === 'DATA_UNAVAILABLE') return 'DATA_UNAVAILABLE';
  if (typeof value === 'number' && Number.isFinite(value)) return `${(value * 100).toFixed(2)}%`;
  return String(value);
}

function showErr(value: unknown): string {
  if (!value || typeof value !== 'object') return 'DATA_UNAVAILABLE';
  const row = value as Dict;
  if (typeof row.mae !== 'number') return 'DATA_UNAVAILABLE';
  return `MAE ${(row.mae as number).toFixed(4)} · RMSE ${typeof row.rmse === 'number' ? (row.rmse as number).toFixed(4) : 'n/a'} · corr ${
    typeof row.forecast_correlation === 'number' ? (row.forecast_correlation as number).toFixed(3) : 'n/a'
  }`;
}

export default function VolatilityLabPage() {
  const { forecasts, mutate } = useVolatilityForecasts();
  const [symbol, setSymbol] = useState('AAPL');
  const [startDate, setStartDate] = useState('2023-01-03');
  const [endDate, setEndDate] = useState('2025-12-31');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<Dict | null>(null);

  const preds = asDict(result?.predictions);
  const realized = asDict(result?.realized_volatility);
  const vix = asDict(result?.vix);
  const features = asDict(result?.features);
  const metrics = asDict(result?.metrics);
  const training = asDict(result?.training_period);
  const errorBlock = asDict(result?.forecast_error);

  async function onRun() {
    setBusy(true);
    setError('');
    try {
      const payload = await volatility.forecast({ symbol, start_date: startDate, end_date: endDate });
      setResult(asDict(payload.data));
      mutate();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Forecast failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="space-y-5 px-4 py-6 sm:px-6">
      <div>
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Trade AI</p>
        <h1 className="text-2xl font-bold text-white">Volatility Lab</h1>
        <p className="mt-2 text-sm text-slate-400">
          Advisory realized-volatility forecasts only. Not direction. Never approves trades. Never overrides Risk
          Guardian.
        </p>
      </div>
      <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm font-semibold text-amber-200">
        ADVISORY — missing VIX, term structure, or IV is shown as DATA_UNAVAILABLE. Values are never invented.
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
          Start
          <input
            type="date"
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-white"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
          />
        </label>
        <label className="text-sm text-slate-300">
          End
          <input
            type="date"
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-white"
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
          />
        </label>
        <div className="md:col-span-3">
          <button
            type="button"
            disabled={busy}
            onClick={onRun}
            className="rounded bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {busy ? 'Fitting chronological model…' : 'Run volatility forecast'}
          </button>
        </div>
        {error ? <p className="md:col-span-3 text-sm text-amber-300">{error}</p> : null}
      </section>

      {result ? (
        <section className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div className="rounded-lg border border-slate-800 p-4 text-sm text-white">
              Predicted 5d vol: {show(preds.vol_5d)}
            </div>
            <div className="rounded-lg border border-slate-800 p-4 text-sm text-white">
              Predicted 10d vol: {show(preds.vol_10d)}
            </div>
            <div className="rounded-lg border border-slate-800 p-4 text-sm text-white">
              Realized 5d vol: {show(realized.vol_5d)}
            </div>
            <div className="rounded-lg border border-slate-800 p-4 text-sm text-white">
              Realized 10d vol: {show(realized.vol_10d)}
            </div>
            <div className="rounded-lg border border-slate-800 p-4 text-sm text-white">
              VIX: {show(typeof vix.level === 'number' ? (vix.level as number) / 100 : vix.level)}
            </div>
            <div className="rounded-lg border border-slate-800 p-4 text-sm text-white">
              Current IV: {show(result.current_iv)}
            </div>
          </div>
          <div className="rounded-lg border border-slate-800 p-4 text-sm text-slate-300">
            <p>Model: {String(result.model_name)}</p>
            <p>
              Training period: {String(training.start || 'DATA_UNAVAILABLE')} → {String(training.end || 'DATA_UNAVAILABLE')}
            </p>
            <p>Forecast error 5d: {showErr(errorBlock.vol_5d)}</p>
            <p>Forecast error 10d: {showErr(errorBlock.vol_10d)}</p>
            <p>Baseline 5d: {showErr(asDict(metrics.vol_5d).baseline)}</p>
            <p className="mt-2 text-amber-200">Does not approve trades. Risk Guardian remains final authority.</p>
          </div>
          <div className="rounded-lg border border-slate-800 p-4 text-sm text-slate-300">
            <p>Available features: {((features.available as string[]) || []).join(', ') || 'none'}</p>
            <p>Unavailable features: {((features.unavailable as string[]) || []).join(', ') || 'none'}</p>
          </div>
        </section>
      ) : null}

      <section className="rounded-lg border border-slate-800 p-4 text-sm text-slate-300">
        <h2 className="font-semibold text-white">Saved advisory forecasts</h2>
        <ul className="mt-2 space-y-1">
          {forecasts.map((row: Dict) => (
            <li key={String(row.id)}>
              {String(row.created_at || '').slice(0, 19)} · {String(row.symbol)} · {String(row.model_name)} · 5d{' '}
              {show(row.vol_5d)}
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
