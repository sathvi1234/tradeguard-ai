import { moneyDisplay } from '@/lib/format';
import { toMarketState } from '@/lib/marketState';
import { MarketStateBadges } from '@/components/MarketStatePanel';

export default function MarketClosedNotice({
  symbol,
  price,
  session,
  freshness,
  timestamp,
  compact = false,
  market,
  streamLive,
  error,
}: {
  symbol?: string;
  price?: unknown;
  session?: unknown;
  freshness?: unknown;
  timestamp?: unknown;
  compact?: boolean;
  market?: unknown;
  streamLive?: boolean;
  error?: unknown;
}) {
  const state = toMarketState(market || { symbol, price, session, freshness, last_update: timestamp }, { streamLive, error, symbol });
  if (state.marketStatus !== 'CLOSED' && state.freshness !== 'STALE' && state.freshness !== 'INVALID' && !state.dataError && state.quoteAvailable && state.simulationEligible) {
    return null;
  }
  if (compact) {
    return (
      <p className="mt-2 text-xs text-slate-300">
        {state.marketStatus === 'CLOSED' ? 'MARKET CLOSED' : 'DATA STALE'} · Session {state.session} · Freshness {state.freshness}
        {state.quoteAvailable && state.price !== null ? ` · Latest ${moneyDisplay(state.price)}` : ''} · {state.reason || 'WAITING FOR FRESH DATA'}
      </p>
    );
  }
  return <MarketStateBadges state={state} />;
}
