'use client';

import Link from 'next/link';
import { useActivity, useMemory, useOrders } from '@/hooks/useApi';
import { isMissing, text } from '@/lib/format';
import { useDemoMode } from '@/hooks/useDemoMode';
import { SimulatedMark } from '@/components/DemoBanner';

type Dict = Record<string, unknown>;

const DRY_RUN = 'DRY_RUN_SIMULATED';
const REAL_PAPER = 'REAL_PAPER_ORDER';

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

type TrailEvent = {
  id: string;
  timestamp: string;
  cycle_id: string;
  event: string;
  category: string;
  severity: string;
  symbol: string;
  message: string;
  execution_class: typeof DRY_RUN | typeof REAL_PAPER;
};

function categoryFor(event: string, executionClass: typeof DRY_RUN | typeof REAL_PAPER): string {
  const type = event.toLowerCase();
  if (type.includes('voice')) return 'Voice alert';
  if (type.includes('debate') || type.includes('bull') || type.includes('bear') || type.includes('red_team')) return 'AI Debate';
  if (type.includes('risk_guardian') || type.includes('risk_rejection') || type.includes('risk_approval') || type.includes('bodyguard')) return 'Risk decision';
  if (type.includes('simulate') || type.includes('dry_run') || (type.includes('order') && executionClass === DRY_RUN)) return 'Simulated trade';
  if (executionClass === REAL_PAPER) return 'Paper order';
  if (type.includes('learn') || type.includes('lesson')) return 'Learning event';
  return 'Analysis';
}

function parseTime(value: string): number {
  const t = Date.parse(value);
  return Number.isFinite(t) ? t : 0;
}

function isRealPaperOrder(meta: Dict, dryRun: unknown, alpacaId: unknown): boolean {
  if (dryRun === true) return false;
  if (isMissing(alpacaId) && isMissing(meta.alpaca_order_id) && isMissing(meta.alpaca_id)) return false;
  return dryRun === false || Boolean(alpacaId || meta.alpaca_order_id || meta.alpaca_id);
}

function fromAudit(row: Dict): TrailEvent {
  const meta = asDict(row.metadata);
  const type = String(row.event_type || 'audit');
  const orderLike = type.startsWith('order_');
  const alpacaId = row.alpaca_order_id || meta.alpaca_order_id || meta.alpaca_id;
  const dryRun = row.dry_run ?? meta.dry_run;
  const real = orderLike && isRealPaperOrder(meta, dryRun, alpacaId);
  let message = text(row.message);
  if (!real && (type === 'order_filled' || type === 'order_submitted')) {
    message = `${message} — not executed (DRY RUN / simulated only)`;
  }
  return {
    id: String(row.event_id || `audit-${row.timestamp}-${type}`),
    timestamp: text(row.timestamp),
    cycle_id: text(row.cycle_id || meta.cycle_id),
    event: type,
    severity: text(row.severity),
    symbol: isMissing(row.symbol) ? 'NO SYMBOL' : String(row.symbol),
    message,
    execution_class: real ? REAL_PAPER : DRY_RUN,
    category: categoryFor(type, real ? REAL_PAPER : DRY_RUN),
  };
}

