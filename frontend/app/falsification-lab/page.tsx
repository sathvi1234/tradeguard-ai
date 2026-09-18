'use client';

import { useState } from 'react';
import { falsification } from '@/lib/api';
import { useBacktestStrategies, useFalsificationReports } from '@/hooks/useApi';
import { QUICK_SWITCH } from '@/lib/symbols';

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

function fmt(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'n/a';
  if (typeof value === 'number' && Number.isFinite(value)) {
    if (Math.abs(value) <= 2) return `${(value * 100).toFixed(2)}%`;
    return value.toFixed(4);
  }
  return String(value);
}

function tone(state: string): string {
  if (state === 'PASS') return 'text-emerald-300';
  if (state === 'WARNING') return 'text-amber-300';
  if (state === 'FAIL') return 'text-rose-300';
  return 'text-slate-400';
}

export default function FalsificationLabPage() {
  const { strategies } = useBacktestStrategies();
  const { reports, mutate } = useFalsificationReports();
  const [symbol, setSymbol] = useState('AAPL');
  const [strategy, setStrategy] = useState('sma_crossover');
  const [startDate, setStartDate] = useState('2024-01-02');
  const [endDate, setEndDate] = useState('2025-12-31');
  const [capital, setCapital] = useState('100000');
  const [positionSize, setPositionSize] = useState('10');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<Dict | null>(null);

  const summary = asDict(result?.summary);
  const tests = Array.isArray(result?.tests) ? (result?.tests as Dict[]) : [];

  async function onRun() {
    setBusy(true);
    setError('');
    try {
      const payload = await falsification.run({
        symbol,
        strategy,
        start_date: startDate,
        end_date: endDate,
        initial_capital: Number(capital),
        position_size: Number(positionSize) / 100,
      });
      setResult(asDict(payload.data));
      mutate();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falsification run failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="space-y-5 px-4 py-6 sm:px-6">
      <div>
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Trade AI</p>
        <h1 className="text-2xl font-bold text-white">Falsification Lab</h1>
        <p className="mt-2 text-sm text-slate-400">
          Research-only challenges of historical backtests. Never live trading. Never overrides Risk Guardian.
        </p>
      </div>

      <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm font-semibold text-amber-200">
        FALSIFICATION RESEARCH — passing tests does not prove a strategy is profitable. Not live returns.
      </div>

      <section className="grid gap-3 rounded-lg border border-slate-800 bg-slate-950/40 p-4 md:grid-cols-3">
        <label className="text-sm text-slate-300">
          Strategy
          <select
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-white"
            value={strategy}
            onChange={(event) => setStrategy(event.target.value)}
          >
            {(strategies.length
              ? strategies
              : [
                  { key: 'sma_crossover', name: 'SMA Crossover' },
                  { key: 'rsi_mean_reversion', name: 'RSI Mean Reversion' },
                  { key: 'macd_trend', name: 'MACD Trend' },
                  { key: 'buy_and_hold', name: 'Buy and Hold' },
                ]
            ).map((item: Dict) => (
              <option key={String(item.key)} value={String(item.key)}>
                {String(item.name || item.key)}
              </option>
            ))}
          </select>
        </label>
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
          Initial capital
          <input
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-white"
            value={capital}
            onChange={(event) => setCapital(event.target.value)}
          />
        </label>
        <label className="text-sm text-slate-300">
          Historical start
          <input
            type="date"
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-white"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
          />
        </label>
        <label className="text-sm text-slate-300">
          Historical end
          <input
            type="date"
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-white"
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
          />
        </label>
        <label className="text-sm text-slate-300">
          Position size (% of equity)
          <input
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-white"
            value={positionSize}
            onChange={(event) => setPositionSize(event.target.value)}
          />
        </label>
        <div className="md:col-span-3">
          <button
            type="button"
            disabled={busy}
            onClick={onRun}
            className="rounded bg-indigo-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {busy ? 'Running falsification tests…' : 'Run falsification tests'}
          </button>
        </div>
        {error ? <p className="md:col-span-3 text-sm text-amber-300">{error}</p> : null}
      </section>

      {result ? (
        <section className="space-y-4">
          <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
            <p className={`text-lg font-bold ${tone(String(result.overall_state))}`}>
              Overall: {String(result.overall_state)}
            </p>
            <p className="mt-1 text-sm text-slate-400">{String(result.disclaimer)}</p>
            <div className="mt-3 grid gap-2 sm:grid-cols-5 text-sm text-slate-200">
              <span>Total {String(summary.total_tests ?? tests.length)}</span>
              <span className="text-emerald-300">Passed {String(summary.passed_tests ?? 0)}</span>
              <span className="text-rose-300">Failed {String(summary.failed_tests ?? 0)}</span>
              <span className="text-amber-300">Warnings {String(summary.warnings ?? 0)}</span>
              <span className="text-slate-400">Inconclusive {String(summary.inconclusive_tests ?? 0)}</span>
            </div>
          </div>
          <div className="space-y-2">
            {tests.map((row) => (
              <article key={String(row.test)} className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-sm font-semibold text-white">{String(row.test)}</h2>
                  <span className={`text-xs font-bold uppercase ${tone(String(row.state))}`}>{String(row.state)}</span>
                </div>
                <p className="mt-2 text-sm text-slate-300">{String(row.explanation)}</p>
                <dl className="mt-2 grid gap-1 text-xs text-slate-400 sm:grid-cols-2">
                  <div>Baseline ({String(row.baseline_metric_name)}): {fmt(row.baseline_metric)}</div>
                  <div>Challenged: {fmt(row.challenged_metric)}</div>
                  <div>Degradation: {fmt(row.performance_degradation)}</div>
                  <div>Timestamp: {String(row.timestamp || '')}</div>
                </dl>
                <pre className="mt-2 overflow-x-auto rounded bg-slate-900 p-2 text-[11px] text-slate-400">
                  {JSON.stringify(row.evidence || {}, null, 2)}
                </pre>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <section className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
        <h2 className="text-sm font-semibold text-white">Saved falsification reports</h2>
        <ul className="mt-2 space-y-1 text-sm text-slate-300">
          {reports.map((row: Dict) => (
            <li key={String(row.id)}>
              {String(row.created_at || '').slice(0, 19)} · {String(row.symbol)} · {String(row.strategy)} ·{' '}
              {String(row.overall_state)} · not proven profitable
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
