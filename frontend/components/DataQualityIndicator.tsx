'use client';

type Dict = Record<string, unknown>;

const LABELS: Record<string, string> = {
  LIVE_FRESH: 'LIVE FRESH',
  MARKET_CLOSED: 'MARKET CLOSED',
  DATA_STALE: 'DATA STALE',
  DATA_WARNING: 'DATA WARNING',
  DATA_INVALID: 'DATA INVALID',
  DATA_UNAVAILABLE: 'DATA UNAVAILABLE',
  DATA_ERROR: 'MARKET DATA ERROR',
};

function tone(state: string): string {
  if (state === 'LIVE_FRESH') return 'border-line bg-surface text-success';
  if (state === 'MARKET_CLOSED') return 'border-line bg-surface text-muted';
  if (state === 'DATA_WARNING') return 'border-line bg-surface text-warning';
  if (state === 'DATA_STALE') return 'border-line bg-surface text-warning';
  return 'border-line bg-surface text-danger';
}

export default function DataQualityIndicator({
  quality,
  compact = false,
}: {
  quality?: Dict | null;
  compact?: boolean;
}) {
  if (!quality) {
    return (
      <span className="rounded-full border border-line bg-surface px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-muted">
        Data quality · loading
      </span>
    );
  }
  const state = String(quality.integrity_state || '').toUpperCase();
  if (!state) {
    return (
      <span className="rounded-full border border-line bg-surface px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-muted">
        Data quality · loading
      </span>
    );
  }
  const notes = String(quality.notes || quality.integrity_notes || '');
  return (
    <span
      className={`rounded-full border px-2 py-1 text-[10px] font-bold uppercase tracking-wide ${tone(state)}`}
      title={notes}
    >
      {compact ? LABELS[state] || state : `Data quality · ${LABELS[state] || state}`}
    </span>
  );
}
