'use client';

import type { ReactNode } from 'react';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import QRCodeComponent from '@/components/QRCode';
import {
  useAlpacaStatus,
  useAnalyticsQuote,
  useAutonomousStatus,
  useBodyguard,
  useGreeks,
  useHealth,
  useIntelligence,
  useMarketData,
  useOptions,
  useDemoOrders,
  useDemoPortfolio,
  useDemoPositions,
  usePortfolioHealth,
  useWatchlist,
} from '@/hooks/useApi';
import { analytics, copilot, autonomous, debate } from '@/lib/api';
import { DATA_UNAVAILABLE, isMissing, isUnavailableDisplay, moneyDisplay, NOT_AVAILABLE, pct, pnlClass, shown, text } from '@/lib/format';
import { greeksDisplay, greeksState, toMarketState } from '@/lib/marketState';
import { explainReason, formatCycleStatus, formatDecision } from '@/lib/reasonCodes';
import { collectConfidence, CONFIDENCE_NOT_PROVIDED } from '@/lib/agentDisplay';
import { useDemoMode } from '@/hooks/useDemoMode';
import { SimulatedMark } from '@/components/DemoBanner';
import { useLearnProgress } from '@/hooks/useLearnProgress';
import { LESSONS } from '@/lib/learn/content';
import { DEFAULT_SIM, estimateSimulatedPnl, WHAT_IF_SHOCKS, type WhatIfShock } from '@/lib/learn/simulate';
import TradeSimulatePanel from '@/components/TradeSimulatePanel';
import { EmptyState } from '@/components/EmptyState';
import MarketWatchCard from '@/components/MarketWatchCard';
import DashboardAnalytics from '@/components/DashboardAnalytics';
import OptionsChainPanel from '@/components/OptionsChainPanel';
import CallAgentButton from '@/components/CallAgentButton';
import SafetyStatusStrip from '@/components/SafetyStatusStrip';
import WatchlistTable from '@/components/WatchlistTable';
import RecentTradesList from '@/components/RecentTradesList';
import { useMarketStream } from '@/components/MarketStreamProvider';

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

function asList(value: unknown): string[] {
  if (!Array.isArray(value) || value.length === 0) return [];
  return value.map((item) => String(item));
}

function decisionBody(status: unknown): Dict {
  const engine = asDict(status);
  const last = asDict(engine.last_decision);
  const nested = asDict(last.data);
  const debate = asDict(engine.last_debate);
  const fromDebate = asDict(debate.final_decision);
  return Object.keys(nested).length ? nested : Object.keys(last).length ? last : fromDebate;
}

function Panel({
  title,
  children,
  className = '',
  simulated = false,
  id,
}: {
  title: string;
  children: ReactNode;
  className?: string;
  simulated?: boolean;
  id?: string;
}) {
  return (
    <section id={id} className={`rounded-xl border border-slate-700/80 bg-slate-900/70 p-4 sm:p-5 ${className}`}>
      <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
        {title}
        {simulated ? <SimulatedMark /> : null}
      </h2>
      {children}
    </section>
  );
}

function PipeNode({ name, status, detail }: { name: string; status: string; detail: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold text-white">{name}</p>
        <p className="text-[10px] font-bold uppercase text-sky-300">{status}</p>
      </div>
      <p className="mt-1 text-xs text-slate-400">{detail}</p>
    </div>
  );
}

function Metric({
  label,
  value,
  valueClass = 'text-white',
  simulated = false,
  source,
}: {
  label: string;
  value: string;
  valueClass?: string;
  simulated?: boolean;
  source?: string;
}) {
  const unavailable = isUnavailableDisplay(value);
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-3 sm:p-4">
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`mt-1 font-semibold tabular-nums ${unavailable ? 'text-amber-300 text-sm' : `text-lg sm:text-xl ${valueClass}`}`}>
        {value}
      </p>
      {simulated && !unavailable ? (
        <p className="mt-1 text-[10px] font-bold uppercase tracking-wide text-amber-300">SIMULATED</p>
      ) : null}
      {!simulated && !unavailable && source ? (
        <p className="mt-1 text-[10px] font-bold uppercase tracking-wide text-sky-400">{source}</p>
      ) : null}
    </div>
  );
}

function Field({ label, value, simulated = false }: { label: string; value: string; simulated?: boolean }) {
  const unavailable = isUnavailableDisplay(value);
  return (
    <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
      <span className="text-xs uppercase tracking-wide text-slate-500">{label}</span>
      <span className={`text-sm ${unavailable ? 'font-semibold text-amber-300' : 'text-slate-100'}`}>{value}</span>
    </div>
  );
}

function agentReady(value: unknown): { status: string; detail: string } {
  if (value === null || value === undefined || value === '') {
    return { status: 'WAITING FOR REQUIRED MARKET DATA', detail: 'No analysis yet. Run analysis.' };
  }
  if (Array.isArray(value)) {
    if (!value.length) return { status: 'WAITING FOR REQUIRED MARKET DATA', detail: 'No analysis yet. Run analysis.' };
    const first = asDict(value[0]);
    return { status: 'READY', detail: shown(first.recommendation || first.strategy || first.summary || first.thesis || value.length) };
  }
  if (typeof value === 'object') {
    const d = asDict(value);
    if (!Object.keys(d).length) return { status: 'WAITING FOR REQUIRED MARKET DATA', detail: 'No analysis yet. Run analysis.' };
    const nested = asDict(d.data);
    const missing = d.missing || nested.missing;
    if (d.valid === false || nested.valid === false) {
      return {
        status: 'WAITING FOR REQUIRED MARKET DATA',
        detail: Array.isArray(missing) ? `Missing: ${missing.join(', ')}` : shown(d.reasoning || nested.status),
      };
    }
    const detail =
      d.analysis ||
      d.reasoning ||
      nested.reasoning ||
      d.thesis ||
      d.display_decision ||
      d.decision ||
      d.recommendation ||
      d.summary ||
      nested.current_price ||
      d.price ||
      d.market_session;
    return {
      status: 'READY',
      detail: shown(detail),
    };
  }
  return { status: 'READY', detail: String(value) };
}

