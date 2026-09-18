'use client';

import { FormEvent, Suspense, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { copilot, intelligence } from '@/lib/api';
import { useAutonomousStatus, useBodyguard, useDemoOrders, useDemoPortfolio, useDemoPositions, useMarketData, useVoiceStatus } from '@/hooks/useApi';
import { isMissing, money, moneyDisplay, pct, shown, text } from '@/lib/format';
import { canSpeak, speak, stopSpeech } from '@/lib/speech';
import { useStreamQuote } from '@/components/MarketStreamProvider';

type Dict = Record<string, unknown>;

const STAGES = [
  'CALLING',
  'CONNECTED',
  'ANALYZING PORTFOLIO',
  'ANALYZING RISK',
  'RISK ALERT',
  'CALL COMPLETED',
] as const;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

export default function CallAgentDemo() {
  return (
    <Suspense fallback={<p className="px-4 py-6 text-sm text-slate-400">Loading Call Agent…</p>}>
      <CallAgentBody />
    </Suspense>
  );
}

function CallAgentBody() {
  const params = useSearchParams();
  const selectedSymbol = (params.get('symbol') || 'AAPL').toUpperCase();
  const { voice } = useVoiceStatus();
  const { portfolio } = useDemoPortfolio();
  const { status, mutate } = useAutonomousStatus();
  const { positions } = useDemoPositions();
  const { bodyguard } = useBodyguard();
  const { market } = useMarketData(selectedSymbol);
  const { quote: streamQuote, merge } = useStreamQuote(selectedSymbol);
  const { orders: paperOrders } = useDemoOrders();
  const liveSnap = merge({ ...(market || {}), ...(streamQuote || {}), symbol: selectedSymbol });
  const lastPaper = (Array.isArray(paperOrders) ? paperOrders : []).find((row: Dict) => String(row.symbol) === selectedSymbol) as Dict | undefined;
  const [stageIndex, setStageIndex] = useState(-1);
  const [running, setRunning] = useState(false);
  const [payload, setPayload] = useState<Dict | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState(`What is happening with ${selectedSymbol}?`);
  const [answer, setAnswer] = useState('');
  const [askBusy, setAskBusy] = useState(false);

  const engine = asDict(status);
  const snap = Object.keys(asDict(payload?.portfolio)).length ? asDict(payload?.portfolio) : asDict(portfolio);
  const dd = asDict(asDict(engine.drawdown_guardian).state);
  const mode = String(payload?.risk_mode || engine.current_mode || dd.current_mode || '').toLowerCase();
  const isCritical = mode === 'critical' || payload?.critical === true;
  const debate = asDict(engine.last_debate);
  const rg = Object.keys(asDict(payload?.risk_guardian)).length
    ? asDict(payload?.risk_guardian)
    : asDict(debate.risk_guardian_result);
  const guard = Object.keys(asDict(payload?.risk_bodyguard)).length
    ? asDict(payload?.risk_bodyguard)
    : asDict(bodyguard);
  const positionRows = asList(asList(payload?.positions).length ? payload?.positions : positions).map(asDict);
  const drawdown = dd.drawdown_percentage ?? engine.current_drawdown ?? payload?.drawdown;
  const reason = text(
    payload?.reason ||
      engine.last_cycle_message ||
      engine.last_halt_reason ||
      (isCritical ? 'CRITICAL mode: new trades are blocked' : null)
  );

  const stage = stageIndex >= 0 ? STAGES[stageIndex] : null;

  const script = useMemo(() => {
    const backendScript = typeof payload?.script === 'string' ? payload.script : '';
    const lines: Record<(typeof STAGES)[number], string> = {
      CALLING: 'Calling. This is a simulated AI voice. No real phone call.',
      CONNECTED: `Hello Demo User. You're currently viewing ${selectedSymbol}. Live price ${moneyDisplay(liveSnap.price)}. Bid ${moneyDisplay(liveSnap.bid)}. Ask ${moneyDisplay(liveSnap.ask)}. This is Trade AI. Your current trading environment is paper trading mode.`,
      'ANALYZING PORTFOLIO': `Analyzing paper portfolio value ${money(snap.account_value)}.`,
      'ANALYZING RISK': `The current market status is educational paper data. Your current risk mode is ${mode || 'MODE NOT REPORTED'}. Drawdown ${isMissing(drawdown) ? 'DRAWDOWN NOT AVAILABLE' : pct(drawdown, true)}.`,
      'RISK ALERT': `Risk Guardian status is ${text(rg.decision)}. ${isCritical ? `Critical risk alert. ${reason}` : `Risk alert. ${reason}`}`,
      'CALL COMPLETED': backendScript || 'This is a simulated educational alert. Simulated call completed. No real phone call was placed.',
    };
    return lines;
  }, [drawdown, isCritical, liveSnap.ask, liveSnap.bid, liveSnap.price, mode, payload?.script, reason, rg.decision, selectedSymbol, snap.account_value]);

  useEffect(() => {
    if (!running || stageIndex < 0 || stageIndex >= STAGES.length) return undefined;
    if (canSpeak()) speak(script[STAGES[stageIndex]]);
    const timer = window.setTimeout(() => {
      if (stageIndex >= STAGES.length - 1) {
        setRunning(false);
        return;
      }
      setStageIndex((index) => index + 1);
    }, 1600);
    return () => window.clearTimeout(timer);
  }, [running, script, stageIndex]);

  useEffect(() => {
    setQuestion(`What is happening with ${selectedSymbol}?`);
  }, [selectedSymbol]);

  useEffect(() => {
    return () => {
      if (typeof window !== 'undefined') stopSpeech();
    };
  }, []);

  async function askAboutStock(event?: FormEvent) {
    event?.preventDefault();
    setAskBusy(true);
    setAnswer('');
    try {
      const response = await copilot.ask(
        `${question} Context symbol: ${selectedSymbol}. Live Alpaca IEX price ${moneyDisplay(liveSnap.price)} bid ${moneyDisplay(liveSnap.bid)} ask ${moneyDisplay(liveSnap.ask)} change ${shown(liveSnap.day_change_pct)}. Virtual cash ${moneyDisplay(asDict(portfolio).cash)}. Demo position ${positionRows.find((row) => String(row.symbol) === selectedSymbol) ? 'open' : 'none'}. Latest analysis ${shown(asDict(engine.last_decision).reason || engine.last_cycle_message)}. Recent demo trade: ${lastPaper ? `${shown(lastPaper.side)} ${shown(lastPaper.quantity)} ${shown(lastPaper.symbol)} @ ${moneyDisplay(lastPaper.filled_avg_price ?? lastPaper.price)} ${shown(lastPaper.status)} ${shown(lastPaper.trade_type)}` : 'none'}. Demo virtual trading only. No real-money orders.`
      );
      setAnswer(String(response.data?.answer || 'NO COPILOT ANSWER'));
    } catch (err) {
      setAnswer(err instanceof Error ? err.message : 'COPILOT ERROR');
    } finally {
      setAskBusy(false);
    }
  }

  async function startCall() {
    setError(null);
    setRunning(true);
    setStageIndex(0);
    try {
      const result = await intelligence.simulateCall();
      setPayload(asDict(result.data));
      await mutate();
    } catch (err) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      setError(e.response?.data?.detail || e.message || 'Simulated call failed');
      setRunning(false);
      setStageIndex(-1);
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Trade AI</p>
            <h1 className="text-xl font-bold text-white sm:text-2xl">Call Agent</h1>
            <p className="text-sm text-slate-400">You&apos;re currently viewing {selectedSymbol}. What would you like to know?</p>
          </div>
          <Link href="/dashboard" className="text-sm text-slate-400 hover:text-white">
            Dashboard
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-5 px-4 py-6 sm:px-6">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <div className="rounded-lg border border-amber-700 bg-amber-950/40 px-3 py-2 text-center text-xs font-bold uppercase tracking-wide text-amber-300">
            SIMULATED AI VOICE
          </div>
          <div className="rounded-lg border border-rose-700 bg-rose-950/40 px-3 py-2 text-center text-xs font-bold uppercase tracking-wide text-rose-300">
            NO REAL PHONE CALL
          </div>
        </div>

        {isCritical ? (
          <section className="rounded-xl border-2 border-rose-500 bg-rose-950/60 p-5">
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-rose-300">CRITICAL mock alert</p>
            <p className="mt-2 text-lg font-semibold text-white">{reason}</p>
            <p className="mt-2 text-sm text-rose-200">This is a simulated Call Agent alert. No real phone call.</p>
          </section>
        ) : null}

        <section className="rounded-xl border border-sky-700 bg-sky-950/30 p-5">
          <p className="text-sm text-sky-100">You&apos;re currently viewing {selectedSymbol}. What would you like to know?</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {[
              `What is happening with ${selectedSymbol}?`,
              `Explain the current price movement of ${selectedSymbol}.`,
              `What are the risks for ${selectedSymbol}?`,
              'Explain the Bull and Bear views.',
              'Explain this trade.',
              'Teach me what this indicator means.',
            ].map((item) => (
              <button key={item} type="button" className="rounded-full border border-slate-600 px-3 py-1 text-xs" onClick={() => setQuestion(item)}>
                {item}
              </button>
            ))}
          </div>
          <form onSubmit={(e) => void askAboutStock(e)} className="mt-3 space-y-2">
            <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={2} className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm" />
            <button type="submit" disabled={askBusy} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white">
              {askBusy ? 'Asking…' : 'Ask Call Agent'}
            </button>
          </form>
          {answer ? <p className="mt-3 text-sm text-slate-200">{answer}</p> : null}
        </section>

        <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
          <button
            type="button"
            disabled={running}
            onClick={startCall}
            className="rounded-lg border border-sky-700 bg-sky-950/50 px-4 py-3 text-sm font-semibold text-sky-200 disabled:opacity-40"
          >
            {running ? 'Simulated call in progress…' : '🔊 Start AI Call'}
          </button>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => {
                setRunning(false);
                setStageIndex(-1);
                stopSpeech();
              }}
              className="rounded border border-slate-600 px-3 py-1 text-xs"
            >
              ⏹ Stop
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Uses AuditLogger VOICE_ALERT and browser mock speech. Telephony disabled
            {voice ? ` · ${text(asDict(voice).telephony)}` : ''}.
          </p>
          {error ? <p className="mt-2 text-sm text-rose-300">{error}</p> : null}
        </section>

        <ol className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {STAGES.map((item, index) => {
            const current = index === stageIndex;
            const done = index < stageIndex;
            return (
              <li
                key={item}
                className={`rounded-lg border px-3 py-3 text-sm ${
                  current
                    ? 'border-sky-500 bg-sky-950/50 text-sky-100'
                    : done
                      ? 'border-emerald-800 bg-emerald-950/20 text-emerald-200'
                      : 'border-slate-800 bg-slate-950/40 text-slate-500'
                }`}
              >
                <span className="text-[11px] uppercase tracking-wide text-slate-500">{index + 1}</span>
                <p className="font-semibold">{item}</p>
              </li>
            );
          })}
        </ol>

        {stage ? (
          <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
            <p className="text-[11px] uppercase tracking-wide text-slate-500">Current stage</p>
            <p className="mt-1 text-xl font-bold text-white">{stage}</p>
            <p className="mt-2 text-sm text-slate-300">{script[stage]}</p>
          </section>
        ) : null}

        <section className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
            <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Portfolio context</h2>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">Value</dt>
                <dd className="text-white">{money(snap.account_value)}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">Cash</dt>
                <dd className="text-white">{money(snap.cash)}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">Drawdown</dt>
                <dd className="text-white">{isMissing(drawdown) ? 'DRAWDOWN NOT AVAILABLE' : pct(drawdown, true)}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">Risk mode</dt>
                <dd className="uppercase text-white">{mode || 'MODE NOT REPORTED'}</dd>
              </div>
            </dl>
          </div>
          <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
            <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Reason for alert</h2>
            <p className="text-sm text-slate-200">{reason}</p>
            <p className="mt-3 text-sm">
              <span className="text-slate-500">RiskGuardian: </span>
              {text(rg.decision)}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              {asList(rg.rejection_reasons).length
                ? asList(rg.rejection_reasons).map(String).join(' · ')
                : text(rg.reason)}
            </p>
            <p className="mt-3 text-sm">
              <span className="text-slate-500">RiskBodyguard: </span>
              {text(guard.action)}
            </p>
            <ul className="mt-1 list-disc pl-5 text-xs text-slate-400">
              {asList(guard.reasons).length ? (
                asList(guard.reasons).map((item) => <li key={String(item)}>{String(item)}</li>)
              ) : (
                <li className="text-amber-300">NO BODYGUARD REASONS REPORTED</li>
              )}
            </ul>
          </div>
        </section>

        <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
          <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Important positions</h2>
          {positionRows.length === 0 ? (
            <p className="text-sm text-slate-400">No open positions</p>
          ) : (
            <ul className="space-y-2 text-sm text-slate-200">
              {positionRows.slice(0, 8).map((row, index) => (
                <li key={String(row.position_id || index)} className="flex flex-wrap justify-between gap-2 border-b border-slate-800 pb-2">
                  <span className="font-medium text-white">{text(row.symbol)}</span>
                  <span>
                    {text(row.option_type)} {money(row.strike)} qty {text(row.quantity)}
                  </span>
                  <span>P&L {money(row.unrealized_pnl)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}
