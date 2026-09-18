'use client';

import type { ReactNode } from 'react';
import { useState } from 'react';
import Link from 'next/link';
import { useAutonomousStatus } from '@/hooks/useApi';
import { useDemoMode } from '@/hooks/useDemoMode';
import { SimulatedMark } from '@/components/DemoBanner';
import { isMissing, isUnavailableDisplay, text } from '@/lib/format';
import { collectConfidence, CONFIDENCE_NOT_PROVIDED, decisionReasonText, displayList, intelEvidence, optionsStatus, riskGuardianCopy } from '@/lib/agentDisplay';
import { explainReason, formatCycleStatus, formatDecision, pickFirstReason, reasonCodeLabel } from '@/lib/reasonCodes';
import { autonomous } from '@/lib/api';
import { EmptyState } from '@/components/EmptyState';

type Dict = Record<string, unknown>;

const NO_TRADE_HALTS = new Set([
  'NO_TRADE',
  'MARKET_CLOSED',
  'MISSING_DATA',
  'STALE_DATA',
  'CRITICAL_MODE',
  'INVALID_CONTRACT',
  'LIVE_TRADING_BLOCKED',
  'DUPLICATE_CYCLE',
]);

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

function asList(value: unknown): string[] {
  if (isMissing(value)) return [];
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object') return JSON.stringify(item);
        return String(item);
      })
      .filter((item) => item && !isUnavailableDisplay(item));
  }
  if (typeof value === 'object') {
    return Object.entries(value as Dict)
      .filter(([, v]) => !isMissing(v) && v !== false)
      .map(([k, v]) => (typeof v === 'object' ? `${k}: ${JSON.stringify(v)}` : `${k}: ${String(v)}`));
  }
  return [String(value)];
}

function agentBody(output: unknown): Dict {
  const raw = asDict(output);
  const nested = asDict(raw.data);
  return Object.keys(nested).length ? nested : raw;
}

type AgentView = {
  id: string;
  name: string;
  recommendation: string;
  confidence: string;
  reasoning: string;
  evidence: string[];
  risks: string[];
  objections: string[];
  present: boolean;
  gate?: boolean;
  hideConfidence?: boolean;
  statusLine?: string;
  missingInputs?: string[];
  explanation?: string;
};

function fromAgentOutput(id: string, name: string, output: unknown, errors?: unknown): AgentView {
  const raw = asDict(output);
  const body = agentBody(output);
  const present = Object.keys(raw).length > 0;
  const rec =
    body.recommendation ??
    body.decision ??
    body.strategy ??
    body.direction ??
    body.viable;
  const evidence = [
    ...asList(body.evidence),
    ...asList(body.supporting_evidence),
    ...asList(body.bullish_evidence),
    ...asList(body.bearish_evidence),
    ...asList(body.selected_contracts),
    ...asList(body.strategy_details),
  ];
  const objections = [...asList(raw.errors), ...asList(errors), ...asList(body.objections), ...asList(body.decision_rules)];
  const reasoning = present ? text(raw.reasoning || body.reasoning || body.llm_explanation || body.notes, 'No reasoning text was provided.') : 'No agent output for this cycle.';
  const recommendation = present ? formatDecision(rec) : 'NO TRADE';
  const extra: Partial<AgentView> = {};
  if (id === 'strategy_agent') {
    extra.statusLine = optionsStatus(reasoning, recommendation) || undefined;
    extra.reasoning = optionsStatus(reasoning, recommendation)
      ? 'Options data is not currently sufficient to evaluate an options strategy.'
      : reasoning;
    extra.hideConfidence = true;
  }
  if (id === 'decision_agent') {
    const parsed = decisionReasonText(body, reasoning);
    extra.reasoning = parsed.reason;
    extra.missingInputs = parsed.missing;
    extra.hideConfidence = true;
  }
  const decisionMissing = id === 'decision_agent' && (extra.missingInputs?.length || 0) > 0;
  return {
    id,
    name,
    present,
    recommendation: present ? formatDecision(rec || (id === 'strategy_agent' || id === 'decision_agent' ? 'NO_TRADE' : rec)) : 'No output this cycle',
    confidence: collectConfidence(raw.confidence, body.confidence, asDict(body.data).confidence),
    reasoning: extra.reasoning || reasoning,
    evidence: displayList(evidence, 'evidence'),
    risks: displayList(asList(body.risks), 'risks'),
    objections: displayList(decisionMissing ? [] : objections, 'objections'),
    hideConfidence: extra.hideConfidence,
    statusLine: extra.statusLine,
    missingInputs: extra.missingInputs,
  };
}

