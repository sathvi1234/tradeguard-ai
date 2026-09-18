'use client';

import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { API_BASE_URL } from '@/lib/api';
import { WATCHLIST } from '@/lib/symbols';

type Quote = Record<string, unknown>;

type StreamStatus = {
  state: string;
  feed: string;
  live_market_data?: boolean;
  error?: string | null;
};

type StreamValue = {
  quotes: Record<string, Quote>;
  status: StreamStatus;
  merge: (item: Quote) => Quote;
};

const DEFAULT_STATUS: StreamStatus = { state: 'DISCONNECTED', feed: 'iex' };

const MarketStreamContext = createContext<StreamValue>({
  quotes: {},
  status: DEFAULT_STATUS,
  merge: (item) => item,
});

function apiWsUrl(symbols: string[]): string {
  const origin =
    API_BASE_URL ||
    (typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1:8001');
  const ws = origin.replace(/^http/i, 'ws');
  return `${ws}/api/v1/stream/market?symbols=${encodeURIComponent(symbols.join(','))}`;
}

export function mergeStreamQuote(item: Quote, streamed?: Quote, wsState?: string): Quote {
  const next: Quote = { ...item };
  if (wsState) next.ws_state = wsState;
  if (!streamed) return next;
  for (const key of ['price', 'bid', 'ask', 'mid', 'spread', 'spread_pct', 'last_trade_price', 'last_trade_size']) {
    if (typeof streamed[key] === 'number') next[key] = streamed[key];
  }
  if (streamed.last_update) {
    next.last_update = streamed.last_update;
    next.freshness = 'FRESH';
    next.data_freshness = 'FRESH';
    next.live = true;
    next.live_market_data = true;
  }
  if (typeof streamed.volume === 'number') next.stream_volume = streamed.volume;
  next.feed = streamed.feed || next.feed || 'iex';
  next.ws_state = streamed.ws_state || wsState || next.ws_state;
  const prev = next.previous_close;
  const price = next.price;
  if (typeof prev === 'number' && prev > 0 && typeof price === 'number') {
    next.day_change = Math.round((price - prev) * 10000) / 10000;
    next.day_change_pct = (price - prev) / prev;
  }
  return next;
}

export function MarketStreamProvider({ children }: { children: ReactNode }) {
  const [quotes, setQuotes] = useState<Record<string, Quote>>({});
  const [status, setStatus] = useState<StreamStatus>(DEFAULT_STATUS);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      if (stopped) return;
      const ws = new WebSocket(apiWsUrl([...WATCHLIST]));
      socketRef.current = ws;
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(String(event.data)) as Quote;
          if (msg.type === 'status') {
            setStatus({
              state: String(msg.state || 'DISCONNECTED'),
              feed: String(msg.feed || 'iex'),
              live_market_data: Boolean(msg.live_market_data),
              error: typeof msg.error === 'string' ? msg.error : null,
            });
            return;
          }
          if ((msg.type === 'quote' || msg.type === 'trade') && typeof msg.symbol === 'string') {
            setQuotes((prev) => ({ ...prev, [String(msg.symbol)]: msg }));
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onerror = () => {
        setStatus((prev) => ({ ...prev, state: 'RECONNECTING' }));
      };
      ws.onclose = () => {
        setStatus((prev) => ({ ...prev, state: stopped ? 'DISCONNECTED' : 'RECONNECTING' }));
        if (!stopped) timer = setTimeout(connect, 2000);
      };
    }

    connect();
    return () => {
      stopped = true;
      if (timer) clearTimeout(timer);
      socketRef.current?.close();
    };
  }, []);

  const value = useMemo<StreamValue>(
    () => ({
      quotes,
      status,
      merge: (item) => mergeStreamQuote(item, quotes[String(item.symbol || '')], status.state),
    }),
    [quotes, status]
  );

  return <MarketStreamContext.Provider value={value}>{children}</MarketStreamContext.Provider>;
}

export function useMarketStream() {
  return useContext(MarketStreamContext);
}

export function useStreamQuote(symbol: string) {
  const { quotes, status, merge } = useMarketStream();
  return { quote: quotes[symbol], status, merge };
}
