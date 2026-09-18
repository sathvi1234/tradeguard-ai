'use client';

import { Suspense, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { useAnalyticsQuote, useMarketData, useWatchlist } from '@/hooks/useApi';
import { useMarketStream } from '@/components/MarketStreamProvider';
import { isMissing, moneyDisplay, NOT_AVAILABLE, pct, pnlClass, shown } from '@/lib/format';
import { normalizeFreshness, normalizeSession } from '@/lib/marketStatus';
import { WATCHLIST } from '@/lib/symbols';
import WatchlistTable from '@/components/WatchlistTable';
import PriceChart from '@/components/PriceChart';
import StockTicket from '@/components/StockTicket';
import CallAgentButton from '@/components/CallAgentButton';
import DashboardAnalytics from '@/components/DashboardAnalytics';
import MarketClosedNotice from '@/components/MarketClosedNotice';
import SafetyStatusStrip from '@/components/SafetyStatusStrip';
import { useAlpacaStatus } from '@/hooks/useApi';

type Dict = Record<string, unknown>;

function asDict(value: unknown): Dict {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Dict) : {};
}

export default function StocksPage() {
  return (
    <Suspense fallback={<p className="px-4 py-6 text-sm text-slate-400">Loading stocks…</p>}>
      <StocksBody />
    </Suspense>
  );
}

function StocksBody() {
  const params = useSearchParams();
  const selected = (params.get('symbol') || 'AAPL').toUpperCase();
  const { items, isLoading, liveMarketData } = useWatchlist([...WATCHLIST]);
  const { market } = useMarketData(selected);
  const { alpaca, error: alpacaError } = useAlpacaStatus();
  const { merge, status: streamStatus } = useMarketStream();
  const { analytics: analyticsPayload, isLoading: analyticsLoading, error: analyticsError } = useAnalyticsQuote(selected);
  const mergedItems = useMemo(() => items.map((row: Dict) => merge(row)), [items, merge]);
  const snap = useMemo(() => {
    const fromList = asDict(mergedItems.find((row: Dict) => String(row.symbol) === selected));
    const fromMarket = merge(asDict(market));
    const fromAnalytics = merge(asDict(analyticsPayload));
    const merged: Dict = { ...fromAnalytics, ...fromMarket, ...fromList, symbol: selected };
    const listBars = Array.isArray(fromList.bars) ? (fromList.bars as unknown[]) : [];
    const marketBars = Array.isArray(fromMarket.bars) ? (fromMarket.bars as unknown[]) : [];
    const analyticsBars = Array.isArray(fromAnalytics.bars) ? (fromAnalytics.bars as unknown[]) : [];
    merged.bars = listBars.length >= 2 ? listBars : marketBars.length >= 2 ? marketBars : analyticsBars;
    return merged;
  }, [mergedItems, market, analyticsPayload, selected, merge]);
  const alpacaOk = !alpacaError && Boolean(alpaca?.connected && alpaca?.authenticated);
  const streamLive = streamStatus.state === 'LIVE' || Boolean(liveMarketData || snap.live);

  return (
    <main className="space-y-5 px-4 py-6 sm:px-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">Trade AI</p>
          <h1 className="text-2xl font-bold text-white">Stocks</h1>
          <p className="mt-1 text-sm text-slate-400">Real Alpaca paper market data. Prices are never hardcoded.</p>
        </div>
        <CallAgentButton symbol={selected} />
      </div>
      <SafetyStatusStrip
        liveMarketData={streamLive}
        alpacaOk={alpacaOk}
        stale={String(snap.freshness).toUpperCase() === 'STALE' && !streamLive}
        reconnecting={streamStatus.state === 'RECONNECTING' || streamStatus.state === 'CONNECTING'}
        disconnected={streamStatus.state === 'DISCONNECTED'}
        connectionState={streamStatus.state || (streamLive ? 'LIVE' : 'CONNECTING')}
      />
      {isLoading && mergedItems.length === 0 ? <p className="text-sm text-slate-400">Loading watchlist from Alpaca…</p> : <WatchlistTable items={mergedItems} selected={selected} />}
      <MarketClosedNotice market={snap} symbol={selected} streamLive={streamStatus.state === 'LIVE'} />

      <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
        <h2 className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">Stock Details</h2>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-white">{shown(snap.symbol || selected)}</p>
            <p className="text-slate-400">{shown(snap.company)}</p>
            <p className="mt-3 text-[10px] font-bold uppercase tracking-wide text-slate-500">Live price</p>
            <p className="text-3xl font-bold text-white">{moneyDisplay(snap.price)}</p>
            <p className={pnlClass(snap.day_change)}>
              {typeof snap.day_change === 'number' ? moneyDisplay(snap.day_change) : NOT_AVAILABLE} ·{' '}
              {typeof snap.day_change_pct === 'number' ? pct(snap.day_change_pct, true) : NOT_AVAILABLE}
            </p>
          </div>
          <CallAgentButton symbol={selected} />
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <Item label="Latest trade" value={moneyDisplay(snap.last_trade_price ?? snap.price)} />
          <Item label="Bid" value={moneyDisplay(snap.bid)} />
          <Item label="Ask" value={moneyDisplay(snap.ask)} />
          <Item label="Mid" value={moneyDisplay(snap.mid)} />
          <Item label="Spread" value={moneyDisplay(snap.spread)} />
          <Item label="Spread %" value={typeof snap.spread_pct === 'number' ? pct(snap.spread_pct, true) : NOT_AVAILABLE} />
          <Item label="Volume" value={shown(snap.volume)} />
          <Item label="Previous close" value={moneyDisplay(snap.previous_close)} />
          <Item label="Session" value={normalizeSession(snap.session)} />
          <Item label="Freshness" value={normalizeFreshness(snap.freshness || snap.data_freshness)} />
          <Item label="Updated" value={shown(snap.last_update)} />
          <Item label="Source" value="ALPACA" />
          <Item label="Feed" value={shown(snap.feed || 'iex').toUpperCase()} />
          <Item label="Status" value={snap.live ? 'LIVE' : shown(streamStatus.state)} />
          <Item label="WebSocket" value={shown(snap.ws_state || streamStatus.state)} />
        </dl>
        {snap.company_note && isMissing(snap.company) ? (
          <p className="mt-2 text-xs text-slate-500">{String(snap.company_note)}</p>
        ) : null}
        <div className="mt-4">
          <PriceChart bars={snap.bars} symbol={selected} />
        </div>
      </section>

      <StockTicket symbol={selected} market={snap} liveStream={streamStatus.state === 'LIVE'} />
      <DashboardAnalytics analytics={analyticsPayload} loading={analyticsLoading} error={analyticsError} />
    </main>
  );
}

function Item({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[10px] uppercase text-slate-500">{label}</dt>
      <dd className="font-semibold text-white">{value}</dd>
    </div>
  );
}
