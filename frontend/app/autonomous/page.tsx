'use client';

import { useState } from 'react';
import Link from 'next/link';
import { autonomous } from '@/lib/api';
import { useAlpacaStatus, useAutonomousStatus, useBodyguard, useHealth, useMarketData } from '@/hooks/useApi';
import { isMissing, isUnavailableDisplay, text } from '@/lib/format';
import { marketStatusLabel, sessionLabel, toMarketState } from '@/lib/marketState';
import { collectConfidence, CONFIDENCE_NOT_PROVIDED } from '@/lib/agentDisplay';
import { explainReason, formatCycleStatus, formatDecision, pickFirstReason, reasonCodeLabel } from '@/lib/reasonCodes';
import { useDemoMode } from '@/hooks/useDemoMode';
import { SimulatedMark } from '@/components/DemoBanner';

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function currentSymbol(status: Dict): string | null {
  const debate = asDict(status.last_debate);
  const decision = asDict(status.last_decision);
  const nested = asDict(decision.data);
  const selected = asDict(nested.selected_contracts || decision.selected_contracts);
  const intel = asDict(status.last_market_intelligence);
  const candidates = [debate.symbol, decision.symbol, nested.symbol, selected.underlying_symbol, selected.symbol, intel.symbol];
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim()) return candidate.trim().toUpperCase();
  }
  return null;
}

function decisionBody(status: Dict): Dict {
  const last = asDict(status.last_decision);
  const nested = asDict(last.data);
  const debate = asDict(status.last_debate);
  const fromDebate = asDict(debate.final_decision);
  return Object.keys(nested).length ? nested : Object.keys(last).length ? last : fromDebate;
}

function Field({ label, value }: { label: string; value: string }) {
  const unavailable = isUnavailableDisplay(value);
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className={`mt-1 text-sm font-semibold ${unavailable ? 'text-amber-300' : 'text-white'}`}>{value}</p>
    </div>
  );
}

function apiErrorMessage(error: unknown): string {
  if (!error) return 'NO ERROR';
  const err = error as { response?: { data?: { detail?: string } }; message?: string };
  return err.response?.data?.detail || err.message || 'Request failed';
}

const PIPELINE = [
  { id: 'market_intelligence', label: 'Market Intelligence' },
  { id: 'market_scout', label: 'Market Scout' },
  { id: 'strategy_brain', label: 'Strategy Brain' },
  { id: 'bull_agent', label: 'Bull' },
  { id: 'bear_agent', label: 'Bear' },
  { id: 'red_team', label: 'Red Team' },
  { id: 'strategy_agent', label: 'Options Strategy' },
  { id: 'decision_agent', label: 'Decision Agent' },
  { id: 'risk_guardian', label: 'Risk Guardian' },
];

