'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { analytics, autonomous, debate } from '@/lib/api';
import { usePortfolio } from '@/hooks/useApi';
import { isMissing, isUnavailableDisplay, money, moneyPositive, text } from '@/lib/format';
import { EmptyState } from '@/components/EmptyState';
import MarketClosedNotice from '@/components/MarketClosedNotice';
import StockSelector from '@/components/StockSelector';
import CallAgentButton from '@/components/CallAgentButton';
import { QUICK_SWITCH } from '@/lib/symbols';

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

function show(value: unknown, fallback = 'NOT AVAILABLE'): string {
  if (isMissing(value)) return fallback;
  if (typeof value === 'number') return String(value);
  return String(value);
}

const PROMPTS = [
  'Analyze AAPL',
  'Explain the current trend',
  'What are the main risks?',
  'Explain the options chain',
  'What happens if volatility rises?',
];

const SECTION_LABELS: { key: string; title: string }[] = [
  { key: 'market_snapshot', title: 'Market Snapshot' },
  { key: 'bull_case', title: 'Bull Scenario' },
  { key: 'bear_case', title: 'Bear Scenario' },
  { key: 'key_risks', title: 'Key Risks' },
  { key: 'options_observations', title: 'Options Insights' },
  { key: 'what_to_watch', title: 'What To Watch' },
  { key: 'educational_explanation', title: 'Educational Explanation' },
];