function mapBodyguard(body: Dict): string {
  if (!Object.keys(body).length) return 'WAITING FOR RISK BODYGUARD';
  if (body.freeze_new_trades === true || String(body.action).toUpperCase().includes('FREEZE')) return 'BLOCKED';
  const action = String(body.action || '').toUpperCase();
  if (['REDUCE', 'HEDGE', 'EXIT', 'WARNING'].includes(action)) return 'WARNING';
  if (action === 'HOLD' || action === 'MONITOR' || action === 'NORMAL') return 'NORMAL';
  return text(body.action);
}

function mapRgDisplay(rg: Dict): string {
  const raw = String(rg.display_decision || rg.decision || '').toUpperCase();
  if (raw.includes('ALLOW') || raw.includes('APPROV')) return 'ALLOW';
  if (raw.includes('HOLD')) return 'HOLD';
  if (raw.includes('BLOCK') || raw.includes('REJECT')) return 'BLOCK';
  if (!raw) return 'WAITING FOR REQUIRED MARKET DATA';
  return raw;
}

function mapRgFinal(rgDecision: string, latest: string, rejections: string[]): string {
  const blob = `${rgDecision} ${latest}`.toUpperCase();
  if (blob.includes('MARKET_CLOSED') || blob.includes('MARKET CLOSED')) return 'NO TRADE';
  if (blob.includes('REJECT') || blob.includes('BLOCK')) return 'NO TRADE';
  if (blob.includes('APPROVE') || blob.includes('ALLOW')) return 'TRADE APPROVED';
  if (blob.includes('NO TRADE') || blob.includes('NO_TRADE') || blob.includes('HOLD')) return 'NO TRADE';
  if (rejections.length) return 'NO TRADE';
  if (!rgDecision && !latest) return 'WAITING FOR REQUIRED MARKET DATA';
  return latest ? latest.toUpperCase() : 'NO TRADE';
}

const COPILOT_EXAMPLES = [
  'What is my portfolio?',
  'Why was my trade rejected?',
  'Explain my drawdown.',
  'Explain the latest AI debate.',
  'What are my biggest risks?',
  'Analyze this stock.',
];

const SHOCK_LABELS: Record<WhatIfShock['id'], string> = {
  price_rises: 'Price ↑',
  price_falls: 'Price ↓',
  vol_rises: 'Volatility ↑',
  vol_falls: 'Volatility ↓',
  dte_decreases: 'DTE ↓',
  drawdown_increases: 'Drawdown ↑',
};

