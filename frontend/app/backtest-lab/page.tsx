'use client';

import { useMemo, useState } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { backtest } from '@/lib/api';
import { useBacktestRuns, useBacktestStrategies } from '@/hooks/useApi';
import { QUICK_SWITCH } from '@/lib/symbols';

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

function fmtPct(value: unknown): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'n/a';
  return `${(value * 100).toFixed(2)}%`;
}

function fmtNum(value: unknown, digits = 2): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'n/a';
  return value.toFixed(digits);
}

function fmtMoney(value: unknown): string {
  if (typeof value !== 'number' || Number.isNaN(value)) return 'n/a';
  return value.toLocaleString('en-US', { style: 'currency', currency: 'USD' });
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-sm font-semibold tabular-nums text-white">{value}</p>
    </div>
  );
}

export default function BacktestLabPage() {
  const { strategies } = useBacktestStrategies();
  const { runs, mutate } = useBacktestRuns();
  const [symbol, setSymbol] = useState('AAPL');
  const [strategy, setStrategy] = useState('sma_crossover');
  const [startDate, setStartDate] = useState('2024-01-02');
  const [endDate, setEndDate] = useState('2025-12-31');
  const [capital, setCapital] = useState('100000');
  const [positionSize, setPositionSize] = useState('10');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<Dict | null>(null);

  const metrics = asDict(result?.metrics);
  const equity = useMemo(() => {
    const curve = Array.isArray(result?.equity_curve) ? (result?.equity_curve as Dict[]) : [];
    return curve.map((point) => ({
      t: String(point.timestamp || '').slice(0, 10),
      equity: typeof point.equity === 'number' ? point.equity : 0,
    }));
  }, [result]);
  const drawdown = useMemo(() => {
    const curve = Array.isArray(metrics.drawdown_curve) ? (metrics.drawdown_curve as Dict[]) : [];
    return curve.map((point) => ({
      t: String(point.timestamp || '').slice(0, 10),
      drawdown: typeof point.drawdown === 'number' ? point.drawdown * 100 : 0,
    }));
  }, [metrics.drawdown_curve]);

  async function onRun() {
    setBusy(true);
    setError('');
    try {
      const payload = await backtest.run({
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
      const message = err instanceof Error ? err.message : 'Backtest failed';
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="space-y-5 px-4 py-6 sm:px-6">
      <div>
        <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Trade AI</p>
        <h1 className="text-2xl font-bold text-white">Backtest Lab</h1>
        <p className="mt-2 text-sm text-slate-400">
          Event-driven historical simulation on prior bars only. Not live trading. Not live returns.
        </p>
      </div>

      <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm font-semibold uppercase tracking-wide text-amber-200">
        HISTORICAL SIMULATION — never live returns
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
          Start date
          <input
            type="date"
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-white"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
          />
        </label>
        <label className="text-sm text-slate-300">
          End date
          <input
            type="date"
            className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-2 text-white"
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
          />
        </label>
        <label className="text-sm text-slate-300">
          Position size (% of equity, max 30%)
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
            {busy ? 'Running historical simulation…' : 'Run historical simulation'}
          </button>
        </div>
        {error ? <p className="md:col-span-3 text-sm text-amber-300">{error}</p> : null}
      </section>

      {result ? (
        <section className="space-y-4">
          <p className="text-xs font-bold uppercase tracking-wide text-amber-200">
            {String(result.result_label || 'HISTORICAL SIMULATION')} · {String(result.symbol)} ·{' '}
            {String(result.strategy)} · not live returns
          </p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Total return" value={fmtPct(metrics.total_return)} />
            <Metric label="Annualized return" value={fmtPct(metrics.annualized_return)} />
            <Metric label="Win rate" value={fmtPct(metrics.win_rate)} />
            <Metric label="Average win" value={fmtMoney(metrics.average_win)} />
            <Metric label="Average loss" value={fmtMoney(metrics.average_loss)} />
            <Metric label="Expectancy" value={fmtMoney(metrics.expectancy)} />
            <Metric label="Profit factor" value={fmtNum(metrics.profit_factor)} />
            <Metric label="Sharpe ratio" value={fmtNum(metrics.sharpe_ratio)} />
            <Metric label="Sortino ratio" value={fmtNum(metrics.sortino_ratio)} />
            <Metric label="Max drawdown" value={fmtPct(metrics.maximum_drawdown)} />
            <Metric label="Volatility" value={fmtPct(metrics.volatility)} />
            <Metric label="Number of trades" value={fmtNum(metrics.number_of_trades, 0)} />
            <Metric label="Avg holding period (days)" value={fmtNum(metrics.average_holding_period_days)} />
            <Metric label="Best trade" value={fmtMoney(metrics.best_trade)} />
            <Metric label="Worst trade" value={fmtMoney(metrics.worst_trade)} />
            <Metric label="Final equity" value={fmtMoney(metrics.final_equity)} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <Metric
              label="Buy & hold (same symbol)"
              value={fmtPct(asDict(result.buy_and_hold).total_return)}
            />
            <Metric
              label="SPY buy & hold"
              value={fmtPct(asDict(result.spy_comparison).total_return)}
            />
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
            <h2 className="mb-2 text-sm font-semibold text-white">Equity curve (historical simulation)</h2>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={equity}>
                  <CartesianGrid stroke="#1e293b" />
                  <XAxis dataKey="t" stroke="#64748b" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Area type="monotone" dataKey="equity" stroke="#818cf8" fill="#312e81" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
            <h2 className="mb-2 text-sm font-semibold text-white">Drawdown (historical simulation)</h2>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={drawdown}>
                  <CartesianGrid stroke="#1e293b" />
                  <XAxis dataKey="t" stroke="#64748b" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Area type="monotone" dataKey="drawdown" stroke="#f59e0b" fill="#78350f" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </section>
      ) : null}

      <section className="rounded-lg border border-slate-800 bg-slate-950/40 p-4">
        <h2 className="text-sm font-semibold text-white">Saved historical simulations</h2>
        <ul className="mt-2 space-y-1 text-sm text-slate-300">
          {runs.map((row: Dict) => (
            <li key={String(row.id)}>
              {String(row.created_at || '').slice(0, 19)} · {String(row.symbol)} · {String(row.strategy)} ·{' '}
              {fmtPct(row.total_return)} · HISTORICAL SIMULATION
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
