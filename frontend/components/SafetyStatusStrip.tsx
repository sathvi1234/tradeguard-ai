'use client';

export default function SafetyStatusStrip({
  liveMarketData,
  alpacaOk,
  reconnecting,
  disconnected,
  stale,
  connectionState,
}: {
  liveMarketData: boolean;
  alpacaOk: boolean;
  reconnecting?: boolean;
  disconnected?: boolean;
  stale?: boolean;
  connectionState?: string;
}) {
  const state = String(connectionState || (liveMarketData ? 'LIVE' : reconnecting ? 'RECONNECTING' : disconnected ? 'DISCONNECTED' : stale ? 'STALE' : 'CONNECTING')).toUpperCase();
  return (
    <div className="flex flex-wrap gap-2 text-[10px] font-bold uppercase tracking-wide">
      <span className={`rounded-full border px-2 py-1 ${liveMarketData ? 'border-line bg-surface text-success' : 'border-line bg-surface text-muted'}`}>
        {liveMarketData ? 'LIVE MARKET DATA — ON' : 'LIVE MARKET DATA — OFF'}
      </span>
      <span className={`rounded-full border px-2 py-1 ${state === 'LIVE' ? 'border-line bg-surface text-success' : state === 'STALE' ? 'border-line bg-surface text-warning' : state === 'DISCONNECTED' ? 'border-line bg-surface text-danger' : 'border-line bg-surface text-warning'}`}>
        {state === 'LIVE' ? 'LIVE' : state === 'STALE' ? 'STALE' : state === 'RECONNECTING' ? 'RECONNECTING' : state === 'CONNECTING' ? 'CONNECTING' : 'DISCONNECTED'}
      </span>
      <span className={`rounded-full border px-2 py-1 ${alpacaOk ? 'border-line bg-surface text-success' : 'border-line bg-surface text-danger'}`}>
        {alpacaOk ? 'ALPACA MARKET DATA — CONNECTED' : 'ALPACA MARKET DATA — OFFLINE'}
      </span>
      <span className="rounded-full border border-line bg-surface px-2 py-1 text-foreground">DEMO VIRTUAL TRADING</span>
      <span className="rounded-full border border-line bg-surface px-2 py-1 text-warning">DRY RUN / SAFETY MODE</span>
      <span className="rounded-full border border-line bg-surface px-2 py-1 text-danger">REAL-MONEY EXECUTION OFF</span>
    </div>
  );
}