function fromIntel(intel: unknown): AgentView {
  const body = asDict(intel);
  const present = Object.keys(body).length > 0;
  const evidence = intelEvidence({ ...body, ...asDict(body.real_data) });
  const availability = String(body.availability || (present ? 'AVAILABLE' : 'UNKNOWN')).toUpperCase();
  return {
    id: 'market_intelligence',
    name: 'Market Intelligence',
    present,
    recommendation: present ? `STATUS: ${availability === 'DATA_UNAVAILABLE' ? 'PARTIAL / OPTIONAL FEEDS MISSING' : availability}` : 'STATUS: UNKNOWN',
    confidence: CONFIDENCE_NOT_PROVIDED,
    reasoning: present ? text(body.notes, 'Market intelligence is a data availability layer, not a trade recommendation.') : 'No market intelligence payload this cycle.',
    evidence,
    risks: displayList(asList(body.unavailable_without_source), 'risks'),
    objections: displayList(asList(body.errors), 'objections'),
    hideConfidence: true,
  };
}

function fromStrategyBrain(scenarios: unknown): AgentView {
  const list = Array.isArray(scenarios) ? scenarios.map(asDict) : [];
  const present = list.length > 0;
  const ranked = [...list].sort((a, b) => Number(b.confidence || 0) - Number(a.confidence || 0));
  const top = ranked[0] || {};
  return {
    id: 'strategy_brain',
    name: 'Strategy Brain',
    present,
    recommendation: present ? formatDecision(top.scenario || top.expected_direction) : 'No output this cycle',
    confidence: present ? collectConfidence(top.confidence) : CONFIDENCE_NOT_PROVIDED,
    reasoning: present ? text(top.thesis, 'No thesis provided.') : 'No strategy-brain output this cycle.',
    evidence: displayList(list.flatMap((s) => asList(s.supporting_evidence).map((item) => `${text(s.scenario)}: ${item}`)), 'evidence'),
    risks: displayList(list.flatMap((s) => asList(s.risks)), 'risks'),
    objections: displayList(list.flatMap((s) => asList(s.invalidation_conditions)), 'objections'),
  };
}

function fromRedTeam(red: unknown): AgentView {
  const body = asDict(red);
  const present = Object.keys(body).length > 0;
  let recommendation = 'No recommendation provided';
  if (present && typeof body.approved_for_review === 'boolean') {
    recommendation = body.approved_for_review ? 'approved_for_review' : 'not_approved_for_review';
  }
  return {
    id: 'red_team',
    name: 'Red Team Critic',
    present,
    recommendation,
    confidence: present ? collectConfidence(body.confidence) : CONFIDENCE_NOT_PROVIDED,
    reasoning: present ? text(body.llm_advisory || body.severity, 'No red-team narrative provided.') : 'No red-team output this cycle.',
    evidence: displayList(asList(body.risk_flags), 'evidence'),
    risks: displayList(asList(body.missing_information), 'risks'),
    objections: displayList(asList(body.objections), 'objections'),
  };
}

function fromRiskGuardian(rg: unknown): AgentView {
  const body = asDict(rg);
  const present = Object.keys(body).length > 0;
  const copy = riskGuardianCopy(body);
  return {
    id: 'risk_guardian',
    name: 'Risk Guardian',
    gate: true,
    present,
    hideConfidence: true,
    recommendation: present ? copy.decision : 'BLOCK',
    confidence: CONFIDENCE_NOT_PROVIDED,
    reasoning: present ? copy.reasonCode : 'Risk Guardian has not produced a decision this cycle.',
    explanation: present ? copy.explanation : undefined,
    evidence: displayList(asList(body.limits_checked), 'evidence'),
    risks: displayList(asList(body.rejection_reasons), 'risks'),
    objections: displayList(asList(body.rejection_reasons), 'objections'),
    statusLine: 'DETERMINISTIC FINAL RISK GATE',
  };
}

