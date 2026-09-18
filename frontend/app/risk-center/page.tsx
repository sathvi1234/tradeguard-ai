'use client';

import Link from 'next/link';
import {
  useActivity,
  useAutonomousStatus,
  useBodyguard,
  usePortfolio,
  usePositions,
} from '@/hooks/useApi';
import { isMissing, isUnavailableDisplay, money, pct, text } from '@/lib/format';
import { missingMetric } from '@/lib/marketState';
import { useDemoMode } from '@/hooks/useDemoMode';
import { SimulatedMark } from '@/components/DemoBanner';

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function ratioFromPercentOrRatio(value: unknown): string {
  if (isMissing(value)) return missingMetric('risk');
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return missingMetric('risk');
  return n > 1 ? pct(n, false) : pct(n, true);
}

function limitValue(key: string, value: unknown): string {
  if (isMissing(value)) return missingMetric('risk');
  const n = typeof value === 'number' ? value : Number(value);
  if (!Number.isFinite(n)) return text(value);
  if (
    key.includes('drawdown') ||
    key.includes('exposure') ||
    key.includes('daily_loss') ||
    key.includes('confidence')
  ) {
    return pct(n, true);
  }
  if (key.includes('size')) return money(n);
  if (key.includes('ratio')) return n.toFixed(2);
  if (Number.isInteger(n)) return String(n);
  return String(n);
}

function dailyLoss(dailyPnl: unknown): string {
  if (isMissing(dailyPnl)) return missingMetric('risk', 'DAILY P&L NOT AVAILABLE');
  const n = typeof dailyPnl === 'number' ? dailyPnl : Number(dailyPnl);
  if (!Number.isFinite(n)) return missingMetric('risk', 'DAILY P&L NOT AVAILABLE');
  return money(n < 0 ? Math.abs(n) : 0);
}

function concentration(positions: unknown, accountValue: unknown): string {
  if (!Array.isArray(positions)) return missingMetric('risk', 'POSITIONS NOT LOADED');
  if (positions.length === 0) return pct(0, true);
  if (isMissing(accountValue)) return missingMetric('risk', 'ACCOUNT VALUE REQUIRED FOR CONCENTRATION');
  const equity = typeof accountValue === 'number' ? accountValue : Number(accountValue);
  if (!Number.isFinite(equity) || equity <= 0) return missingMetric('risk', 'ACCOUNT VALUE REQUIRED FOR CONCENTRATION');
  const bySymbol: Record<string, number> = {};
  let counted = 0;
  for (const row of positions) {
    const pos = asDict(row);
    const symbol = typeof pos.symbol === 'string' ? pos.symbol : '';
    const exposure = typeof pos.total_exposure === 'number' ? pos.total_exposure : Number(pos.total_exposure);
    if (!symbol || !Number.isFinite(exposure)) continue;
    bySymbol[symbol] = (bySymbol[symbol] || 0) + exposure;
    counted += 1;
  }
  if (!counted) return missingMetric('risk', 'CONCENTRATION NOT AVAILABLE');
  const peak = Math.max(...Object.values(bySymbol));
  return pct(peak / equity, true);
}

function exposure(snapshot: Dict): string {
  if (isMissing(snapshot.position_exposure) || isMissing(snapshot.account_value)) {
    if (typeof snapshot.exposure_pct === 'number') return pct(snapshot.exposure_pct, true);
    return missingMetric('risk', 'EXPOSURE NOT AVAILABLE');
  }
  const account = Number(snapshot.account_value);
  const exp = Number(snapshot.position_exposure);
  if (!Number.isFinite(account) || account <= 0 || !Number.isFinite(exp)) return missingMetric('risk', 'EXPOSURE NOT AVAILABLE');
  return pct(exp / account, true);
}