function fromMemory(row: Dict, index: number): TrailEvent[] {
  const events: TrailEvent[] = [];
  const cycleId = text(row.cycle_id);
  const ts = text(row.timestamp);
  const symbol = isMissing(row.symbol) ? 'NO SYMBOL' : String(row.symbol);
  const dry = row.dry_run !== false;
  const rg = asDict(row.risk_guardian_result);
  const objections = asList(row.red_team_objections).map(String);
  const summaries = asDict(row.agent_reasoning_summaries);
  const entry = asDict(row.entry);
  const alpacaId = entry.alpaca_order_id || entry.alpaca_id;
  const realOrder = !dry && isRealPaperOrder(entry, row.dry_run, alpacaId);

  events.push({
    id: `memory-${cycleId}-${index}`,
    timestamp: ts,
    cycle_id: cycleId,
    event: dry ? 'dry_run_cycle' : 'cycle_memory',
    severity: String(row.outcome || '') === 'blocked' ? 'high' : 'info',
    symbol,
    message: `Cycle outcome ${text(row.outcome)}${row.decision ? ` · decision ${String(row.decision)}` : ''}${
      dry ? ' — DRY RUN / simulated only; not executed' : ''
    }`,
    execution_class: realOrder ? REAL_PAPER : DRY_RUN,
    category: categoryFor(dry ? 'dry_run_cycle' : 'cycle_memory', realOrder ? REAL_PAPER : DRY_RUN),
  });

  if (!isMissing(row.strategy) || summaries.strategy) {
    events.push({
      id: `memory-strategy-${cycleId}-${index}`,
      timestamp: ts,
      cycle_id: cycleId,
      event: 'strategy_analysis',
      severity: 'info',
      symbol,
      message: text(row.strategy || summaries.strategy),
      execution_class: DRY_RUN,
      category: categoryFor('strategy_analysis', DRY_RUN),
    });
  }

  if (summaries.decision) {
    events.push({
      id: `memory-decision-${cycleId}-${index}`,
      timestamp: ts,
      cycle_id: cycleId,
      event: 'decision',
      severity: 'info',
      symbol,
      message: text(summaries.decision),
      execution_class: DRY_RUN,
      category: categoryFor('decision', DRY_RUN),
    });
  }

  if (objections.length) {
    events.push({
      id: `memory-redteam-${cycleId}-${index}`,
      timestamp: ts,
      cycle_id: cycleId,
      event: 'red_team_objections',
      severity: 'warning',
      symbol,
      message: objections.join(' · '),
      execution_class: DRY_RUN,
      category: categoryFor('red_team_objections', DRY_RUN),
    });
  }

  if (Object.keys(rg).length) {
    events.push({
      id: `memory-rg-${cycleId}-${index}`,
      timestamp: ts,
      cycle_id: cycleId,
      event: 'risk_guardian',
      severity: String(rg.decision).toLowerCase() === 'approved' ? 'info' : 'warning',
      symbol,
      message: `RiskGuardian ${text(rg.decision)}${
        asList(rg.rejection_reasons).length ? ` · ${asList(rg.rejection_reasons).map(String).join(' · ')}` : ''
      }`,
      execution_class: DRY_RUN,
      category: categoryFor('risk_guardian', DRY_RUN),
    });
  }

  if (!isMissing(row.risk_mode)) {
    events.push({
      id: `memory-mode-${cycleId}-${index}`,
      timestamp: ts,
      cycle_id: cycleId,
      event: 'drawdown_mode',
      severity: String(row.risk_mode).toLowerCase() === 'critical' ? 'critical' : 'info',
      symbol,
      message: `Drawdown / risk mode ${text(row.risk_mode)}`,
      execution_class: DRY_RUN,
      category: categoryFor('drawdown_mode', DRY_RUN),
    });
  }

  return events;
}

function fromPaperOrder(row: Dict, index: number): TrailEvent | null {
  const alpacaId = row.alpaca_order_id || row.alpaca_id;
  if (isMissing(alpacaId)) return null;
  return {
    id: String(row.order_id || `paper-${alpacaId}-${index}`),
    timestamp: text(row.submitted_at || row.filled_at || row.timestamp),
    cycle_id: text(row.cycle_id),
    event: String(row.status || 'order'),
    severity: 'info',
    symbol: text(row.symbol),
    message: `REAL paper order ${text(row.side)} qty ${text(row.quantity)} status ${text(row.status)} id ${String(alpacaId)}`,
    execution_class: REAL_PAPER,
    category: categoryFor('paper_order', REAL_PAPER),
  };
}

function severityClass(severity: string): string {
  switch (severity) {
    case 'critical':
      return 'border-rose-700 bg-rose-950/30 text-rose-200';
    case 'high':
    case 'warning':
      return 'border-amber-700 bg-amber-950/30 text-amber-200';
    default:
      return 'border-slate-700 bg-slate-900/60 text-slate-200';
  }
}

