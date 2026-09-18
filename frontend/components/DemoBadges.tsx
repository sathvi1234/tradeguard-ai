'use client';

import { useDemoMode } from '@/hooks/useDemoMode';

export default function DemoBadges({
  className = '',
  alpacaOk,
  liveMarketData,
}: {
  className?: string;
  alpacaOk?: boolean;
  liveMarketData?: boolean;
}) {
  const demo = useDemoMode();
  return (
    <div className={`flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-wide ${className}`}>
      {demo.enabled ? (
        <span className="rounded-full border border-line bg-primary-soft px-2 py-1 text-primary">Demo Trading · Virtual Money</span>
      ) : null}
      {alpacaOk !== undefined ? (
        <span className={`rounded-full border px-2 py-1 ${alpacaOk ? 'border-line bg-surface text-success' : 'border-line bg-surface text-danger'}`}>
          Alpaca Market Data {alpacaOk ? 'Connected' : 'Offline'}
        </span>
      ) : null}
      {liveMarketData !== undefined ? (
        <span className={`rounded-full border px-2 py-1 ${liveMarketData ? 'border-line bg-surface text-success' : 'border-line bg-surface text-muted'}`}>
          Live Market Data {liveMarketData ? 'On' : 'Off'}
        </span>
      ) : null}
      <span className="rounded-full border border-line bg-surface px-2 py-1 text-foreground">Paper Trading</span>
      <span className="rounded-full border border-line bg-surface px-2 py-1 text-warning">Dry Run</span>
      <span className="rounded-full border border-line bg-surface px-2 py-1 text-danger">Real-Money Trading Off</span>
    </div>
  );
}