export default function Dashboard() {
  const demo = useDemoMode();
  const { progress, ready: learnReady } = useLearnProgress();
  const { portfolio, isLoading: portfolioLoading, error: portfolioError } = useDemoPortfolio();
  const { health: portfolioHealth } = usePortfolioHealth();
  const { status: liveStatus, error: statusError, mutate: mutateStatus } = useAutonomousStatus();
  const { health: backendHealth, error: backendError } = useHealth();
  const { alpaca, error: alpacaError } = useAlpacaStatus();
  const { positions: livePositions, isLoading: positionsLoading } = useDemoPositions();
  const { greeks: liveGreeks, error: greeksError } = useGreeks();
  const { bodyguard: liveBodyguard, error: bodyguardError } = useBodyguard();
  const { orders: demoOrders } = useDemoOrders();
  const { items: watchItems, liveMarketData, isLoading: watchLoading } = useWatchlist();
  const { merge, status: streamStatus } = useMarketStream();
  const status = liveStatus;
  const [symbol, setSymbol] = useState('AAPL');
  const { market: liveMarket, error: marketError, mutate: mutateMarket, isLoading: marketLoading } = useMarketData(symbol);
  const { analytics: analyticsPayload, error: analyticsError, isLoading: analyticsLoading, mutate: mutateAnalytics } = useAnalyticsQuote(symbol);
  const { intelligence: liveIntel, mutate: mutateIntel } = useIntelligence(symbol);
  const { options: liveOptions, error: optionsError, mutate: mutateOptions } = useOptions(symbol);
  const positions = livePositions;
  const greeks = asDict(liveGreeks);
  const greekStatus = greeksState(greeks, greeksError);
  const greek = (key: string) => {
    const value = greeks[key] ?? greeks[`portfolio_${key}`];
    return greeksDisplay(greeks, value);
  };
  const market = liveMarket;
  const intelligence = liveIntel;
  const bodyguard = liveBodyguard;
  const [fetchedAt, setFetchedAt] = useState(Date.now());
  const [analyzeBusy, setAnalyzeBusy] = useState(false);
  const [analyzeSections, setAnalyzeSections] = useState<Dict | null>(null);
  const [analyzeError, setAnalyzeError] = useState('');
  const [shockId, setShockId] = useState<WhatIfShock['id']>('price_falls');
  const [copilotQ, setCopilotQ] = useState(COPILOT_EXAMPLES[0]);
  const [copilotA, setCopilotA] = useState('');
  const [copilotBusy, setCopilotBusy] = useState(false);
  const [cycleBusy, setCycleBusy] = useState(false);
  const [cycleMessage, setCycleMessage] = useState('');

  useEffect(() => {
    if (liveMarket) setFetchedAt(Date.now());
  }, [liveMarket]);

  const backendOk = !backendError && backendHealth?.status === 'healthy';
  const alpacaOk = !alpacaError && Boolean(alpaca?.connected && alpaca?.authenticated);

  const p = portfolioError || !portfolio ? null : portfolio;
  const drawdownValue = (() => {
    if (p && !isMissing(p.drawdown_pct)) return `${Number(p.drawdown_pct).toFixed(2)}%`;
    if (status && !isMissing(status.current_drawdown)) return pct(status.current_drawdown, true);
    return '0.00%';
  })();

  const mode = String(status?.current_mode || '').toLowerCase();

  const body = decisionBody(status);
  const lastDebate = asDict(status?.last_debate);
  const agentOutputs = asDict(lastDebate.agent_outputs);
  const decisionAgent = asDict(agentOutputs.decision_agent);
  const latestDecision = formatDecision(body.decision);
  const confidenceRaw = collectConfidence(body.confidence, decisionAgent.confidence, asDict(decisionAgent.data).confidence);
  const confidence = confidenceRaw === CONFIDENCE_NOT_PROVIDED ? 'Not provided by this agent' : confidenceRaw;
  const strategy = isMissing(body.strategy_recommendation || body.strategy)
    ? 'Not selected — no executable strategy approved'
    : String(body.strategy_recommendation || body.strategy);
  const scenario = shown(body.scenario || lastDebate.scenario || formatCycleStatus(status?.last_cycle_status));
  const reasoning = shown(
    decisionAgent.reasoning ||
      body.reasoning ||
      body.analysis ||
      body.llm_explanation ||
      asDict(status?.last_decision).reasoning ||
      status?.last_cycle_message
  );
  const evidence = asList(body.evidence || decisionAgent.evidence || lastDebate.evidence);
  const riskItems = [
    ...asList(body.decision_rules),
    ...asList(body.risks),
    ...(isMissing(body.risk_level) ? [] : [`Risk level: ${String(body.risk_level)}`]),
  ];

  const rg = Object.keys(asDict(status?.last_risk_guardian)).length
    ? asDict(status?.last_risk_guardian)
    : asDict(lastDebate.risk_guardian_result);
  const rejection = asList(status?.last_rejection_reasons).length
    ? asList(status?.last_rejection_reasons)
    : asList(rg.rejection_reasons);
  const checks = asList(rg.limits_checked || rg.checks);
  const red = asDict(status?.last_red_team);
  const redWarnings = [...asList(red.objections), ...asList(red.risk_flags)];
  const rgDecision = mapRgDisplay(rg);
  const finalLabel = mapRgFinal(rgDecision, latestDecision, rejection);

  const quote = asDict(market?.quote);
  const trade = asDict(market?.trade);
  const lastBar = Array.isArray(market?.bars) ? asDict((market.bars as unknown[])[(market.bars as unknown[]).length - 1]) : {};
  const quoteSpread =
    typeof quote.bid === 'number' && typeof quote.ask === 'number' && quote.bid > 0 && quote.ask > 0 ? quote.ask - quote.bid : undefined;
  const marketState = toMarketState(market, { streamLive: streamStatus.state === 'LIVE' || Boolean(liveMarketData), error: marketError, symbol });
  const session = marketState.session;
  const freshness = marketState.freshness;
  const sessionBar = session;
  const dataBadge = freshness;
  const riskBadge =
    mode === 'critical' ? 'CRITICAL' : mode === 'protection' ? 'PROTECTION' : mode === 'normal' ? 'NORMAL' : mode ? mode.toUpperCase() : 'NORMAL';

  const bg = asDict(bodyguard);
  const bodyguardLabel = bodyguardError && !Object.keys(bg).length ? NOT_AVAILABLE : mapBodyguard(bg);
  const dd = asDict(asDict(status?.drawdown_guardian).state);
  const ddMode = shown(dd.current_mode || status?.current_mode).toUpperCase();
  const health = asDict(portfolioHealth);

  const shock = WHAT_IF_SHOCKS.find((item) => item.id === shockId) || WHAT_IF_SHOCKS[0];
  const simPnl = estimateSimulatedPnl(DEFAULT_SIM, shock);

  const pipeline = [
    { name: 'Market Intelligence', ...agentReady(status?.last_market_intelligence || intelligence) },
    { name: 'Market Scout', ...agentReady(agentOutputs.market_scout) },
    { name: 'Strategy Brain', ...agentReady(status?.last_strategy_brain || agentOutputs.strategy_agent) },
    { name: 'Bull', ...agentReady(agentOutputs.bull_agent) },
    { name: 'Bear', ...agentReady(agentOutputs.bear_agent) },
    { name: 'Red Team', ...agentReady(status?.last_red_team) },
    { name: 'Options Strategy', ...agentReady(agentOutputs.options_strategy || agentOutputs.options_analyst || body.strategy_recommendation) },
    { name: 'Decision Agent', ...agentReady(agentOutputs.decision_agent || body) },
    { name: 'Risk Guardian', ...agentReady(Object.keys(rg).length ? rg : null) },
    { name: 'Trade / No Trade', status: finalLabel, detail: explainReason(rejection[0] || status?.last_halt_reason || status?.last_cycle_message || 'NO_TRADE') },
  ];

  const activityRows = useMemo(() => {
    const rows: { id: string; label: string; klass: string; message: string }[] = [];
    if (status?.last_cycle_message || status?.last_halt_reason) {
      const closed = String(status.last_halt_reason || '').includes('MARKET_CLOSED');
      rows.push({
        id: 'cycle',
        label: 'Market Analysis',
        klass: 'DRY_RUN_SIMULATED',
        message: closed ? 'NO TRADE · Market closed' : String(status.last_cycle_message || status.last_halt_reason),
      });
    }
    if (Object.keys(rg).length || rejection.length) {
      rows.push({
        id: 'risk',
        label: 'Risk Guardian',
        klass: 'DRY_RUN_SIMULATED',
        message: `${rgDecision}${rejection[0] ? ` · Reason: ${rejection[0]}` : ''}`.trim(),
      });
    }
    const tradeRows = (Array.isArray(demoOrders) ? demoOrders : []) as Dict[];
    tradeRows.slice(0, 5).forEach((order: Dict, idx: number) => {
      rows.push({
        id: `ord-${idx}`,
        label: 'Demo Trade',
        klass: 'DRY_RUN_SIMULATED',
        message: `${shown(order.side).toUpperCase()} ${shown(order.symbol)} ${shown(order.quantity)} share${Number(order.quantity) === 1 ? '' : 's'} ${moneyDisplay(order.price)}`,
      });
    });
    return rows.slice(0, 10);
  }, [status, rg, rejection, rgDecision, demoOrders]);

  const mergedWatch = useMemo(() => (Array.isArray(watchItems) ? watchItems.map((row: Dict) => merge(row)) : []), [watchItems, merge]);
  const recentPaper = Array.isArray(demoOrders) ? demoOrders : [];
  const positionRows = Array.isArray(positions) ? positions : [];
  const beginnerLessons = LESSONS.filter((l) => l.level === 'beginner');
  const beginnerDone = beginnerLessons.filter((l) => progress.lessonsCompleted.includes(l.id)).length;
  const beginnerPct = beginnerLessons.length ? Math.round((beginnerDone / beginnerLessons.length) * 100) : 0;
  const nextLesson = LESSONS.find((l) => !progress.lessonsCompleted.includes(l.id));
  const hasLearnData =
    progress.lessonsCompleted.length + progress.challengesCompleted.length + progress.conceptsLearned.length + progress.simulations.length > 0;

  const rgBar = rgDecision || 'HOLD';

  const hasCycle = Boolean(
    status?.last_cycle_message || status?.last_decision || status?.last_debate || status?.last_halt_reason
  );

  async function runAnalysis() {
    setCycleBusy(true);
    setCycleMessage('');
    try {
      const response = await autonomous.runCycle(symbol);
      setCycleMessage(String(response.data?.message || response.data?.status || 'Cycle finished'));
      await mutateStatus();
    } catch (err) {
      setCycleMessage(err instanceof Error ? err.message : 'Cycle failed');
    } finally {
      setCycleBusy(false);
    }
  }

  async function askCopilot() {
    setCopilotBusy(true);
    try {
      const response = await copilot.ask(copilotQ);
      setCopilotA(String(response.data?.answer || 'Copilot had no answer for this question.'));
    } catch (err) {
      setCopilotA(err instanceof Error ? `MARKET DATA ERROR: ${err.message}` : 'MARKET DATA ERROR');
    } finally {
      setCopilotBusy(false);
    }
  }

  async function analyzeStock() {
    setAnalyzeBusy(true);
    setAnalyzeError('');
    try {
      await mutateMarket();
      await mutateAnalytics();
      await mutateOptions();
      await mutateIntel();
      const port = asDict(portfolio);
      const rawDd = Number(port.drawdown_pct || 0);
      const analysis = await analytics.analyze(symbol, `Analyze ${symbol}`);
      setAnalyzeSections(asDict(analysis.data?.sections));
      await debate
        .run({
          symbol,
          option_type: 'call',
          portfolio_value: Number(port.account_value || 100000),
          current_equity: Number(port.account_value || 100000),
          current_positions: 0,
          current_drawdown: rawDd > 1 ? rawDd / 100 : rawDd,
        })
        .catch(() => null);
      await mutateStatus();
    } catch (err) {
      setAnalyzeError(err instanceof Error ? err.message : 'Analysis unavailable');
    } finally {
      setAnalyzeBusy(false);
    }
  }

  return (
    <div className="bg-slate-950">
      <main className="flex flex-col gap-5 px-4 py-6 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <SafetyStatusStrip
            liveMarketData={streamStatus.state === 'LIVE' || Boolean(liveMarketData)}
            alpacaOk={alpacaOk}
            stale={String(freshness).toUpperCase() === 'STALE' || mergedWatch.some((row: Record<string, unknown>) => String(row.freshness).toUpperCase() === 'STALE')}
            disconnected={streamStatus.state === 'DISCONNECTED'}
            reconnecting={streamStatus.state === 'RECONNECTING' || streamStatus.state === 'CONNECTING'}
            connectionState={String(freshness).toUpperCase() === 'STALE' ? 'STALE' : streamStatus.state || (liveMarketData ? 'LIVE' : 'CONNECTING')}
          />
          <CallAgentButton symbol={symbol} />
            </div>
        {demo.enabled ? (
          <Panel title="Alpaca market-data connection">
            <p className="text-sm text-slate-200">
              Alpaca connection: {alpacaOk ? 'connected' : alpacaError ? 'unavailable' : 'not connected'}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              Live market data is separate from real-money execution. Demo trades use the virtual ledger only.
            </p>
          </Panel>
        ) : null}

        <Panel title="Portfolio summary">
          <p className="mb-3 text-[10px] font-bold uppercase tracking-wide text-sky-400">Demo User Virtual Account · $100,000 starting cash</p>
          {portfolioLoading && !p ? (
            <p className="text-sm text-slate-400">Loading portfolio…</p>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
              <Metric source="DEMO LEDGER" label="Cash" value={p ? moneyDisplay(p.cash) : moneyDisplay(100000)} />
              <Metric source="DEMO LEDGER" label="Buying Power" value={p ? moneyDisplay(p.buying_power) : moneyDisplay(100000)} />
              <Metric source="DEMO LEDGER" label="Portfolio Value" value={p ? moneyDisplay(p.equity ?? p.account_value) : moneyDisplay(100000)} />
              <Metric source="DEMO LEDGER" label="Unrealized P/L" value={p ? moneyDisplay(p.unrealized_pnl) : moneyDisplay(0)} valueClass={p ? pnlClass(p.unrealized_pnl) : ''} />
              <Metric source="DEMO LEDGER" label="Realized P&L" value={p ? moneyDisplay(p.realized_pnl ?? p.total_pnl) : moneyDisplay(0)} valueClass={p ? pnlClass(p.realized_pnl ?? p.total_pnl) : ''} />
            </div>
          )}
        </Panel>

        <div
          className={`grid grid-cols-2 gap-2 text-[11px] font-semibold uppercase tracking-wide sm:grid-cols-4 ${
            mode === 'critical' ? 'rounded-xl border-2 border-rose-500 bg-rose-950/40 p-3' : ''
          }`}
        >
          <div className={`rounded-lg border px-3 py-2 ${mode === 'critical' ? 'border-rose-500 text-rose-200' : 'border-slate-800 text-slate-200'}`}>
            Risk: {riskBadge}
          </div>
          <div className={`rounded-lg border border-slate-800 px-3 py-2 text-slate-200`}>Market: {sessionBar} · {marketState.marketStatus === 'CLOSED' ? 'MARKET CLOSED' : marketState.marketStatus}</div>
          <div className="rounded-lg border border-slate-800 px-3 py-2 text-slate-200">Data: {dataBadge}</div>
          <div className="rounded-lg border border-slate-800 px-3 py-2 text-slate-200">Risk Guardian: {rgBar}</div>
          {mode === 'critical' ? (
            <p className="col-span-2 text-sm font-bold uppercase tracking-wide text-rose-300 sm:col-span-4">NEW TRADES BLOCKED</p>
          ) : null}
          {!backendOk ? <p className="col-span-2 text-xs text-amber-300 sm:col-span-4">Backend MARKET DATA ERROR</p> : null}
        </div>

        <Panel title="Market Overview">
          <p className="mb-3 text-xs text-slate-400">Watchlist quotes from Alpaca. Click a symbol to open Stocks.</p>
          {watchLoading && mergedWatch.length === 0 ? (
            <p className="text-sm text-slate-400">Loading Alpaca watchlist…</p>
          ) : (
            <WatchlistTable items={mergedWatch} selected={symbol} />
          )}
        </Panel>

        <Panel title="Recent Trades">
          <RecentTradesList fills={recentPaper} />
        </Panel>

        <Panel title="AI Trading Mentor">
          <p className="mb-3 text-xs text-slate-400">Advisory only. Risk Guardian remains the final authority.</p>
          <div className="mb-3 flex flex-wrap gap-2">
            <CallAgentButton symbol={symbol} />
            <button type="button" disabled={analyzeBusy} onClick={() => void analyzeStock()} className="rounded-xl border border-slate-600 px-4 py-3 text-xs font-bold uppercase">
              {analyzeBusy ? 'Analyzing…' : 'Refresh AI analysis'}
            </button>
          </div>
          {analyzeError ? <p className="text-sm text-rose-300">{analyzeError}</p> : null}
          {analyzeSections ? (
            <div className="space-y-2 text-sm">
              <p><span className="text-sky-300">Market summary:</span> {shown(analyzeSections.market_snapshot)}</p>
              <p><span className="text-sky-300">Bull:</span> {shown(analyzeSections.bull_case)}</p>
              <p><span className="text-sky-300">Bear:</span> {shown(analyzeSections.bear_case)}</p>
              <p><span className="text-sky-300">Risk:</span> {shown(analyzeSections.key_risks)}</p>
              <p><span className="text-sky-300">Explanation:</span> {shown(analyzeSections.educational_explanation)}</p>
            </div>
          ) : (
            <p className="text-sm text-slate-400">Run analysis to load an educational AI summary for {symbol}.</p>
          )}
        </Panel>

        <MarketWatchCard
          symbol={symbol}
          onSymbolChange={setSymbol}
          market={market}
          error={marketError}
          loading={marketLoading}
          fetchedAt={fetchedAt}
          onRefresh={() => {
            void mutateMarket();
          }}
          onAnalyze={() => void analyzeStock()}
        />

        <DashboardAnalytics analytics={analyticsPayload} loading={analyticsLoading} error={analyticsError} />

        <Panel title="Analyze Stock" id="analyze">
          <p className="mb-3 text-xs text-slate-400">Fetches Alpaca quotes, options, intelligence, then advisory AI analysis. Not financial advice.</p>
          <button
            type="button"
            disabled={analyzeBusy}
            onClick={() => void analyzeStock()}
            className="rounded-lg bg-primary px-4 py-2 text-xs font-semibold uppercase text-white disabled:opacity-50"
          >
            {analyzeBusy ? 'Analyzing…' : 'Analyze Stock'}
          </button>
          {analyzeError ? <p className="mt-2 text-sm text-rose-300">{analyzeError}</p> : null}
          {analyzeSections ? (
            <div className="mt-4 space-y-3 text-sm">
              {[
                ['market_snapshot', 'Market Snapshot'],
                ['bull_case', 'Bull Scenario'],
                ['bear_case', 'Bear Scenario'],
                ['key_risks', 'Key Risks'],
                ['options_observations', 'Options Insights'],
                ['educational_explanation', 'AI Explanation'],
              ].map(([key, title]) => (
                <div key={key}>
                  <p className="text-[11px] font-bold uppercase tracking-wide text-sky-300">{title}</p>
                  <p className="text-slate-200">{shown(analyzeSections[key])}</p>
                </div>
              ))}
              {redWarnings.length ? (
                <div>
                  <p className="text-[11px] font-bold uppercase tracking-wide text-amber-300">Red Team</p>
                  <p className="text-slate-200">{redWarnings.join(' · ')}</p>
                </div>
              ) : null}
      </div>
          ) : null}
        </Panel>

        <TradeSimulatePanel
          symbol={symbol}
          onSymbolChange={setSymbol}
          market={merge({
            ...asDict(market),
            symbol,
            price: quote.last_trade_price ?? trade.price ?? asDict(market).price,
            bid: quote.bid ?? asDict(market).bid,
            ask: quote.ask ?? asDict(market).ask,
            spread: quoteSpread ?? asDict(market).spread,
            volume: lastBar.volume ?? asDict(market).volume,
            session,
            freshness,
          })}
        />

        <Panel title="Latest AI decision">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-sky-300">AI recommends. Deterministic Risk Guardian decides.</p>
          {!hasCycle ? (
            <EmptyState
              title="No analysis has been run yet."
              body="Run an analysis cycle to generate the latest AI decision, debate, and Risk Guardian result."
              action={
                <button
                  type="button"
                  disabled={cycleBusy}
                  onClick={() => void runAnalysis()}
                  className="mt-3 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-white"
                >
                  {cycleBusy ? 'Running…' : 'Run Analysis'}
                </button>
              }
            />
          ) : !status && statusError ? (
            <p className="text-sm font-semibold text-amber-300">MARKET DATA ERROR: autonomous status could not be loaded.</p>
          ) : (
            <div className="space-y-3">
              <Field label="Strategy" value={strategy} />
              <Field label="Scenario" value={scenario} />
              <Field label="Confidence" value={confidence} />
              <Field label="Reasoning" value={reasoning} />
              <div>
                <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Evidence</p>
                {evidence.length === 0 ? (
                  <p className="text-sm text-slate-400">No evidence recorded for this cycle. Common when the cycle halted (market closed, stale data, or NO TRADE).</p>
                ) : (
                  <ul className="list-disc space-y-1 pl-5 text-sm text-slate-200">
                    {evidence.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Risks</p>
                {riskItems.length === 0 ? (
                  <p className="text-sm text-slate-400">No risk list in this cycle output.</p>
                ) : (
                  <ul className="list-disc space-y-1 pl-5 text-sm text-slate-200">
                    {riskItems.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>
              <div>
                <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">Red Team objections</p>
                {redWarnings.length === 0 ? (
                  <p className="text-sm text-slate-400">No material objection identified.</p>
                ) : (
                  <ul className="list-disc space-y-1 pl-5 text-sm text-amber-200">
                    {redWarnings.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>
              <div className={`rounded-xl border p-4 ${finalLabel.includes('REJECTED') || mode === 'critical' ? 'border-rose-500 bg-rose-950/40' : 'border-slate-700'}`}>
                <p className="text-[11px] uppercase tracking-wide text-slate-400">Risk Guardian · Final decision</p>
                <p className="mt-2 text-xl font-bold text-white">{rgDecision}</p>
                <p className="mt-2 text-sm text-slate-300">{explainReason(rejection[0] || rg.reason || status?.last_halt_reason || status?.last_cycle_message || 'NO_TRADE')}</p>
                <p className="mt-1 text-xs text-slate-500">Analysis is separate from execution. {finalLabel}.</p>
              </div>
              <button type="button" disabled={cycleBusy} onClick={() => void runAnalysis()} className="rounded-lg border border-slate-600 px-3 py-1.5 text-xs">
                {cycleBusy ? 'Running…' : 'Run analysis again'}
              </button>
              {cycleMessage ? <p className="text-xs text-slate-400">{cycleMessage}</p> : null}
            </div>
          )}
        </Panel>

        <Panel title="Agent pipeline">
          {!hasCycle ? (
            <EmptyState
              title="No analysis has been run yet."
              body="The agent pipeline appears after a real cycle. Missing agents are not filled with invented output."
              action={
                <button type="button" disabled={cycleBusy} onClick={() => void runAnalysis()} className="mt-3 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-white">
                  {cycleBusy ? 'Running…' : 'Run Analysis'}
                </button>
              }
            />
          ) : (() => {
            const byName = Object.fromEntries(pipeline.map((node) => [node.name, node]));
            const linear = ['Market Intelligence', 'Market Scout', 'Strategy Brain'];
            const after = ['Red Team', 'Options Strategy', 'Decision Agent', 'Risk Guardian', 'Trade / No Trade'];
            return (
              <div className="space-y-1">
                {linear.map((name, idx) => {
                  const node = byName[name];
                  return (
                    <div key={name}>
                      {idx > 0 ? <p className="py-1 text-center text-slate-600">↓</p> : null}
                      <PipeNode name={node.name} status={node.status} detail={node.detail} />
                    </div>
                  );
                })}
                <p className="py-1 text-center text-slate-600">↙&nbsp;&nbsp;&nbsp;↘</p>
                <div className="grid grid-cols-2 gap-2">
                  <PipeNode name={byName.Bull.name} status={byName.Bull.status} detail={byName.Bull.detail} />
                  <PipeNode name={byName.Bear.name} status={byName.Bear.status} detail={byName.Bear.detail} />
                </div>
                <p className="py-1 text-center text-slate-600">↘&nbsp;&nbsp;&nbsp;↙</p>
                {after.map((name, idx) => {
                  const node = byName[name];
                  return (
                    <div key={name}>
                      {idx > 0 ? <p className="py-1 text-center text-slate-600">↓</p> : null}
                      <PipeNode name={node.name} status={node.status} detail={node.detail} />
                    </div>
                  );
                })}
              </div>
            );
          })()}
        </Panel>

        <Panel title="Risk overview">
          <div className="grid gap-2 text-sm sm:grid-cols-2">
            <Field label="Current mode" value={mode ? mode.toUpperCase() : 'NORMAL'} />
            <Field label="Peak equity" value={moneyDisplay(dd.peak_equity ?? health.peak_equity ?? p?.peak_equity ?? 100000)} />
            <Field label="Current equity" value={p ? moneyDisplay(p.equity ?? p.account_value) : moneyDisplay(dd.current_equity)} />
            <Field label="Drawdown" value={drawdownValue} />
            <Field label="Daily loss" value={p ? moneyDisplay(p.daily_pnl) : moneyDisplay(0)} />
            <Field label="Exposure" value={isMissing(health.exposure ?? health.exposure_pct) ? '0.00%' : pct(health.exposure ?? health.exposure_pct, true)} />
            <Field label="Concentration" value={isMissing(health.concentration) ? '0.00%' : pct(health.concentration, true)} />
            <Field label="Open positions" value={String(health.open_positions ?? positionRows.length ?? 0)} />
            <Field label="Buying power" value={p ? moneyDisplay(p.buying_power) : moneyDisplay(health.buying_power)} />
            <Field label="Volatility" value={shown(health.volatility || 'Not enough data')} />
          </div>
          <div className="mt-4 space-y-2 text-sm">
            <p>RiskGuardian checks: {checks.length ? checks.map((c) => `${c}: ${rejection.some((r) => r.includes(c)) ? 'FAIL' : 'PASS'}`).join(' · ') : 'No checks in this cycle yet'}</p>
            <p>RiskBodyguard: {bodyguardLabel}</p>
            <p>DrawdownGuardian: {ddMode === DATA_UNAVAILABLE || ddMode === NOT_AVAILABLE ? 'NORMAL' : ddMode}</p>
            {mode === 'critical' ? <p className="font-bold text-rose-300">NEW TRADES BLOCKED — {shown(status?.last_halt_reason || dd.reason)}</p> : null}
            {bg.reasons ? <p className="text-slate-400">{asList(bg.reasons).join(' ')}</p> : null}
          </div>
        </Panel>

        <Panel title="Portfolio Greeks">
            {greekStatus === 'NO_OPTION_POSITIONS' || greekStatus === 'LOADING' ? (
              <div>
                <div className="grid grid-cols-2 gap-3">
                  <Metric label="Delta" value="—" />
                  <Metric label="Gamma" value="—" />
                  <Metric label="Theta" value="—" />
                  <Metric label="Vega" value="—" />
                </div>
                <p className="mt-2 text-xs text-slate-500">No option positions</p>
                <p className="mt-1 text-xs text-slate-500">Greeks are calculated only for currently held option positions.</p>
              </div>
            ) : greekStatus === 'ERROR' || greekStatus === 'GREEKS_UNAVAILABLE' ? (
              <EmptyState
                title="GREEKS DATA UNAVAILABLE"
                body={String(greeks.notes || 'Option positions exist but required Greek inputs are missing.')}
              />
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <Metric label="Delta" value={greek('delta')} />
                  <Metric label="Gamma" value={greek('gamma')} />
                  <Metric label="Theta" value={greek('theta')} />
                  <Metric label="Vega" value={greek('vega')} />
                </div>
                {greeks.notes ? <p className="mt-3 text-xs text-slate-500">{String(greeks.notes)}</p> : null}
              </>
            )}
        </Panel>

        <Panel title="Positions">
            {positionsLoading && positionRows.length === 0 ? (
              <p className="text-sm text-slate-400">Loading positions…</p>
            ) : positionRows.length === 0 ? (
              <EmptyState title="No open positions." body="Demo positions appear after a filled virtual BUY. They persist after refresh." href="/stocks" action="Browse Stocks" />
            ) : (
              <div className="space-y-3">
                {positionRows.map((row: Dict, idx: number) => (
                  <div key={String(row.symbol || idx)} className="rounded-lg border border-slate-800 p-3 text-sm">
                    <p className="font-semibold text-white">{shown(row.symbol)}</p>
                    <p className="text-slate-300">
                      {shown(row.quantity)} share{Number(row.quantity) === 1 ? '' : 's'} · Avg entry {moneyDisplay(row.avg_entry ?? row.avg_entry_price)}
                    </p>
                    <p className="text-slate-300">Current {moneyDisplay(row.current_price)} · Market value {moneyDisplay(row.market_value)}</p>
                    <p className={`tabular-nums ${pnlClass(row.unrealized_pnl ?? row.pnl)}`}>
                      {moneyDisplay(row.unrealized_pnl ?? row.pnl)}
                      {typeof row.pnl_pct === 'number' ? ` · ${pct(row.pnl_pct, true)}` : ''}
            </p>
          </div>
                ))}
          </div>
            )}
        </Panel>

        <OptionsChainPanel symbol={symbol} onSymbolChange={setSymbol} options={liveOptions} error={optionsError} />

        <Panel title="Quant Copilot">
          <p className="mb-3 text-xs text-slate-400">LLM is explanatory only. Copilot never executes trades.</p>
          <div className="flex flex-wrap gap-2">
            {COPILOT_EXAMPLES.map((item) => (
              <button
                key={item}
                type="button"
                className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-300"
                onClick={() => setCopilotQ(item)}
              >
                {item}
              </button>
            ))}
          </div>
          <p className="mt-3 text-sm text-slate-300">{copilotQ}</p>
          <button
            type="button"
            disabled={copilotBusy}
            onClick={() => void askCopilot()}
            className="mt-3 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            Ask Copilot
          </button>
          {copilotA ? <p className="mt-3 text-sm text-slate-200">{copilotA}</p> : null}
          <Link href="/copilot" className="mt-3 inline-block text-xs text-sky-300">
            Open Quant Copilot
            </Link>
        </Panel>

        <Panel title="Recent activity">
          {activityRows.length === 0 ? (
            <p className="text-sm text-slate-400">No activity yet. Run analysis, a debate, a simulated trade, or a voice alert to populate the audit trail.</p>
          ) : (
            <ul className="space-y-2 text-sm">
              {activityRows.map((row) => (
                <li key={row.id} className="rounded-lg border border-slate-800 px-3 py-2">
                  <span className="mr-2 text-[10px] font-bold uppercase text-slate-400">{row.label}</span>
                  <span className={`mr-2 text-[10px] font-bold uppercase ${row.klass === 'REAL_PAPER_ORDER' ? 'text-sky-300' : 'text-amber-300'}`}>
                    {row.klass}
                  </span>
                  <span className="text-slate-200">{row.message}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Your learning">
          {!learnReady ? (
            <p className="text-sm text-slate-400">Loading stored learning state…</p>
          ) : !hasLearnData ? (
            <p className="text-sm text-slate-400">No learning progress stored yet. Open the learning path to begin.</p>
          ) : (
            <div className="space-y-3 text-sm">
              <p>Beginner</p>
              <div className="h-2 overflow-hidden rounded bg-slate-800">
                <div className="h-full bg-sky-500" style={{ width: `${beginnerPct}%` }} />
            </div>
              <p className="text-slate-400">{beginnerPct}%</p>
              <p>Concepts learned: {progress.conceptsLearned.length}</p>
              <p>Challenges completed: {progress.challengesCompleted.length}</p>
              <p>Simulations completed: {progress.simulations.length}</p>
              <p>Next lesson: {nextLesson ? nextLesson.title : 'All listed lessons completed'}</p>
            </div>
          )}
          <Link href="/learn" className="mt-3 inline-block text-xs text-sky-300">
            Open learning
          </Link>
        </Panel>

        <Panel title="What happens if..." simulated>
          <p className="mb-3 text-xs font-bold uppercase tracking-wide text-amber-300">SIMULATION ONLY · does not execute orders</p>
          <div className="flex flex-wrap gap-2">
            {WHAT_IF_SHOCKS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setShockId(item.id)}
                className={`rounded-lg border px-3 py-1 text-xs ${shockId === item.id ? 'border-sky-500 text-white' : 'border-slate-700 text-slate-300'}`}
              >
                {SHOCK_LABELS[item.id]}
              </button>
            ))}
            </div>
          <div className="mt-4 space-y-2 text-sm">
            <Field simulated label="Estimated scenario impact" value={`${simPnl.toFixed(2)} classroom P&L (per labeled assumptions)`} />
            <Field simulated label="Risk changes" value={shock.extraDrawdownPct ? `educational drawdown overlay ${shock.extraDrawdownPct}` : 'held constant except the selected shock'} />
            <Field simulated label="Greeks changes" value="first-order classroom approximation only" />
            <p className="text-xs text-slate-400">{shock.assumption}</p>
          </div>
          <Link href="/learn/simulator" className="mt-3 inline-block text-xs text-sky-300">
            Open full simulator
          </Link>
        </Panel>

        <Panel title="Mobile access">
          <QRCodeComponent />
        </Panel>
      </main>
    </div>
  );
}