export default function AutonomousControlCenter() {
  const demo = useDemoMode();
  const { status: liveStatus, isLoading, error, mutate } = useAutonomousStatus();
  const { health } = useHealth();
  const { alpaca } = useAlpacaStatus();
  const { bodyguard: liveBodyguard, error: bodyguardError } = useBodyguard();
  const status = demo.enabled ? demo.bundle.status : liveStatus;
  const bodyguard = demo.enabled ? demo.bundle.bodyguard : liveBodyguard;
  const engine = asDict(status);
  const symbol = currentSymbol(engine);
  const { market, error: marketError } = useMarketData(symbol || '');
  const [pending, setPending] = useState<'start' | 'stop' | 'cycle' | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const debate = asDict(engine.last_debate);
  const outputs = asDict(debate.agent_outputs);
  const decision = decisionBody(engine);
  const rg = asDict(debate.risk_guardian_result);
  const guard = Object.keys(asDict(engine.last_bodyguard)).length ? asDict(engine.last_bodyguard) : asDict(bodyguard);
  const intel = asDict(engine.last_market_intelligence);
  const healthInfo = asDict(health);
  const alpacaInfo = asDict(alpaca);
  const running = Boolean(engine.running);

  const marketState = toMarketState(market || intel, { error: marketError, symbol: symbol || undefined });
  const liveTradingOff = alpacaInfo.live_trading !== true && healthInfo.live_trading !== true;
  const liveMarketOn = Boolean(healthInfo.live_market_data || marketState.liveMarketData);
  const rgReason = pickFirstReason(rg.reason, ...(asList(rg.rejection_reasons) as unknown[]), engine.last_halt_reason, decision.execution_reason);
  const cycleStamp = text(engine.last_cycle || engine.last_cycle_time, '');
  const strategyValue = decision.strategy_recommendation || decision.strategy;
  const latestDecision = formatDecision(decision.decision || engine.last_cycle_status || 'NO_TRADE');

  const pipelinePresent: Record<string, boolean> = {
    market_intelligence: Object.keys(intel).length > 0,
    market_scout: Object.keys(asDict(outputs.market_scout)).length > 0,
    strategy_brain: asList(engine.last_strategy_brain).length > 0,
    bull_agent: Object.keys(asDict(outputs.bull_agent)).length > 0,
    bear_agent: Object.keys(asDict(outputs.bear_agent)).length > 0,
    red_team: Object.keys(asDict(engine.last_red_team)).length > 0,
    strategy_agent: Object.keys(asDict(outputs.strategy_agent)).length > 0,
    decision_agent: Object.keys(asDict(outputs.decision_agent)).length > 0 || Object.keys(decision).length > 0,
    risk_guardian: Object.keys(rg).length > 0,
  };

  async function runSafe(kind: 'start' | 'stop' | 'cycle', fn: () => Promise<{ data?: Dict }>) {
    setPending(kind);
    setActionError(null);
    setActionMessage(null);
    try {
      const result = await fn();
      const payload = asDict(result.data);
      const backendMessage = text(payload.message || payload.status);
      setActionMessage(`DRY RUN / SIMULATED — ${backendMessage}`);
      await mutate();
    } catch (err) {
      setActionError(`DRY RUN / SIMULATED — ${apiErrorMessage(err)}`);
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Trade AI</p>
            <h1 className="text-xl font-bold text-white sm:text-2xl">Autonomous Control Center</h1>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="rounded border border-sky-700 bg-sky-950/60 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-sky-300">
              PAPER TRADING ON
            </span>
            {demo.enabled ? <SimulatedMark /> : null}
            <Link href="/dashboard" className="text-sm text-slate-400 hover:text-white">
              Dashboard
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-5 px-4 py-6 sm:px-6 lg:px-8">
        <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div className="rounded-xl border border-sky-800 bg-sky-950/40 px-4 py-3 text-sm font-semibold text-sky-200">
            PAPER TRADING
            <span className="mt-1 block text-xs font-normal text-sky-300/80">ON</span>
          </div>
          <div className="rounded-xl border border-amber-800 bg-amber-950/40 px-4 py-3 text-sm font-semibold text-amber-200">
            DRY RUN
            <span className="mt-1 block text-xs font-normal text-amber-300/80">ON · backend {String(healthInfo.dry_run ?? engine.dry_run ?? true)}</span>
          </div>
          <div className="rounded-xl border border-emerald-800 bg-emerald-950/40 px-4 py-3 text-sm font-semibold text-emerald-200">
            LIVE MARKET DATA
            <span className="mt-1 block text-xs font-normal text-emerald-300/80">{liveMarketOn ? 'ON' : 'OFF'}</span>
          </div>
          <div className="rounded-xl border border-fuchsia-800 bg-fuchsia-950/40 px-4 py-3 text-sm font-semibold text-fuchsia-200">
            DEMO TRADING
            <span className="mt-1 block text-xs font-normal text-fuchsia-300/80">VIRTUAL MONEY</span>
          </div>
          <div className="rounded-xl border border-rose-800 bg-rose-950/40 px-4 py-3 text-sm font-semibold text-rose-200">
            REAL-MONEY TRADING
            <span className="mt-1 block text-xs font-normal text-rose-300/80">
              {liveTradingOff ? 'OFF' : 'ON'} · Real-money order execution is disabled. Demo trading uses virtual money only.
            </span>
          </div>
        </section>

        <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
          <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Safe controls</h2>
          <p className="mb-4 text-xs text-slate-500">Monitoring and analysis only. No live trading controls. No credential controls.</p>
          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              disabled={demo.enabled || pending !== null || running}
              onClick={() => runSafe('start', () => autonomous.start())}
              className="rounded-lg border border-emerald-700 bg-emerald-950/50 px-4 py-3 text-sm font-semibold text-emerald-200 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {pending === 'start' ? 'Starting…' : 'Start monitoring'}
            </button>
            <button
              type="button"
              disabled={demo.enabled || pending !== null || !running}
              onClick={() => runSafe('stop', () => autonomous.stop())}
              className="rounded-lg border border-slate-600 bg-slate-800 px-4 py-3 text-sm font-semibold text-slate-200 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {pending === 'stop' ? 'Stopping…' : 'Stop monitoring'}
            </button>
            <button
              type="button"
              disabled={demo.enabled || pending !== null || !running}
              onClick={() => runSafe('cycle', () => autonomous.runCycle())}
              className="rounded-lg border border-sky-700 bg-sky-950/50 px-4 py-3 text-sm font-semibold text-sky-200 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {pending === 'cycle' ? 'Running analysis…' : 'Run analysis cycle'}
            </button>
          </div>
          {demo.enabled ? (
            <p className="mt-2 text-xs text-fuchsia-200">DEMO MODE overlay — engine controls disabled so simulated data is not mixed with a live cycle.</p>
          ) : null}
          <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-amber-300">DRY RUN / SIMULATED</p>
          {actionMessage ? <p className="mt-2 text-sm text-emerald-300">{actionMessage}</p> : null}
          {actionError ? <p className="mt-2 text-sm text-rose-300">{actionError}</p> : null}
        </section>

        {!demo.enabled && isLoading && !status ? (
          <p className="text-sm text-slate-400">Loading autonomous status…</p>
        ) : !demo.enabled && error ? (
          <p className="rounded-xl border border-rose-800 bg-rose-950/40 px-4 py-6 text-sm text-rose-200">
            Unable to load backend status: {error instanceof Error ? error.message : String(error)}
          </p>
        ) : (
          <>
            <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
                <Field label="Autonomous status" value={running ? 'running' : 'stopped'} />
              </div>
              <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
                <Field
                  label="Current cycle"
                  value={
                    isMissing(engine.cycle_count)
                      ? 'No cycle count yet'
                      : `${engine.cycle_count} · ${formatCycleStatus(engine.last_cycle_status)}`
                  }
                />
              </div>
              <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
                <Field label="Current symbol" value={symbol || 'No symbol this cycle'} />
              </div>
              <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
                <Field label="Market status" value={marketStatusLabel(marketState)} />
              </div>
              <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
                <Field label="Market session" value={sessionLabel(marketState.session || intel.market_session)} />
              </div>
              <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
                <Field label="Selected strategy" value={isMissing(strategyValue) ? 'Not selected — no executable strategy approved' : String(strategyValue)} />
              </div>
              <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
                <Field label="Risk mode" value={String(engine.current_mode || 'normal').toUpperCase()} />
              </div>
              <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
                <Field label="Latest decision" value={latestDecision} />
                <p className="mt-2 text-xs text-slate-400">
                  Decision reason: {explainReason(rgReason || decision.reason || engine.last_halt_reason || engine.last_cycle_status)}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  Confidence {collectConfidence(decision.confidence) === CONFIDENCE_NOT_PROVIDED ? 'Not provided by this agent' : collectConfidence(decision.confidence)}
                </p>
              </div>
              <div className="rounded-xl border border-amber-700/80 bg-amber-950/20 p-4">
                <Field label="Risk Guardian" value={formatDecision(rg.display_decision || rg.decision || 'BLOCK')} />
                <p className="mt-2 text-xs text-slate-400">Risk reason: {reasonCodeLabel(rgReason) || 'NO REASON CODE'}</p>
                <p className="mt-1 text-xs text-slate-500">{explainReason(rgReason, 'Risk Guardian blocked this trade.')}</p>
              </div>
              <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
                <Field
                  label="RiskBodyguard status"
                  value={!demo.enabled && bodyguardError && Object.keys(guard).length === 0 ? 'Bodyguard status not loaded' : text(guard.action, 'Monitor')}
                />
                <p className="mt-2 text-xs text-slate-400">
                  freeze_new_trades:{' '}
                  {typeof guard.freeze_new_trades === 'boolean' ? String(guard.freeze_new_trades) : 'NOT REPORTED'}
                </p>
              </div>
              <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-4 sm:col-span-2 lg:col-span-3">
                <Field label="Last cycle timestamp" value={cycleStamp || 'No cycle has completed yet'} />
              </div>
            </section>

            <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
              <h2 className="mb-4 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Agent pipeline</h2>
              <ol className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {PIPELINE.map((stage, index) => (
                  <li
                    key={stage.id}
                    className={`rounded-lg border px-3 py-2 text-sm ${
                      pipelinePresent[stage.id]
                        ? 'border-emerald-800 bg-emerald-950/30 text-emerald-200'
                        : 'border-slate-800 bg-slate-950/40 text-slate-500'
                    }`}
                  >
                    <span className="mr-2 text-xs text-slate-500">{index + 1}</span>
                    {stage.label}
                    <span className="mt-1 block text-[11px] uppercase tracking-wide">
                      {pipelinePresent[stage.id] ? 'present' : 'NOT RUN THIS CYCLE'}
                    </span>
                  </li>
                ))}
              </ol>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