function Metric({ label, value, valueClass = 'text-white' }: { label: string; value: string; valueClass?: string }) {
  const unavailable = isUnavailableDisplay(value);
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-4">
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-1 font-semibold tabular-nums ${unavailable ? 'text-sm text-amber-300' : `text-xl ${valueClass}`}`}>
        {value}
      </p>
    </div>
  );
}

export default function RiskCenter() {
  const demo = useDemoMode();
  const { portfolio: livePortfolio, isLoading: portfolioLoading, error: portfolioError } = usePortfolio();
  const { status: liveStatus, isLoading: statusLoading, error: statusError } = useAutonomousStatus();
  const { bodyguard: liveBodyguard, isLoading: bodyguardLoading, error: bodyguardError } = useBodyguard();
  const { positions: livePositions, error: positionsError } = usePositions();
  const { activity: liveActivity, error: activityError } = useActivity();

  const portfolio = demo.enabled ? demo.bundle.portfolio : livePortfolio;
  const status = demo.enabled ? demo.bundle.status : liveStatus;
  const bodyguard = demo.enabled ? demo.bundle.bodyguard : liveBodyguard;
  const positions = demo.enabled ? demo.bundle.positions : livePositions;
  const activity = demo.enabled ? demo.bundle.activity : liveActivity;

  const engine = asDict(status);
  const snapshot = Object.keys(asDict(portfolio)).length ? asDict(portfolio) : asDict(engine.portfolio);
  const dd = asDict(engine.drawdown_guardian);
  const ddState = asDict(dd.state);
  const limits = asDict(engine.risk_limits);
  const debate = asDict(engine.last_debate);
  const rgLatest = asDict(debate.risk_guardian_result);
  const red = asDict(engine.last_red_team);
  const guard = asDict(bodyguard);
  const mode = String(engine.current_mode || ddState.current_mode || '').toLowerCase();
  const isCritical = mode === 'critical';

  const peak = !isMissing(ddState.peak_equity) ? ddState.peak_equity : snapshot.peak_equity;
  const equity = !isMissing(ddState.current_equity) ? ddState.current_equity : snapshot.current_equity ?? snapshot.account_value;
  const drawdown = !isMissing(ddState.drawdown_percentage)
    ? pct(ddState.drawdown_percentage, true)
    : engine.current_mode
      ? pct(engine.current_drawdown, true)
      : ratioFromPercentOrRatio(snapshot.drawdown_pct);
  const dailyPnl = !isMissing(ddState.daily_pnl) ? ddState.daily_pnl : snapshot.daily_pnl;

  const transitions = asList(dd.transitions).map(asDict);
  const criticalTransition = [...transitions].reverse().find((item) => String(item.new_mode).toLowerCase() === 'critical');
  const redWarnings = [...asList(red.objections).map(String), ...asList(red.risk_flags).map(String)];
  const bodyReasons = asList(guard.reasons).map(String);

  const rgFromActivity = asList(activity)
    .map(asDict)
    .filter((event) => {
      const type = String(event.event_type || '');
      return type === 'risk_rejection' || type === 'risk_approval';
    });
  const rgDecisions: Dict[] = [];
  if (Object.keys(rgLatest).length) rgDecisions.push(rgLatest);
  for (const event of rgFromActivity) {
    rgDecisions.push({
      timestamp: event.timestamp,
      decision: String(event.event_type) === 'risk_approval' ? 'approved' : 'rejected',
      reason: event.message,
      symbol: event.symbol,
      metadata: event.metadata,
    });
  }

  const loading = demo.enabled ? false : (portfolioLoading || statusLoading || bodyguardLoading) && !status && !portfolio;
  const failed = demo.enabled ? false : Boolean(statusError && portfolioError && bodyguardError);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-8">
          <div>
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Trade AI</p>
            <h1 className="text-xl font-bold text-white sm:text-2xl">Risk Center</h1>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded border border-sky-700 bg-sky-950/60 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-sky-300">
              PAPER TRADING
            </span>
            {demo.enabled ? <SimulatedMark /> : null}
            <Link href="/dashboard" className="text-sm text-slate-400 hover:text-white">
              Dashboard
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
        <p className="rounded-xl border border-slate-700 bg-slate-900/70 px-4 py-3 text-sm font-medium text-slate-200">
          AI recommends. Deterministic Risk Guardian decides.
        </p>

        {loading ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-6 py-16 text-center text-slate-400">
            Loading risk data…
          </div>
        ) : failed ? (
          <div className="rounded-xl border border-rose-800 bg-rose-950/40 px-6 py-16 text-center text-rose-200">
            Unable to load backend risk data
          </div>
        ) : (
          <>
            {isCritical ? (
              <section className="rounded-xl border-2 border-rose-500 bg-rose-950/70 p-5 shadow-[0_0_40px_rgba(244,63,94,0.25)]">
                <p className="text-xs font-bold uppercase tracking-[0.2em] text-rose-300">Critical</p>
                <h2 className="mt-2 text-3xl font-bold text-white">New trades are blocked</h2>
                <p className="mt-3 text-sm text-rose-100">
                  {text(
                    criticalTransition?.reason ||
                      engine.last_cycle_message ||
                      (bodyReasons.find((item) => item.toLowerCase().includes('critical')) ?? null) ||
                      guard.action
                  )}
                </p>
                <p className="mt-2 text-sm text-rose-200">
                  Drawdown Guardian mode is CRITICAL. Risk Bodyguard freeze_new_trades={' '}
                  {typeof guard.freeze_new_trades === 'boolean' ? String(guard.freeze_new_trades) : 'NOT REPORTED'}.
                </p>
              </section>
            ) : null}

            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {(['normal', 'protection', 'critical'] as const).map((item) => (
                <div
                  key={item}
                  className={`rounded-xl border px-4 py-4 text-center ${
                    mode === item
                      ? item === 'critical'
                        ? 'border-rose-500 bg-rose-950/50 text-rose-100'
                        : item === 'protection'
                          ? 'border-amber-500 bg-amber-950/40 text-amber-100'
                          : 'border-emerald-500 bg-emerald-950/40 text-emerald-100'
                      : 'border-slate-800 bg-slate-950/40 text-slate-500'
                  }`}
                >
                  <p className="text-lg font-bold uppercase">{item}</p>
                  {item === 'critical' && mode === 'critical' ? (
                    <p className="mt-2 text-xs font-semibold uppercase tracking-wide">New Trades Blocked</p>
                  ) : null}
                </div>
              ))}
            </div>

            <section
              className={`rounded-xl border-2 p-5 ${
                mode === 'critical'
                  ? 'border-rose-500 bg-rose-950/40 text-rose-100'
                  : mode === 'protection'
                    ? 'border-amber-500 bg-amber-950/30 text-amber-100'
                    : mode === 'normal'
                      ? 'border-emerald-500 bg-emerald-950/30 text-emerald-100'
                      : 'border-slate-700 bg-slate-900/70 text-slate-200'
              }`}
            >
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] opacity-80">Current trading mode</p>
              <p className="mt-2 text-3xl font-bold uppercase">{mode || 'MODE NOT REPORTED'}</p>
            </section>

            <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <Metric label="Peak equity" value={statusError && isMissing(peak) ? missingMetric('risk', 'PEAK EQUITY NOT AVAILABLE') : money(peak, 'PEAK EQUITY NOT AVAILABLE')} />
              <Metric label="Current equity" value={portfolioError && isMissing(equity) ? missingMetric('risk', 'EQUITY NOT AVAILABLE') : money(equity, 'EQUITY NOT AVAILABLE')} />
              <Metric label="Drawdown" value={drawdown} />
              <Metric label="Daily loss" value={dailyLoss(dailyPnl)} />
              <Metric label="Exposure" value={exposure(snapshot)} />
              <Metric
                label="Concentration"
                value={positionsError ? missingMetric('risk', 'POSITIONS NOT LOADED') : concentration(positions, snapshot.account_value ?? equity)}
              />
            </section>

            <section className="rounded-xl border border-slate-700/80 bg-slate-900/70 p-5">
              <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Risk limits</h2>
              {Object.keys(limits).length === 0 ? (
                <p className="text-sm font-semibold text-amber-300">RISK LIMITS NOT LOADED</p>
              ) : (
                <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {Object.entries(limits).map(([key, value]) => (
                    <div key={key} className="rounded-lg border border-slate-800 bg-slate-950/40 p-3">
                      <dt className="text-[11px] uppercase tracking-wide text-slate-500">{key.replace(/_/g, ' ')}</dt>
                      <dd className="mt-1 font-semibold tabular-nums text-white">{limitValue(key, value)}</dd>
                    </div>
                  ))}
                </dl>
              )}
            </section>

            <section className="rounded-xl border border-slate-700/80 bg-slate-900/70 p-5">
              <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">RiskGuardian decisions</h2>
              {rgDecisions.length === 0 ? (
                <p className="text-sm font-semibold text-amber-300">NO RISK GUARDIAN DECISIONS YET</p>
              ) : (
                <div className="space-y-3">
                  {rgDecisions.map((decision, idx) => {
                    const verdict = String(decision.decision || '').toLowerCase();
                    const reasons = asList(decision.rejection_reasons).map(String);
                    return (
                      <div
                        key={idx}
                        className={`rounded-lg border p-4 ${
                          verdict === 'approved' ? 'border-emerald-800 bg-emerald-950/30' : 'border-rose-800 bg-rose-950/30'
                        }`}
                      >
                        <p className="text-sm font-semibold uppercase text-white">{text(decision.decision)}</p>
                        <p className="mt-1 text-sm text-slate-300">
                          {text(decision.reason || reasons.join(' · ') || asList(engine.last_rejection_reasons).map(String).join(' · '))}
                        </p>
                        <p className="mt-2 text-xs text-slate-500">{text(decision.timestamp)}</p>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="rounded-xl border border-slate-700/80 bg-slate-900/70 p-5">
              <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Red Team warnings</h2>
              {redWarnings.length === 0 ? (
                <p className="text-sm font-semibold text-amber-300">NO RED TEAM WARNINGS THIS CYCLE</p>
              ) : (
                <ul className="list-disc space-y-1 pl-5 text-sm text-amber-200">
                  {typeof red.severity === 'string' ? <li>Severity: {red.severity}</li> : null}
                  {redWarnings.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              )}
            </section>

            <section className="rounded-xl border border-slate-700/80 bg-slate-900/70 p-5">
              <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">RiskBodyguard status</h2>
              {(!demo.enabled && bodyguardError) || Object.keys(guard).length === 0 ? (
                <p className="text-sm font-semibold text-amber-300">RISK BODYGUARD STATUS NOT LOADED</p>
              ) : (
                <div className="space-y-2 text-sm text-slate-200">
                  <p>
                    <span className="text-slate-500">Action: </span>
                    {text(guard.action)}
                  </p>
                  <p>
                    <span className="text-slate-500">Freeze new trades: </span>
                    {typeof guard.freeze_new_trades === 'boolean' ? String(guard.freeze_new_trades) : 'NOT REPORTED'}
                  </p>
                  <p>
                    <span className="text-slate-500">Positions reviewed: </span>
                    {isMissing(guard.positions_reviewed) ? 'NOT REPORTED' : String(guard.positions_reviewed)}
                  </p>
                  <p>
                    <span className="text-slate-500">Drawdown mode: </span>
                    {text(guard.drawdown_mode)}
                  </p>
                  <div>
                    <p className="text-slate-500">Reasons</p>
                    {bodyReasons.length === 0 ? (
                      <p className="font-semibold text-amber-300">NO BODYGUARD REASONS REPORTED</p>
                    ) : (
                      <ul className="mt-1 list-disc pl-5">
                        {bodyReasons.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>
              )}
            </section>

            <section className="rounded-xl border border-slate-700/80 bg-slate-900/70 p-5">
              <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                DrawdownGuardian transitions
              </h2>
              {transitions.length === 0 ? (
                <p className="text-sm font-semibold text-amber-300">NO DRAWDOWN TRANSITIONS YET</p>
              ) : (
                <div className="space-y-3">
                  {transitions.map((event, idx) => (
                    <div key={idx} className="rounded-lg border border-slate-800 bg-slate-950/40 p-4 text-sm">
                      <p className="font-semibold uppercase text-white">
                        {text(event.previous_mode)} → {text(event.new_mode)}
                      </p>
                      <p className="mt-1 text-slate-300">{text(event.reason)}</p>
                      <p className="mt-2 text-xs text-slate-500">
                        Drawdown {pct(event.drawdown, true)} · Equity {money(event.equity)} · {text(event.timestamp)}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </>
        )}
        {activityError ? <p className="sr-only">Activity feed unavailable</p> : null}
      </main>
    </div>
  );
}
