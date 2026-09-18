'use client';

import Link from 'next/link';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useGreeks, useDemoOrders, useDemoPortfolio, usePortfolio, usePortfolioHistory, useDemoPositions } from '@/hooks/useApi';
import { isMissing, isUnavailableDisplay, money, pct, pnlClass, text } from '@/lib/format';
import { greeksDisplay, greeksState, missingMetric } from '@/lib/marketState';
import { useDemoMode } from '@/hooks/useDemoMode';
import { SimulatedMark } from '@/components/DemoBanner';

type Dict = Record<string, unknown>;

const OCC_PATTERN = /^[A-Z]{1,6}\d{6}[CP]\d{8}$/;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

function Metric({
  label,
  value,
  valueClass = 'text-white',
  hint,
  tone = 'default',
}: {
  label: string;
  value: string;
  valueClass?: string;
  hint?: string;
  tone?: 'default' | 'neutral' | 'error';
}) {
  const unavailable = tone === 'error' || (tone === 'default' && isUnavailableDisplay(value));
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p
        className={`mt-1 font-semibold tabular-nums ${
          tone === 'neutral'
            ? 'text-xl text-slate-500'
            : unavailable
              ? 'text-sm text-amber-300'
              : `text-xl ${valueClass}`
        }`}
      >
        {value}
      </p>
      {hint ? <p className="mt-1 text-[11px] text-slate-500">{hint}</p> : null}
    </div>
  );
}

function occAndUnderlying(row: Dict): { occ: string; underlying: string } {
  const explicitOcc = row.occ_symbol;
  const explicitUnderlying = row.underlying_symbol || row.underlying;
  const symbol = typeof row.symbol === 'string' ? row.symbol.toUpperCase() : '';
  if (!isMissing(explicitOcc) || OCC_PATTERN.test(symbol)) {
    const occ = String(explicitOcc || symbol);
    const fromOcc = occ.match(/^[A-Z]+/);
    return {
      occ,
      underlying: !isMissing(explicitUnderlying) ? String(explicitUnderlying) : fromOcc ? fromOcc[0] : 'UNDERLYING NOT AVAILABLE',
    };
  }
  return {
    occ: 'EQUITY POSITION',
    underlying: symbol || 'SYMBOL NOT AVAILABLE',
  };
}

function exposure(snapshot: Dict): string {
  if (isMissing(snapshot.position_exposure) || isMissing(snapshot.account_value)) {
    return missingMetric('risk', 'EXPOSURE NOT AVAILABLE');
  }
  const account = Number(snapshot.account_value);
  const exp = Number(snapshot.position_exposure);
  if (!Number.isFinite(account) || account <= 0 || !Number.isFinite(exp)) return missingMetric('risk', 'EXPOSURE NOT AVAILABLE');
  return pct(exp / account, true);
}

function drawdown(snapshot: Dict): string {
  if (isMissing(snapshot.drawdown_pct)) return missingMetric('risk', 'DRAWDOWN NOT AVAILABLE');
  return pct(snapshot.drawdown_pct, false);
}

function greekValue(greeks: Dict, value: unknown): string {
  return greeksDisplay(greeks, value);
}

function historyPoints(history: unknown): Array<Record<string, string | number>> {
  if (!Array.isArray(history)) return [];
  const points: Array<Record<string, string | number>> = [];
  for (const item of history) {
    const row = asDict(item);
    const value = Number(row.account_value ?? row.current_equity ?? row.equity);
    if (!Number.isFinite(value)) continue;
    const pnl = Number(row.total_pnl ?? row.pnl);
    const dd = Number(row.drawdown_pct ?? row.drawdown);
    points.push({
      timestamp: typeof row.timestamp === 'string' ? row.timestamp : 'TIMESTAMP NOT AVAILABLE',
      account_value: value,
      ...(Number.isFinite(pnl) ? { total_pnl: pnl } : {}),
      ...(Number.isFinite(dd) ? { drawdown_pct: dd } : {}),
    });
  }
  return points;
}

const tooltipStyle = { backgroundColor: '#FFFFFF', border: '1px solid #E5E5E3', color: '#111111' };