export default function ActivityMemoryPage() {
  const demo = useDemoMode();
  const { activity, isLoading: activityLoading, error: activityError } = useActivity();
  const { memory, isLoading: memoryLoading, error: memoryError } = useMemory();
  const { orders, error: ordersError } = useOrders();

  const demoEvents: TrailEvent[] = demo.enabled
    ? demo.bundle.activity.map((row) => {
        const event = fromAudit(asDict(row));
        return { ...event, message: event.message.includes('SIMULATED') ? event.message : `SIMULATED — ${event.message}` };
      })
    : [];

  const events: TrailEvent[] = [];
  if (!demo.enabled) {
    if (!activityError) {
      for (const row of asList(activity)) events.push(fromAudit(asDict(row)));
    }
    if (!memoryError) {
      asList(memory).forEach((row, index) => events.push(...fromMemory(asDict(row), index)));
    }
    if (!ordersError) {
      asList(orders).forEach((row, index) => {
        const paper = fromPaperOrder(asDict(row), index);
        if (paper) events.push(paper);
      });
    }
  }

  const seen = new Set<string>();
  const unique = (demo.enabled ? demoEvents : events).filter((item) => {
    const key = `${item.timestamp}|${item.event}|${item.message}|${item.cycle_id}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
  unique.sort((a, b) => parseTime(b.timestamp) - parseTime(a.timestamp));

  const loading = demo.enabled ? false : (activityLoading || memoryLoading) && unique.length === 0;
  const failed = demo.enabled ? false : Boolean(activityError && memoryError);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Trade AI</p>
            <h1 className="text-xl font-bold text-white sm:text-2xl">Activity / Memory</h1>
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

      <main className="mx-auto max-w-5xl space-y-4 px-4 py-6 sm:px-6">
        {demo.enabled ? (
          <p className="rounded-lg border border-fuchsia-700 bg-fuchsia-950/40 px-4 py-3 text-sm text-fuchsia-100">
            DEMO MODE showing SIMULATED audit events only. Live paper account activity is hidden so it is not mixed with simulated values. Exit demo to view live paper audit data.
          </p>
        ) : (
          <p className="text-sm text-slate-400">
            Chronological audit trail and post-trade memory. Simulated cycle actions are labeled{' '}
            <span className="font-semibold text-amber-300">{DRY_RUN}</span>. Actual Alpaca paper orders, if any, are labeled{' '}
            <span className="font-semibold text-emerald-300">{REAL_PAPER}</span>. Simulated orders are never shown as executed.
          </p>
        )}

        {loading ? (
          <p className="rounded-xl border border-slate-800 bg-slate-900/70 px-6 py-16 text-center text-slate-400">
            Loading audit and memory…
          </p>
        ) : failed ? (
          <p className="rounded-xl border border-rose-800 bg-rose-950/40 px-6 py-16 text-center text-rose-200">
            Unable to load AuditLogger or PostTradeMemory
          </p>
        ) : unique.length === 0 ? (
          <p className="rounded-xl border border-slate-800 bg-slate-900/70 px-6 py-16 text-center text-slate-300">
            No activity or memory records
          </p>
        ) : (
          <ol className="space-y-3">
            {unique.map((item) => (
              <li key={item.id} className={`rounded-xl border p-4 ${severityClass(item.severity)}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
                      item.execution_class === REAL_PAPER
                        ? 'border border-emerald-500 bg-emerald-950 text-emerald-300'
                        : 'border border-amber-500 bg-amber-950 text-amber-300'
                    }`}
                  >
                    {item.execution_class}
                  </span>
                  <span className="rounded border border-slate-600 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-slate-300">
                    {item.category}
                  </span>
                  <span className="text-[11px] uppercase tracking-wide text-slate-500">{item.severity}</span>
                </div>
                <dl className="mt-3 grid grid-cols-1 gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
                  <div>
                    <dt className="text-[11px] uppercase tracking-wide text-slate-500">Timestamp</dt>
                    <dd className="font-medium text-white">{item.timestamp}</dd>
                  </div>
                  <div>
                    <dt className="text-[11px] uppercase tracking-wide text-slate-500">Cycle ID</dt>
                    <dd className="font-mono text-xs text-slate-200">{item.cycle_id}</dd>
                  </div>
                  <div>
                    <dt className="text-[11px] uppercase tracking-wide text-slate-500">Event</dt>
                    <dd className="font-medium text-white">{item.event.replace(/_/g, ' ')}</dd>
                  </div>
                  <div>
                    <dt className="text-[11px] uppercase tracking-wide text-slate-500">Symbol</dt>
                    <dd className="font-medium text-white">{item.symbol}</dd>
                  </div>
                  <div className="sm:col-span-2">
                    <dt className="text-[11px] uppercase tracking-wide text-slate-500">Message</dt>
                    <dd className="text-slate-200">{item.message}</dd>
                  </div>
                </dl>
              </li>
            ))}
          </ol>
        )}
      </main>
    </div>
  );
}