function Arrow() {
  return (
    <div className="flex justify-center py-1 text-slate-500" aria-hidden>
      ↓
    </div>
  );
}

function AgentCard({ agent }: { agent: AgentView }) {
  const unavailable = (value: string) => isUnavailableDisplay(value);
  const gate = Boolean(agent.gate);
  const showConfidence = !agent.hideConfidence && !gate;
  return (
    <article
      className={`rounded-xl border p-4 sm:p-5 ${
        gate
          ? 'border-amber-500/80 bg-amber-950/30 shadow-[0_0_0_1px_rgba(245,158,11,0.25)]'
          : 'border-slate-700/80 bg-slate-900/70'
      }`}
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className={`text-sm font-semibold uppercase tracking-[0.14em] ${gate ? 'text-amber-300' : 'text-slate-200'}`}>
          {agent.name}
        </h3>
        {gate ? (
          <span className="rounded border border-amber-500 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-amber-300">
            Deterministic Final Risk Gate
          </span>
        ) : null}
      </div>
      {!agent.present ? (
        <p className="text-sm text-slate-400">No output from this agent in the current cycle.</p>
      ) : (
        <dl className="space-y-3 text-sm">
          {agent.statusLine ? (
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-slate-500">Status</dt>
              <dd className="mt-0.5 font-semibold text-amber-200">{agent.statusLine}</dd>
            </div>
          ) : null}
          <div>
            <dt className="text-[11px] uppercase tracking-wide text-slate-500">{gate ? 'Decision' : agent.id === 'market_intelligence' ? 'Status' : 'Recommendation'}</dt>
            <dd className={`mt-0.5 font-medium ${unavailable(agent.recommendation) ? 'text-amber-300' : 'text-white'}`}>
              {agent.recommendation}
            </dd>
          </div>
          {gate ? (
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-slate-500">Authority</dt>
              <dd className="mt-0.5 font-semibold text-amber-200">DETERMINISTIC RISK GUARDIAN</dd>
            </div>
          ) : null}
          {showConfidence ? (
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-slate-500">Confidence</dt>
              <dd className="mt-0.5 tabular-nums text-slate-100">{agent.confidence}</dd>
            </div>
          ) : agent.id === 'market_intelligence' ? (
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-slate-500">Confidence</dt>
              <dd className="mt-0.5 text-slate-400">Not provided</dd>
            </div>
          ) : null}
          <div>
            <dt className="text-[11px] uppercase tracking-wide text-slate-500">{gate ? 'Reason' : 'Reasoning'}</dt>
            <dd className="mt-0.5 text-slate-300">{agent.reasoning}</dd>
          </div>
          {gate && agent.explanation ? (
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-slate-500">Explanation</dt>
              <dd className="mt-0.5 text-slate-300">{agent.explanation}</dd>
            </div>
          ) : null}
          {agent.missingInputs && agent.missingInputs.length ? (
            <div>
              <dt className="text-[11px] uppercase tracking-wide text-slate-500">Missing analyses</dt>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-slate-300">
                {agent.missingInputs.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <FieldList label="Evidence" items={agent.evidence} />
          <FieldList label="Risks" items={agent.risks} />
          <FieldList label="Objections" items={agent.objections} />
          {gate ? <p className="pt-2 text-xs font-semibold uppercase tracking-wide text-amber-200">AI recommends. Risk Guardian decides.</p> : null}
        </dl>
      )}
    </article>
  );
}

function FieldList({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-slate-500">{label}</p>
      <ul className="mt-1 list-disc space-y-1 pl-5">
        {items.map((item, idx) => (
          <li key={`${label}-${idx}`} className="text-slate-300">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Stage({ children }: { children: ReactNode }) {
  return <div className="mx-auto w-full max-w-3xl">{children}</div>;
}

function resolveVerdict(status: Dict, rg: Dict, decision: Dict): { label: string; reason: string; tone: string } {
  const halt = String(status.last_halt_reason || '');
  const cycleStatus = String(status.last_cycle_status || '');
  const decisionVal = String(decision.decision || '').toLowerCase();
  const rgDecision = String(rg.decision || '').toLowerCase();
  const message = status.last_cycle_message;
  const rejections = [
    ...asList(status.last_rejection_reasons),
    ...asList(rg.rejection_reasons),
  ];
  const decisionReason = decision.reasoning;

  const reasonFrom = (...candidates: unknown[]) => {
    const picked = pickFirstReason(...candidates);
    return explainReason(picked, explainReason(halt || cycleStatus || 'NO_TRADE'));
  };

  if (cycleStatus === 'risk_rejected' || halt === 'RISK_GUARDIAN_REJECTED') {
    return {
      label: 'TRADE REJECTED',
      reason: reasonFrom(rejections, rg.reason, message, halt),
      tone: 'border-rose-500 bg-rose-950/50 text-rose-200',
    };
  }

  if (
    NO_TRADE_HALTS.has(halt) ||
    cycleStatus === 'no_trade' ||
    cycleStatus === 'critical_mode' ||
    cycleStatus === 'live_blocked' ||
    cycleStatus === 'debate_failed' ||
    decisionVal === 'no_trade'
  ) {
    return {
      label: 'NO TRADE',
      reason: reasonFrom(rg.reason, halt, decision.execution_reason, message, decisionReason, cycleStatus),
      tone: 'border-slate-500 bg-slate-900 text-slate-200',
    };
  }

  if (rgDecision === 'approved' || halt === 'DRY_RUN_ONLY' || cycleStatus === 'halted_after_risk_guardian') {
    return {
      label: 'TRADE APPROVED',
      reason: reasonFrom(message, halt, 'Risk Guardian decision: approved'),
      tone: 'border-emerald-500 bg-emerald-950/40 text-emerald-200',
    };
  }

  if (rgDecision === 'rejected') {
    return {
      label: 'TRADE REJECTED',
      reason: reasonFrom(rejections, rg.reason, message),
      tone: 'border-rose-500 bg-rose-950/50 text-rose-200',
    };
  }

  return {
    label: 'NO VERDICT YET',
    reason: reasonFrom(message, halt, cycleStatus, 'No verdict yet.'),
    tone: 'border-amber-500 bg-amber-950/30 text-amber-200',
  };
}

export default function AIDebate() {
  const demo = useDemoMode();
  const { status: liveStatus, isLoading, error, mutate } = useAutonomousStatus();
  const [cycleBusy, setCycleBusy] = useState(false);
  const [cycleMessage, setCycleMessage] = useState('');
  const status = demo.enabled ? demo.bundle.status : liveStatus;
  const engine = asDict(status);
  const debate = asDict(engine.last_debate);
  const outputs = asDict(debate.agent_outputs);
  const errors = asDict(debate.agent_errors);
  const decision = Object.keys(asDict(engine.last_decision)).length
    ? asDict(engine.last_decision)
    : asDict(debate.final_decision);
  const rg = asDict(debate.risk_guardian_result);

  const hasCycle = Boolean(
    engine.last_debate ||
      engine.last_market_intelligence ||
      engine.last_red_team ||
      engine.last_strategy_brain ||
      engine.last_cycle_status
  );

  const intel = fromIntel(engine.last_market_intelligence);
  const scout = fromAgentOutput('market_scout', 'Market Scout', outputs.market_scout, errors.market_scout);
  const brain = fromStrategyBrain(engine.last_strategy_brain);
  const bull = fromAgentOutput('bull_agent', 'Bull', outputs.bull_agent, errors.bull_agent);
  const bear = fromAgentOutput('bear_agent', 'Bear', outputs.bear_agent, errors.bear_agent);
  const red = fromRedTeam(engine.last_red_team);
  const strategy = fromAgentOutput(
    'strategy_agent',
    'Options Strategy',
    outputs.strategy_agent,
    errors.strategy_agent
  );
  const decisionAgent = fromAgentOutput(
    'decision_agent',
    'Decision Agent',
    outputs.decision_agent,
    errors.decision_agent
  );
  const guardian = fromRiskGuardian(rg);
  const verdict = hasCycle ? resolveVerdict(engine, rg, decision) : null;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Trade AI</p>
            <h1 className="text-xl font-bold text-white sm:text-2xl">AI Debate</h1>
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

      <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
        {!demo.enabled && isLoading && !status ? (
          <div className="rounded-xl border border-slate-800 bg-slate-900/70 px-6 py-16 text-center text-slate-400">
            Loading cycle data…
          </div>
        ) : !demo.enabled && error ? (
          <div className="rounded-xl border border-rose-800 bg-rose-950/40 px-6 py-16 text-center">
            <p className="font-semibold text-rose-200">Unable to load backend cycle data</p>
            <p className="mt-2 text-sm text-rose-300">{error instanceof Error ? error.message : String(error)}</p>
          </div>
        ) : !hasCycle ? (
          <div className="space-y-4">
            <EmptyState
              title="No debate from a backend cycle yet"
              body="Run an analysis cycle. This page only renders real cycle output and will not invent agent results."
              action={
                <button
                  type="button"
                  disabled={cycleBusy}
                  onClick={async () => {
                    setCycleBusy(true);
                    setCycleMessage('');
                    try {
                      const response = await autonomous.runCycle();
                      setCycleMessage(String(response.data?.message || response.data?.status || 'Cycle finished'));
                      await mutate();
                    } catch (err) {
                      setCycleMessage(err instanceof Error ? err.message : 'Cycle failed');
                    } finally {
                      setCycleBusy(false);
                    }
                  }}
                  className="mt-3 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-white"
                >
                  {cycleBusy ? 'Running…' : 'Run Analysis'}
                </button>
              }
            />
            {cycleMessage ? <p className="text-center text-sm text-slate-400">{cycleMessage}</p> : null}
          </div>
        ) : (
          <div className="space-y-1">
            <div className="mb-5 rounded-xl border border-slate-800 bg-slate-900/60 p-4 text-sm text-slate-300">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">Symbol</p>
                  <p className="font-semibold text-white">{text(debate.symbol)}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">Cycle status</p>
                  <p className="font-semibold text-white">{formatCycleStatus(engine.last_cycle_status)}</p>
                </div>
                <div>
                  <p className="text-[11px] uppercase tracking-wide text-slate-500">Halt reason</p>
                  <p className="font-semibold text-white">{reasonCodeLabel(engine.last_halt_reason) || explainReason(engine.last_halt_reason)}</p>
                </div>
              </div>
            </div>

            <Stage>
              <AgentCard agent={intel} />
            </Stage>
            <Arrow />
            <Stage>
              <AgentCard agent={scout} />
            </Stage>
            <Arrow />
            <Stage>
              <AgentCard agent={brain} />
            </Stage>
            <Arrow />
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <AgentCard agent={bull} />
              <AgentCard agent={bear} />
            </div>
            <div className="hidden justify-center gap-24 py-1 text-slate-500 md:flex" aria-hidden>
              <span>↘</span>
              <span>↙</span>
            </div>
            <Arrow />
            <Stage>
              <AgentCard agent={red} />
            </Stage>
            <Arrow />
            <Stage>
              <AgentCard agent={strategy} />
            </Stage>
            <Arrow />
            <Stage>
              <AgentCard agent={decisionAgent} />
            </Stage>
            <Arrow />
            <Stage>
              <AgentCard agent={guardian} />
            </Stage>
            <Arrow />
            {verdict ? (
              <section className={`rounded-xl border-2 px-5 py-6 text-center ${verdict.tone}`}>
                <p className="text-[11px] font-semibold uppercase tracking-[0.22em] opacity-80">Final result</p>
                <h2 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">{verdict.label}</h2>
                <p className="mx-auto mt-3 max-w-2xl text-sm">
                  <span className="opacity-70">Exact reason: </span>
                  {verdict.reason}
                </p>
              </section>
            ) : null}
          </div>
        )}
      </main>
    </div>
  );
}