export default function StockAnalyticsPage() {
  const { portfolio } = usePortfolio();
  const [symbol, setSymbol] = useState('AAPL');
  const [loaded, setLoaded] = useState<Dict | null>(null);
  const [question, setQuestion] = useState('Ask anything about this stock...');
  const [sections, setSections] = useState<Dict | null>(null);
  const [debateResult, setDebateResult] = useState<Dict | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');

  const tech = asDict(loaded?.technicals);
  const options = Array.isArray(loaded?.options) ? (loaded?.options as Dict[]) : [];
  const intel = asDict(loaded?.intelligence);
  const missing = Array.isArray(loaded?.unavailable_without_source)
    ? (loaded?.unavailable_without_source as string[])
    : [];

  async function loadSymbol(next = symbol) {
    setBusy('load');
    setError('');
    try {
      const response = await analytics.get(next.trim().toUpperCase());
      setLoaded(response.data as Dict);
      setSymbol(next.trim().toUpperCase());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analytics unavailable');
      setLoaded(null);
    } finally {
      setBusy('');
    }
  }

  useEffect(() => {
    void loadSymbol('AAPL');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function analyze(event?: FormEvent) {
    event?.preventDefault();
    setBusy('analyze');
    setError('');
    try {
      if (!loaded) await loadSymbol(symbol);
      const q = question.trim() === 'Ask anything about this stock...' ? `Analyze ${symbol}` : question;
      const response = await analytics.analyze(symbol, q);
      setSections(asDict(response.data?.sections));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis unavailable');
    } finally {
      setBusy('');
    }
  }

  async function runDebate() {
    setBusy('debate');
    setError('');
    try {
      const p = asDict(portfolio);
      const rawDd = Number(p.drawdown_pct || 0);
      const response = await debate.run({
        symbol,
        option_type: 'call',
        portfolio_value: Number(p.account_value || 100000),
        current_equity: Number(p.account_value || 100000),
        current_positions: 0,
        current_drawdown: rawDd > 1 ? rawDd / 100 : rawDd,
      });
      setDebateResult(asDict(response.data));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Debate failed');
    } finally {
      setBusy('');
    }
  }

  async function runCycle() {
    setBusy('cycle');
    setError('');
    try {
      await autonomous.runCycle(symbol);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cycle failed');
    } finally {
      setBusy('');
    }
  }

  const agents = asDict(debateResult?.agent_outputs);
  const rg = asDict(debateResult?.risk_guardian_result);
  const final = asDict(debateResult?.final_decision);
  const rgLabel = useMemo(() => {
    const blob = `${rg.decision || final.decision || ''}`.toUpperCase();
    if (blob.includes('REJECT')) return 'TRADE REJECTED';
    if (blob.includes('APPROVE') || blob.includes('ALLOW')) return 'TRADE APPROVED';
    if (blob.includes('NO')) return 'NO TRADE';
    return debateResult ? 'NO TRADE' : '';
  }, [debateResult, final.decision, rg.decision]);

  return (
    <main className="space-y-5 px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Trade AI</p>
          <h1 className="text-2xl font-bold text-white">Stock Analytics</h1>
          <p className="mt-1 text-sm text-slate-400">Facts from Alpaca paper data. Indicators use available bars. Nothing is invented.</p>
        </div>
        <CallAgentButton symbol={symbol} />
      </div>

      <div className="space-y-3">
        <StockSelector
          value={symbol}
          onChange={(next) => {
            setSymbol(next);
            void loadSymbol(next);
          }}
        />
        <div className="flex flex-wrap gap-1">
          {QUICK_SWITCH.map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => {
                setSymbol(item);
                void loadSymbol(item);
              }}
              className={`rounded-md border px-2 py-1 text-[11px] font-semibold ${
                item === symbol ? 'border-sky-500 text-white' : 'border-slate-700 text-slate-400'
              }`}
            >
              {item}
            </button>
          ))}
        </div>
      </div>
      {error ? <p className="text-sm text-rose-300">{error}</p> : null}

      {!loaded ? (
        <EmptyState title="Enter a ticker to begin." body="Load AAPL or another symbol to see quotes, technicals, and options when Alpaca returns them." />
      ) : (
        <>
          <MarketClosedNotice market={loaded} symbol={String(loaded.symbol || '')} />

          <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
            <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Price</h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Field label="Price" value={typeof loaded.price === 'number' && loaded.price > 0 ? money(loaded.price) : 'NO QUOTE AVAILABLE'} />
              <Field label="Bid" value={typeof loaded.bid === 'number' ? moneyPositive(loaded.bid) : 'NO BID'} />
              <Field label="Ask" value={typeof loaded.ask === 'number' ? moneyPositive(loaded.ask) : 'NO ASK'} />
              <Field label="Spread" value={typeof loaded.spread === 'number' ? moneyPositive(loaded.spread) : 'NO SPREAD'} />
              <Field label="Volume" value={show(loaded.volume, 'VOLUME NOT AVAILABLE')} />
              <Field label="Session" value={show(loaded.session, 'SESSION UNKNOWN')} />
              <Field label="Freshness" value={show(loaded.freshness, 'FRESHNESS UNKNOWN')} />
            </div>
          </section>

          <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
            <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Technical Analysis</h2>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Field label="SMA" value={show(tech.sma_20)} />
              <Field label="EMA" value={show(tech.ema_12)} />
              <Field label="RSI" value={show(tech.rsi_14)} />
              <Field label="MACD" value={show(tech.macd)} />
              <Field label="VWAP" value={show(tech.vwap_last_bar)} />
            </div>
          </section>

          <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
            <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Options analytics</h2>
            {options.length === 0 ? (
              <p className="text-sm text-slate-400">No option contracts returned for this symbol.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-left text-xs">
                  <thead className="text-slate-500">
                    <tr>
                      {['Expiration', 'Strike', 'C/P', 'Bid', 'Ask', 'Mid', 'OI', 'IV', 'Delta'].map((h) => (
                        <th key={h} className="px-2 py-1 font-medium">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {options.slice(0, 8).map((row) => (
                      <tr key={String(row.occ_symbol)} className="border-t border-slate-800 text-slate-200">
                        <td className="px-2 py-1">{show(row.expiration)}</td>
                        <td className="px-2 py-1">{show(row.strike)}</td>
                        <td className="px-2 py-1">{show(row.call_put)}</td>
                        <td className="px-2 py-1">{show(row.bid)}</td>
                        <td className="px-2 py-1">{show(row.ask)}</td>
                        <td className="px-2 py-1">{show(row.mid)}</td>
                        <td className="px-2 py-1">{show(row.open_interest)}</td>
                        <td className="px-2 py-1">{show(row.iv)}</td>
                        <td className="px-2 py-1">{show(row.delta)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
            <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Market intelligence</h2>
            <Field label="Volume" value={show(intel.volume)} />
            <Field label="IV" value={show(intel.iv)} />
            <p className="mt-3 text-xs text-slate-500">Not provided by current feeds: {missing.join(', ')}</p>
          </section>
        </>
      )}

      <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">AI Stock Analyst</h2>
        <p className="mb-3 text-xs text-slate-500">Advisory only. LLM never claims certainty and never invents missing fields.</p>
        <div className="mb-3 flex flex-wrap gap-2">
          {PROMPTS.map((item) => (
            <button key={item} type="button" className="rounded-full border border-slate-700 px-3 py-1 text-xs" onClick={() => setQuestion(item.replace('AAPL', symbol))}>
              {item.replace('AAPL', symbol)}
            </button>
          ))}
        </div>
        <form onSubmit={(e) => void analyze(e)} className="space-y-2">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            rows={2}
            placeholder="Ask anything about this stock..."
            className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
          />
          <button type="submit" disabled={busy === 'analyze'} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold uppercase tracking-wide text-white">
            Analyze With AI
          </button>
        </form>
        {sections ? (
          <div className="mt-4 space-y-3 text-sm">
            {SECTION_LABELS.map((item) => (
              <div key={item.key}>
                <p className="text-[11px] font-bold uppercase tracking-wide text-sky-300">{item.title}</p>
                <p className="text-slate-200">{text(sections[item.key])}</p>
              </div>
            ))}
            <p className="text-xs text-slate-500">Advisory only. Not a buy or sell instruction.</p>
          </div>
        ) : null}
      </section>

      <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">AI debate</h2>
        <div className="flex flex-wrap gap-2">
          <button type="button" disabled={!!busy} onClick={() => void runDebate()} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white">
            Run AI Debate
          </button>
          <button type="button" disabled={!!busy} onClick={() => void runCycle()} className="rounded-lg border border-slate-600 px-4 py-2 text-sm">
            Run analysis cycle
          </button>
          <Link href="/ai-debate" className="rounded-lg border border-slate-600 px-4 py-2 text-sm">
            Open debate page
          </Link>
        </div>
        {debateResult ? (
          <div className="mt-4 space-y-2 text-sm">
            <p>Bull: {text(asDict(agents.bull_agent).reasoning || asDict(agents.bull_agent).recommendation)}</p>
            <p>Bear: {text(asDict(agents.bear_agent).reasoning || asDict(agents.bear_agent).recommendation)}</p>
            <p>
              Risk Guardian: {text(rg.decision)} — {(Array.isArray(rg.rejection_reasons) ? rg.rejection_reasons : []).join('; ') || text(rg.reason)}
            </p>
            <p className="text-lg font-bold text-white">{rgLabel}</p>
            <p className="text-xs text-sky-300">AI recommends. Risk Guardian decides.</p>
          </div>
        ) : null}
      </section>
    </main>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] uppercase text-slate-500">{label}</p>
      <p className={`text-sm ${isUnavailableDisplay(value) ? 'text-amber-300' : 'text-white'}`}>{value}</p>
    </div>
  );
}