export default function PortfolioPage() {
  const demo = useDemoMode();
  const { portfolio: apiPortfolio, error: portfolioError } = usePortfolio();
  const { portfolio: demoPortfolio, error: demoPortfolioError } = useDemoPortfolio();
  const { history, isLoading: historyLoading, error: historyError } = usePortfolioHistory();
  const { positions: livePositions, isLoading: positionsLoading, error: positionsError } = useDemoPositions();
  const { orders: liveOrders, isLoading: ordersLoading, error: ordersError } = useDemoOrders();
  const { greeks: liveGreeks, isLoading: greeksLoading, error: greeksError } = useGreeks();

  const portfolio = apiPortfolio || demoPortfolio;
  const positions = livePositions;
  const greeks = liveGreeks;
  const orders = liveOrders;
  const source = String(asDict(portfolio).source || '').toUpperCase();
  const isDemoLedger = source === 'DEMO_LEDGER' || Boolean(asDict(portfolio).virtual_money) || Boolean(asDict(portfolio).demo_portfolio);

  const hasPortfolio = Boolean(portfolio && typeof portfolio === 'object');
  const primaryPending = !apiPortfolio && !portfolioError;
  const demoPending = !demoPortfolio && !demoPortfolioError;
  const portfolioStatus: 'LOADING' | 'ERROR' | 'EMPTY' | 'SUCCESS' = hasPortfolio
    ? 'SUCCESS'
    : primaryPending || demoPending
      ? 'LOADING'
      : portfolioError || demoPortfolioError
        ? 'ERROR'
        : 'EMPTY';
  const greekStatus = greeksLoading && !greeks && !greeksError ? 'LOADING' : greeksState(greeks, greeksError);

  const snap = asDict(portfolio);
  const greeksDict = asDict(greeks);
  const points = historyError ? [] : historyPoints(history);
  if (isDemoLedger && points.length === 0 && typeof snap.starting_cash === 'number' && typeof snap.account_value === 'number') {
    points.push(
      { timestamp: 'Ledger start', account_value: Number(snap.starting_cash), total_pnl: 0 },
      {
        timestamp: 'Current',
        account_value: Number(snap.account_value),
        ...(Number.isFinite(Number(snap.total_pnl)) ? { total_pnl: Number(snap.total_pnl) } : {}),
        ...(Number.isFinite(Number(snap.drawdown_pct)) ? { drawdown_pct: Number(snap.drawdown_pct) } : {}),
      }
    );
  }
  const positionRows = Array.isArray(positions) ? positions.map(asDict) : [];
  const orderRows = Array.isArray(orders) ? orders.map(asDict) : [];

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div>
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Trade AI</p>
            <h1 className="text-xl font-bold text-white sm:text-2xl">Portfolio</h1>
        </div>
          <div className="flex flex-wrap items-center gap-3">
            {isDemoLedger ? (
              <span className="rounded border border-indigo-300 bg-indigo-50 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-indigo-800">
                DEMO PORTFOLIO · VIRTUAL MONEY
              </span>
            ) : (
              <span className="rounded border border-sky-700 bg-sky-950/60 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-sky-300">
                PAPER TRADING
              </span>
            )}
            {demo.enabled ? <SimulatedMark /> : null}
            <Link href="/dashboard" className="text-sm text-slate-400 hover:text-white">
              Dashboard
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
        <section>
          <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Summary</h2>
          {portfolioStatus === 'LOADING' ? (
            <p className="text-sm text-slate-400">Loading portfolio…</p>
          ) : portfolioStatus === 'ERROR' ? (
            <p className="text-sm font-semibold text-amber-300">PORTFOLIO DATA ERROR</p>
          ) : portfolioStatus === 'EMPTY' ? (
            <p className="text-sm text-slate-400">No portfolio snapshot yet.</p>
          ) : (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Metric label="Portfolio Value" value={money(snap.account_value, 'PORTFOLIO VALUE NOT AVAILABLE')} />
              <Metric label="Cash" value={money(snap.cash, 'CASH NOT AVAILABLE')} />
              <Metric label="Buying Power" value={money(snap.buying_power, 'BUYING POWER NOT AVAILABLE')} />
              <Metric label="Total P&L" value={money(snap.total_pnl, 'P&L NOT AVAILABLE')} valueClass={pnlClass(snap.total_pnl)} />
              <Metric label="Daily P&L" value={money(snap.daily_pnl, 'DAILY P&L NOT AVAILABLE')} valueClass={pnlClass(snap.daily_pnl)} />
              <Metric label="Drawdown" value={drawdown(snap)} />
              <Metric label="Exposure" value={exposure(snap)} />
              <Metric label="Positions" value={positionsError ? 'POSITIONS NOT LOADED' : String(positionRows.length)} />
                </div>
          )}
        </section>

        <section className="rounded-xl border border-slate-700/80 bg-slate-900/70 p-5">
          <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Portfolio Greeks</h2>
          {greekStatus === 'LOADING' ? (
            <p className="text-sm text-slate-400">Loading Greeks…</p>
          ) : greekStatus === 'ERROR' ? (
            <p className="text-sm text-amber-300">Greeks request failed. This is not a portfolio data error.</p>
          ) : greekStatus === 'NO_OPTION_POSITIONS' ? (
            <>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <Metric label="Delta" value="—" hint="No option positions" tone="neutral" />
                <Metric label="Gamma" value="—" hint="No option positions" tone="neutral" />
                <Metric label="Theta" value="—" hint="No option positions" tone="neutral" />
                <Metric label="Vega" value="—" hint="No option positions" tone="neutral" />
                </div>
              <p className="mt-3 text-xs text-slate-500">Greeks are calculated only for currently held option positions.</p>
            </>
          ) : greekStatus === 'GREEKS_UNAVAILABLE' ? (
            <>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <Metric label="Delta" value="GREEKS DATA UNAVAILABLE" tone="error" />
                <Metric label="Gamma" value="GREEKS DATA UNAVAILABLE" tone="error" />
                <Metric label="Theta" value="GREEKS DATA UNAVAILABLE" tone="error" />
                <Metric label="Vega" value="GREEKS DATA UNAVAILABLE" tone="error" />
                </div>
              <p className="mt-3 text-xs text-slate-500">
                {String(greeksDict.notes || 'Option positions exist but required Greek inputs are missing.')}
              </p>
            </>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                <Metric label="Delta" value={greekValue(greeksDict, greeksDict.delta ?? greeksDict.portfolio_delta)} />
                <Metric label="Gamma" value={greekValue(greeksDict, greeksDict.gamma ?? greeksDict.portfolio_gamma)} />
                <Metric label="Theta" value={greekValue(greeksDict, greeksDict.theta ?? greeksDict.portfolio_theta)} />
                <Metric label="Vega" value={greekValue(greeksDict, greeksDict.vega ?? greeksDict.portfolio_vega)} />
              </div>
              {greeksDict.notes ? <p className="mt-3 text-xs text-slate-500">{String(greeksDict.notes)}</p> : null}
            </>
          )}
        </section>

        <section className="rounded-xl border border-slate-700/80 bg-slate-900/70 p-5">
          <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
            History {demo.enabled ? '· SIMULATED' : ''}
          </h2>
          {historyLoading && points.length === 0 && !historyError ? (
            <p className="text-sm text-slate-400">Loading portfolio history…</p>
          ) : points.length === 0 ? (
            <p className="text-sm text-slate-300">No portfolio history available</p>
          ) : (
            <div className="space-y-6">
              <div>
                <h3 className="mb-2 text-sm font-medium text-slate-300">Portfolio value</h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={points}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="timestamp" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                      <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                      <Tooltip contentStyle={tooltipStyle} />
                      <Line type="monotone" dataKey="account_value" stroke="#22c55e" dot={false} name="Portfolio value" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
              </div>
              {points.some((point) => 'total_pnl' in point) ? (
                <div>
                  <h3 className="mb-2 text-sm font-medium text-slate-300">Total P&L</h3>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={points}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                        <XAxis dataKey="timestamp" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                        <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                        <Tooltip contentStyle={tooltipStyle} />
                        <Area type="monotone" dataKey="total_pnl" stroke="#3b82f6" fill="#1d4ed8" fillOpacity={0.25} name="Total P&L" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
                </div>
              ) : null}
              {points.some((point) => 'drawdown_pct' in point) ? (
                <div>
                  <h3 className="mb-2 text-sm font-medium text-slate-300">Drawdown</h3>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={points}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                        <XAxis dataKey="timestamp" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                        <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                        <Tooltip contentStyle={tooltipStyle} />
                        <Area type="monotone" dataKey="drawdown_pct" stroke="#ef4444" fill="#7f1d1d" fillOpacity={0.3} name="Drawdown" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
                </div>
              ) : null}
            </div>
          )}
        </section>

        <section className="rounded-xl border border-slate-700/80 bg-slate-900/70 p-5">
          <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Positions</h2>
          {positionsError && positionRows.length === 0 ? (
            <p className="text-sm font-semibold text-amber-300">POSITIONS NOT LOADED</p>
          ) : positionsLoading && positionRows.length === 0 ? (
            <p className="text-sm text-slate-400">Loading positions…</p>
          ) : positionRows.length === 0 ? (
            <p className="text-sm text-slate-400">No open positions</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-[1100px] w-full text-left text-sm">
                <thead className="text-[11px] uppercase tracking-wide text-slate-500">
                  <tr>
                    {[
                      'OCC contract',
                      'Underlying',
                      'Strike',
                      'Type',
                      'Expiration',
                      'Quantity',
                      'Price',
                      'P&L',
                      'Delta',
                      'Gamma',
                      'Theta',
                      'Vega',
                    ].map((header) => (
                      <th key={header} className="border-b border-slate-800 pb-2 pr-4 font-medium">
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {positionRows.map((row, idx) => {
                    const ids = occAndUnderlying(row);
                    return (
                      <tr key={String(row.position_id || idx)} className="border-b border-slate-800/80">
                        <td className="py-2.5 pr-4 font-mono text-xs text-slate-200">{ids.occ}</td>
                        <td className="py-2.5 pr-4 text-white">{ids.underlying}</td>
                        <td className="py-2.5 pr-4 tabular-nums">{money(row.strike)}</td>
                        <td className="py-2.5 pr-4 uppercase">{text(row.option_type || row.type)}</td>
                        <td className="py-2.5 pr-4">{text(row.expiration)}</td>
                        <td className="py-2.5 pr-4 tabular-nums">{isMissing(row.quantity) ? 'QUANTITY NOT AVAILABLE' : String(row.quantity)}</td>
                        <td className="py-2.5 pr-4 tabular-nums">{money(row.current_price ?? row.entry_price, 'PRICE NOT AVAILABLE')}</td>
                        <td className={`py-2.5 pr-4 tabular-nums ${pnlClass(row.unrealized_pnl)}`}>{money(row.unrealized_pnl, 'P&L NOT AVAILABLE')}</td>
                        <td className="py-2.5 pr-4 tabular-nums">{ids.occ === 'EQUITY POSITION' ? 'NO OPTION GREEKS' : greekValue(greeksDict, row.delta)}</td>
                        <td className="py-2.5 pr-4 tabular-nums">{ids.occ === 'EQUITY POSITION' ? 'NO OPTION GREEKS' : greekValue(greeksDict, row.gamma)}</td>
                        <td className="py-2.5 pr-4 tabular-nums">{ids.occ === 'EQUITY POSITION' ? 'NO OPTION GREEKS' : greekValue(greeksDict, row.theta)}</td>
                        <td className="py-2.5 pr-4 tabular-nums">{ids.occ === 'EQUITY POSITION' ? 'NO OPTION GREEKS' : greekValue(greeksDict, row.vega)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
          </div>
        )}
        </section>

        <section className="rounded-xl border border-slate-700/80 bg-slate-900/70 p-5">
          <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Orders</h2>
          {ordersError && orderRows.length === 0 ? (
            <p className="text-sm font-semibold text-amber-300">ORDERS NOT LOADED</p>
          ) : ordersLoading && orderRows.length === 0 ? (
            <p className="text-sm text-slate-400">Loading orders…</p>
          ) : orderRows.length === 0 ? (
            <p className="text-sm text-slate-400">No tracked orders</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-[720px] w-full text-left text-sm">
                <thead className="text-[11px] uppercase tracking-wide text-slate-500">
                  <tr>
                    {['Symbol / OCC', 'Side', 'Quantity', 'Limit', 'Status', 'Submitted'].map((header) => (
                      <th key={header} className="border-b border-slate-800 pb-2 pr-4 font-medium">
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {orderRows.map((row, idx) => (
                    <tr key={String(row.order_id || idx)} className="border-b border-slate-800/80">
                      <td className="py-2.5 pr-4 font-mono text-xs text-white">{text(row.symbol)}</td>
                      <td className="py-2.5 pr-4 uppercase">{text(row.side)}</td>
                      <td className="py-2.5 pr-4 tabular-nums">{isMissing(row.quantity) ? 'QUANTITY NOT AVAILABLE' : String(row.quantity)}</td>
                      <td className="py-2.5 pr-4 tabular-nums">{money(row.limit_price ?? row.price)}</td>
                      <td className="py-2.5 pr-4">{text(row.status)}</td>
                      <td className="py-2.5 pr-4 text-slate-400">{text(row.submitted_at ?? row.timestamp)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
      </div>
          )}
        </section>
      </main>
    </div>
  );
}
